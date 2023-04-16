import requests
import json
import matplotlib.pyplot as plt
import numpy
import pandas as pd
import seaborn as sns
import argparse
import sys
import streamlit as st

def generateCharts(api_url, proxy=()):
    proxies = {
        'http':proxy
    }
    response = requests.get(api_url, proxies=proxies, timeout=60)
    df = pd.DataFrame(json.loads(response.text))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["volume"] = df["volume"].astype(float)
    df["count"] = 1
    df["premium"] = df["premium"].astype(float)

    #load currencies json file
    with open('currencies.json') as f:
        currenciesLUT = json.load(f)
    #convert the currenciesLUT to a dictionary
    currenciesLUT = {int(k):v for k,v in currenciesLUT.items()}
    df["currencySymbol"] = df['currency'].str['id'].map(currenciesLUT) #add the currency symbol to the dataframe

    #count the number of contracts and total volume for each day in df
    groupedPerDay = df.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})

    sns.set_style("whitegrid")
    #drop last day as it is incomplete
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Contracts per day", "Date", "Contracts", "count")
    generateLineplot(groupedPerDay, "Traded volume per day (BTC)", "Date", "BTC", "volume")
    
    #Compute cumulative volume
    groupedPerDay["volume"] = groupedPerDay["volume"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative volume (BTC)", "Date", "BTC", "volume")

    #Compute cumulative count of contracts
    groupedPerDay["count"] = groupedPerDay["count"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative num contracts", "Date", "Contracts", "count")

    groupedPerMonth = df.groupby([pd.Grouper(key='timestamp', freq='M')]).agg({'count': 'count', 'volume': 'sum'})    
    #drop last month as it is incomplete
    groupedPerMonth = groupedPerMonth[:-1]

    #replace timestamp with month name and year
    groupedPerMonth.index = groupedPerMonth.index.strftime('%B %Y')
    #change index name
    groupedPerMonth.index.name = "Month"
    generateBarplot(groupedPerMonth, "Contracts per month", "Month", "Contracts", "count")
    generateBarplot(groupedPerMonth, "Volume per month (BTC)", "Month", "BTC", "volume")

    #order the currencies by volume
    volumePerCurrency = df.groupby(["currencySymbol"]).agg({'volume': 'sum'})
    volumePerCurrency = volumePerCurrency.sort_values(by=['volume'], ascending=False)
    #get the list of currencies
    currencies = volumePerCurrency.index.tolist()
    generateCurrenciesDailyContractsPlot(df, currencies)
    generateCurrenciesCumulativeVolPlot(df, currencies)

    #Average volume per day
    groupedPerDay = df.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'volume': 'mean'})
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Average volume per day (BTC)", "Date", "BTC", "volume")

    #calculate average premium and number of contracts per currency
    groupedPerCurrency = df.groupby(["currencySymbol"]).agg({'premium': 'mean', 'count': 'sum'})
    #order by premium distance to 0
    groupedPerCurrency = groupedPerCurrency.sort_values(by=['count'], ascending=False)
    numContracts = 0
    totalContracts = df.shape[0]
    numCurrencies = 0
    #count the number of currencies that contain the 95% of the total number of contracts
    for index, currency in groupedPerCurrency.iterrows():
        numContracts += currency['count']
        numCurrencies += 1
        if numContracts > totalContracts * 0.95:
            break
    #keep only the currencies that have 95% of the contracts
    groupedPerCurrencyTop95 = groupedPerCurrency[:numCurrencies]
    generateBarplot(groupedPerCurrencyTop95, "Contracts per currency (95% of contracts)", "Currency", "Contracts", "count")
    groupedPerCurrencyBelow95 = groupedPerCurrency[numCurrencies:]
    generateBarplot(groupedPerCurrencyBelow95, "Contracts per currency (remaining contracts)", "Currency", "Contracts", "count")
    generateBarplot(groupedPerCurrency, "Average premium per currency", "Currency", "Premium", "premium")

    generateCurrenciesHistograms(df, currencies)

    #calculate average premium per day weighted by volume
    df["premium"] = df["premium"] * df["volume"]
    groupedPerDay = df.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'premium': 'sum', 'volume': 'sum'})
    groupedPerDay["premium"] = groupedPerDay["premium"] / groupedPerDay["volume"]
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Average premium per day", "Date", "Premium", "premium")

def generateCurrenciesHistograms(df, currencies):
    for currency in currencies:
        fig = plt.figure(figsize=(12, 6))
        if currency == 'BTC':
            plt.title("BTC Swaps per premium")
            plt.ylabel('Swaps')
        else:
            plt.title(str(currency) + " Contracts per premium")
            plt.ylabel('Contracts')
        currencyData = df.loc[df['currencySymbol']==currency]
        if len(currencyData) < 5:
            continue
        #order by premium distance to mean
        mean = currencyData["premium"].mean()
        currencyData = currencyData.sort_values(by=['premium'], key=lambda x: abs(x - mean))
        #keep only the 95% of the data around 0 premium
        currencyData = currencyData[:int(len(currencyData) * 0.95)]
        #find min and max premium
        minPremium = currencyData["premium"].min()
        maxPremium = currencyData["premium"].max()
        if (maxPremium - minPremium < 0.1):
            continue
        ax = sns.histplot(data=currencyData, x="premium", binwidth=0.1, binrange=(minPremium, maxPremium))
        if len(ax.patches) < 3:
            continue
        for p in ax.patches:
            if (p.get_height() > 0):
                ax.annotate(str(p.get_height()), (p.get_x() + p.get_width() / 2., p.get_height()), ha='center', va='center', xytext=(0, 10), textcoords='offset points')
        step = ((maxPremium - minPremium) / 20).round(1)
        #set the x axis labels in the middle of the bins and with one decimal
        ticks = numpy.arange(minPremium, maxPremium, step=step)
        plt.xticks(ticks + 0.05, ticks.round(1))
        st.pyplot(fig)

def generateCurrenciesDailyContractsPlot(df, currencies):
    fig = plt.figure(figsize=(10, 4))
    plt.title("Daily contracts by currency")
    plt.xlabel("Date")
    plt.ylabel("Contracts")
    for currency in currencies:
        currencyData = df.loc[df['currencySymbol']==currency]
        groupedPerDay = currencyData.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})
        groupedPerDay = groupedPerDay[:-1]
        if groupedPerDay.empty:
            continue
        ax = sns.lineplot(data=groupedPerDay, x=groupedPerDay.index, y="count")
        #get the last value
        lastValue = groupedPerDay["count"].iloc[-1]
        ax.lines[-1].set_label(str(currency))
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., ncol=2)
    st.pyplot(fig)

def generateCurrenciesCumulativeVolPlot(df, currencies):
    fig = plt.figure(figsize=(10, 4))
    plt.title("Cumulative volume (BTC) by currency")
    plt.xlabel("Date")
    plt.ylabel("BTC")
    for currency in currencies:
        #filter the data with index 1 equal to the currency
        currencyData = df.loc[df['currencySymbol']==currency]
        groupedPerDayAndCurrency = currencyData.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})
        groupedPerDayAndCurrency["volume"] = groupedPerDayAndCurrency["volume"].cumsum()
        #get the last value
        lastValue = groupedPerDayAndCurrency["volume"].iloc[-1]
        if lastValue > 0.001:
            ax = sns.lineplot(data=groupedPerDayAndCurrency, x=groupedPerDayAndCurrency.index, y="volume")
            ax.lines[-1].set_label(str(currency) + " {:.3f}".format(lastValue))
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., ncol=2)
    st.pyplot(fig)

def generateBarplot(data, title, xlabel, ylabel, yfield):
    fig = plt.figure(figsize=(10, 4))
    ax = sns.barplot(data=data, x=data.index, y=yfield)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=90, fontsize=8)
    st.pyplot(fig)

def generateLineplot(data, title, xlabel, ylabel, yfield):
    fig = plt.figure(figsize=(10, 4))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    ax = sns.lineplot(data=data, x=data.index, y=yfield)
    st.pyplot(fig)

if __name__ == "__main__":
     #get the api url from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument("-api_url", help="the url of the api")
    parser.add_argument("-proxy_url", help="the url of the tor proxy")
    args = parser.parse_args()
    api_url = args.api_url
    proxy_url = args.proxy_url
    st.title('RoboSats P2P Stats')
    generateCharts(api_url, proxy_url)
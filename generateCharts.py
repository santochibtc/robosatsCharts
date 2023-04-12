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
    df["currencyId"] = df['currency'].str['id'] #extract the currency id from the currency object
    #count the number of contracts and total volume for each day in df
    groupedPerDay = df.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})

    sns.set_style("whitegrid")
    #drop last day as it is incomplete
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Contracts per day", "Date", "Contracts", "count", 1.5, "contractsPerDay.jpg")
    generateLineplot(groupedPerDay, "Traded volume per day (BTC)", "Date", "BTC", "volume", 'auto', "volumePerDay.jpg")
    
    #Compute cumulative volume
    groupedPerDay["volume"] = groupedPerDay["volume"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative volume (BTC)", "Date", "BTC", "volume", 1.5, "cumulativeVolume.jpg")

    #Compute cumulative count of contracts
    groupedPerDay["count"] = groupedPerDay["count"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative num contracts", "Date", "Contracts", "count", 'auto', "cumulativeContracts.jpg")

    groupedPerMonth = df.groupby([pd.Grouper(key='timestamp', freq='M')]).agg({'count': 'count', 'volume': 'sum'})    
    #drop last month as it is incomplete
    groupedPerMonth = groupedPerMonth[:-1]

    #replace timestamp with month name and year
    groupedPerMonth.index = groupedPerMonth.index.strftime('%B %Y')
    #change index name
    groupedPerMonth.index.name = "Month"
    
    generateBarplot(groupedPerMonth, "Contracts per month", "Month", "Contracts", "count", 1.5, "contractsPerMonth.jpg")
    generateBarplot(groupedPerMonth, "Volume per month (BTC)", "Month", "BTC", "volume", 1.5, "volumePerMonth.jpg")

    #order the currencies by volume
    volumePerCurrency = df.groupby(["currencyId"]).agg({'volume': 'sum'})
    volumePerCurrency = volumePerCurrency.sort_values(by=['volume'], ascending=False)
    #get the list of currencies
    currencies = volumePerCurrency.index.tolist()
    generateCurrenciesDailyContractsPlot(df, currencies)
    generateCurrenciesCumulativeVolPlot(df, currencies)

def generateCurrenciesDailyContractsPlot(df, currencies):
    fig = plt.figure(figsize=(10, 4))
    plt.title("Daily contracts by currency")
    plt.xlabel("Date")
    plt.ylabel("Contracts")
    for currency in currencies:
        currencyData = df.loc[df['currencyId']==currency]
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
        currencyData = df.loc[df['currencyId']==currency]
        groupedPerDayAndCurrency = currencyData.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})
        groupedPerDayAndCurrency["volume"] = groupedPerDayAndCurrency["volume"].cumsum()
        #get the last value
        lastValue = groupedPerDayAndCurrency["volume"].iloc[-1]
        if lastValue > 0.001:
            ax = sns.lineplot(data=groupedPerDayAndCurrency, x=groupedPerDayAndCurrency.index, y="volume")
            ax.lines[-1].set_label(str(currency) + " {:.3f}".format(lastValue))
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., ncol=2)
    st.pyplot(fig)

def generateBarplot(data, title, xlabel, ylabel, yfield, aspect, filename):
    fig = plt.figure(figsize=(10, 4))
    ax = sns.barplot(data=data, x=data.index, y=yfield)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=90, fontsize=8)
    plt.gca().set_aspect(aspect)
    ratio = 0.5
    xleft, xright = ax.get_xlim()
    ybottom, ytop = ax.get_ylim()
    ax.set_aspect(abs((xright-xleft)/(ybottom-ytop))*ratio)
    st.pyplot(fig)

def generateLineplot(data, title, xlabel, ylabel, yfield, aspect, filename):
    fig = plt.figure(figsize=(10, 4))
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    #plt.xticks(rotation=45, fontsize=8)
    ax = sns.lineplot(data=data, x=data.index, y=yfield)
    plt.gca().set_aspect(aspect)
    ratio = 0.5
    xleft, xright = ax.get_xlim()
    ybottom, ytop = ax.get_ylim()
    ax.set_aspect(abs((xright-xleft)/(ybottom-ytop))*ratio)
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
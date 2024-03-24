import requests
import json
import matplotlib.pyplot as plt
import numpy
import pandas as pd
import seaborn as sns
import argparse
import sys
import streamlit as st
import datetime


def generateCharts(api_url, proxy=()):
    proxies = {"http": proxy}
    start = datetime.date(2022, 1, 1)
    end = start + datetime.timedelta(days=31)
    df = pd.DataFrame()
    while(start < datetime.date.today()):
        url_width_dates = api_url + '?start=' + start.strftime('%d-%m-%Y') + '&end=' + end.strftime('%d-%m-%Y')
        response = requests.get(url_width_dates, proxies=proxies, timeout=60)
        df = pd.concat([df, pd.DataFrame(json.loads(response.text))])        
        start += datetime.timedelta(days=31) 
        end += datetime.timedelta(days=31)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["volume"] = df["volume"].astype(float)
    df["count"] = 1
    df["premium"] = df["premium"].astype(float)

    # load currencies json file
    with open("currencies.json") as f:
        currenciesLUT = json.load(f)
    # convert the currenciesLUT to a dictionary
    currenciesLUT = {int(k): v for k, v in currenciesLUT.items()}
    df["currencySymbol"] = (
        df["currency"].map(currenciesLUT)
    )  # add the currency symbol to the dataframe
    df = df.drop_duplicates(
        subset=["timestamp", "currencySymbol", "volume", "price", "premium"]
    )

    # count the number of contracts and total volume for each day in df
    groupedPerDay = df.groupby([pd.Grouper(key="timestamp", freq="D")]).agg(
        {"count": "sum", "volume": "sum"}
    )

    sns.set_style("whitegrid")
    # drop last day as it is incomplete
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Contracts per day", "Date", "Contracts", "count")
    generateLineplot(groupedPerDay, "Volume per day (BTC)", "Date", "BTC", "volume")

    # Average volume per day
    groupedPerDayAvg = groupedPerDay.copy()
    groupedPerDayAvg["volume"] = groupedPerDayAvg["volume"] / groupedPerDayAvg["count"]
    generateLineplot(
        groupedPerDayAvg, "Average volume per day (BTC)", "Date", "BTC", "volume"
    )

    # Compute cumulative volume
    groupedPerDay["volume"] = groupedPerDay["volume"].cumsum()
    # get the last value of the cumulative volume
    generateLineplot(
        groupedPerDay,
        "Cumulative volume " + str(groupedPerDay.iloc[-1]["volume"].round(3)) + " BTC",
        "Date",
        "BTC",
        "volume",
    )

    # Compute cumulative count of contracts
    groupedPerDay["count"] = groupedPerDay["count"].cumsum()
    generateLineplot(
        groupedPerDay,
        "Cumulative num contracts " + str(int(groupedPerDay.iloc[-1]["count"])),
        "Date",
        "Contracts",
        "count",
    )

    groupedPerMonth = df.groupby([pd.Grouper(key="timestamp", freq="M")]).agg(
        {"count": "count", "volume": "sum"}
    )
    # drop last month as it is incomplete
    #groupedPerMonth = groupedPerMonth[:-1]

    # replace timestamp with month name and year
    groupedPerMonth.index = groupedPerMonth.index.strftime("%B %Y")
    # change index name
    groupedPerMonth.index.name = "Month"
    generateBarplot(
        groupedPerMonth, "Contracts per month", "Month", "Contracts", "count"
    )
    generateBarplot(
        groupedPerMonth, "Volume per month (BTC)", "Month", "BTC", "volume", 2
    )

    # order the currencies by volume
    volumePerCurrency = df.groupby(["currencySymbol"]).agg({"volume": "sum"})
    volumePerCurrency = volumePerCurrency.sort_values(by=["volume"], ascending=False)
    # get the list of currencies
    currencies = volumePerCurrency.index.tolist()
    generateCurrenciesDailyContractsPlot(df, currencies)
    generateCurrenciesCumulativeVolPlot(df, currencies)

    # calculate average premium and number of contracts per currency
    groupedPerCurrency = df.groupby(["currencySymbol"]).agg(
        {"premium": "mean", "count": "sum"}
    )
    # order by premium distance to 0
    groupedPerCurrency = groupedPerCurrency.sort_values(by=["count"], ascending=False)
    numContracts = 0
    totalContracts = df.shape[0]
    numCurrencies = 0
    # count the number of currencies that contain the 95% of the total number of contracts
    for index, currency in groupedPerCurrency.iterrows():
        numContracts += currency["count"]
        numCurrencies += 1
        if numContracts > totalContracts * 0.95:
            break
    # keep only the currencies that have 95% of the contracts
    groupedPerCurrencyTop95 = groupedPerCurrency[:numCurrencies]
    generateBarplot(
        groupedPerCurrencyTop95,
        "Contracts per currency (95% of contracts)",
        "Currency",
        "Contracts",
        "count",
    )
    groupedPerCurrencyBelow95 = groupedPerCurrency[numCurrencies:]
    generateBarplot(
        groupedPerCurrencyBelow95,
        "Contracts per currency (remaining contracts)",
        "Currency",
        "Contracts",
        "count",
    )
    generateBarplot(
        groupedPerCurrency,
        "Average premium per currency",
        "Currency",
        "Premium",
        "premium",
        2,
    )

    generateCurrenciesHistograms(df, currencies)

    # agrregate by day of the week
    df["dayOfWeek"] = df["timestamp"].dt.day_name()
    groupedPerDayOfWeek = df.groupby(["dayOfWeek"]).agg(
        {"count": "sum", "volume": "sum"}
    )
    # order by day of the week
    groupedPerDayOfWeek = groupedPerDayOfWeek.reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    )
    # plot the number of contracts per day of the week
    generateBarplot(
        groupedPerDayOfWeek,
        "Contracts per day of the week",
        "Day of the week",
        "Contracts",
        "count",
    )
    # plot the volume per day of the week
    generateBarplot(
        groupedPerDayOfWeek,
        "Volume per day of the week (BTC)",
        "Day of the week",
        "BTC",
        "volume",
        2,
    )

    # calculate average premium per day weighted by volume
    df["premium"] = df["premium"] * df["volume"]
    groupedPerDay = df.groupby([pd.Grouper(key="timestamp", freq="D")]).agg(
        {"premium": "sum", "volume": "sum"}
    )
    groupedPerDay["premium"] = groupedPerDay["premium"] / groupedPerDay["volume"]
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(
        groupedPerDay, "Average premium per day", "Date", "Premium", "premium"
    )


def generateCurrenciesHistograms(df, currencies):
    for currency in currencies:
        fig = plt.figure(figsize=(12, 6))
        currencyData = df.loc[df["currencySymbol"] == currency]
        median = currencyData["premium"].median()
        if currency == "BTC":
            plt.title("BTC Swaps per premium, median=" + str(median.round(1)))
            plt.ylabel("Swaps")
        else:
            plt.title(
                str(currency) + " Contracts per premium, median=" + str(median.round(1))
            )
            plt.ylabel("Contracts")
        if len(currencyData) < 5:
            continue
        # order by premium distance to median
        currencyData = currencyData.sort_values(
            by=["premium"], key=lambda x: abs(x - median)
        )
        # keep only the 95% of the data around 0 premium
        currencyData = currencyData[: int(len(currencyData) * 0.95)]
        # find min and max premium
        minPremium = currencyData["premium"].min().round(1)
        maxPremium = currencyData["premium"].max().round(1)
        if maxPremium - minPremium < 0.1:
            continue
        binwidth = 0.2
        ax = sns.histplot(
            data=currencyData,
            x="premium",
            binwidth=binwidth,
            binrange=(minPremium, maxPremium),
        )
        if len(ax.patches) < 3:
            continue
        addBarsValues(ax, 2)
        # add median vertical line
        ax.axvline(median)
        step = ((maxPremium - minPremium) / 20).round(1)
        # set the x axis labels in the middle of the bins and with one decimal
        ticks = numpy.arange(minPremium, maxPremium, step=step).round(1)
        plt.xticks(ticks=ticks, labels=ticks)
        st.pyplot(fig)


def addBarsValues(ax, decimals=0):
    for p in ax.patches:
        if p.get_height() > 0:
            if decimals > 0:
                text = str(p.get_height().round(decimals))
            else:
                text = str(p.get_height().astype(int))
            ax.annotate(
                text,
                (p.get_x() + p.get_width() / 2.0, p.get_height()),
                ha="center",
                va="center",
                xytext=(0, 10),
                textcoords="offset points",
            )


def generateCurrenciesDailyContractsPlot(df, currencies):
    fig = plt.figure(figsize=(10, 4))
    plt.title("Daily contracts by currency")
    plt.xlabel("Date")
    plt.ylabel("Contracts")
    for currency in currencies:
        currencyData = df.loc[df["currencySymbol"] == currency]
        groupedPerDay = currencyData.groupby(
            [pd.Grouper(key="timestamp", freq="D")]
        ).agg({"count": "sum", "volume": "sum"})
        groupedPerDay = groupedPerDay[:-1]
        if groupedPerDay.empty:
            continue
        ax = sns.lineplot(data=groupedPerDay, x=groupedPerDay.index, y="count")
        # get the last value
        lastValue = groupedPerDay["count"].iloc[-1]
        ax.lines[-1].set_label(str(currency))
    plt.legend(ncol=2)
    st.pyplot(fig)


def generateCurrenciesCumulativeVolPlot(df, currencies):
    fig = plt.figure(figsize=(10, 4))
    plt.title("Cumulative volume (BTC) by currency")
    plt.xlabel("Date")
    plt.ylabel("BTC")
    for currency in currencies:
        # filter the data with index 1 equal to the currency
        currencyData = df.loc[df["currencySymbol"] == currency]
        groupedPerDayAndCurrency = currencyData.groupby(
            [pd.Grouper(key="timestamp", freq="D")]
        ).agg({"count": "sum", "volume": "sum"})
        groupedPerDayAndCurrency["volume"] = groupedPerDayAndCurrency["volume"].cumsum()
        # get the last value
        lastValue = groupedPerDayAndCurrency["volume"].iloc[-1]
        if lastValue > 0.001:
            ax = sns.lineplot(
                data=groupedPerDayAndCurrency,
                x=groupedPerDayAndCurrency.index,
                y="volume",
            )
            ax.lines[-1].set_label(str(currency) + " {:.3f}".format(lastValue))
    plt.legend(ncol=2)
    st.pyplot(fig)


def generateBarplot(data, title, xlabel, ylabel, yfield, decimals=0):
    fig = plt.figure(figsize=(10, 4))
    ax = sns.barplot(data=data, x=data.index, y=yfield)
    addBarsValues(ax, decimals)
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
    # get the api url from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument("-api_url", help="the url of the api")
    parser.add_argument("-proxy_url", help="the url of the tor proxy")
    args = parser.parse_args()
    api_url = args.api_url
    proxy_url = args.proxy_url
    st.title("RoboSats P2P Stats")
    generateCharts(api_url, proxy_url)

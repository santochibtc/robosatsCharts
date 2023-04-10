import requests
import json
import matplotlib.pyplot as plt
import numpy
import pandas as pd
import seaborn as sns
import argparse
import sys

def generateCharts(api_url, proxy=()):
    proxies = {
        'http':proxy
    }
    response = requests.get(api_url, proxies=proxies, timeout=60)
    df = pd.DataFrame(json.loads(response.text))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["volume"] = df["volume"].astype(float)
    df["count"] = 1
    #count the number of contracts and total volume for each day in df
    groupedPerDay = df.groupby([pd.Grouper(key='timestamp', freq='D')]).agg({'count': 'sum', 'volume': 'sum'})

    sns.set_style("whitegrid")
    #drop last day as it is incomplete
    groupedPerDay = groupedPerDay[:-1]
    generateLineplot(groupedPerDay, "Contracts per day", "Date", "Number", "count", 1.5, "contractsPerDay.jpg")
    generateLineplot(groupedPerDay, "Traded volume per day (BTC)", "Date", "BTC", "volume", 'auto', "volumePerDay.jpg")
    
    #Compute cumulative volume
    groupedPerDay["volume"] = groupedPerDay["volume"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative volume (BTC)", "Date", "BTC", "volume", 1.5, "cumulativeVolume.jpg")

    #Compute cumulative count of contracts
    groupedPerDay["count"] = groupedPerDay["count"].cumsum()
    generateLineplot(groupedPerDay, "Cumulative num contracts", "Date", "BTC", "count", 'auto', "cumulativeContracts.jpg")

    groupedPerMonth = df.groupby([pd.Grouper(key='timestamp', freq='M')]).agg({'count': 'count', 'volume': 'sum'})    
    #drop last month as it is incomplete
    groupedPerMonth = groupedPerMonth[:-1]
    #replace timestamp with month name and year
    groupedPerMonth.index = groupedPerMonth.index.strftime('%B %Y')
    
    generateBarplot(groupedPerMonth, "Contracts per month", "Month", "Number", "count", 1.5, "contractsPerMonth.jpg")
    generateBarplot(groupedPerMonth, "Volume per month", "Month", "Volume", "volume", 1.5, "volumePerMonth.jpg")

def generateBarplot(data, title, xlabel, ylabel, yfield, aspect, filename):
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=90, fontsize=8)
    ax = sns.barplot(data=data, x=data.index, y=yfield)
    plt.gca().set_aspect(aspect)
    ratio = 0.5
    xleft, xright = ax.get_xlim()
    ybottom, ytop = ax.get_ylim()
    ax.set_aspect(abs((xright-xleft)/(ybottom-ytop))*ratio)
    plt.savefig(filename, dpi=250, bbox_inches='tight')
    plt.clf()

def generateLineplot(data, title, xlabel, ylabel, yfield, aspect, filename):
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
    plt.savefig(filename, dpi=250, bbox_inches='tight')
    plt.clf()

if __name__ == "__main__":
     #get the api url from the command line
    parser = argparse.ArgumentParser()
    parser.add_argument("-api_url", help="the url of the api")
    parser.add_argument("-proxy_url", help="the url of the tor proxy")
    args = parser.parse_args()
    api_url = args.api_url
    proxy_url = args.proxy_url
    generateCharts(api_url, proxy_url)
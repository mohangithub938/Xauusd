import numpy as np
import pandas as pd

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def rsi(s,n=14):
    d=s.diff()
    gain=d.clip(lower=0)
    loss=-d.clip(upper=0)
    ag=gain.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    al=loss.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rs=ag/al.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(50)

def atr(df,n=14):
    pc=df.close.shift(1)
    tr=pd.concat([df.high-df.low,(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()

def adx(df,n=14):
    up=df.high.diff()
    down=-df.low.diff()
    plus=up.where((up>down)&(up>0),0.0)
    minus=down.where((down>up)&(down>0),0.0)
    pc=df.close.shift(1)
    tr=pd.concat([df.high-df.low,(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    av=tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    pdi=100*plus.ewm(alpha=1/n,adjust=False,min_periods=n).mean()/av
    mdi=100*minus.ewm(alpha=1/n,adjust=False,min_periods=n).mean()/av
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False,min_periods=n).mean().fillna(0)

def add_technicals(df):
    x=df.copy()
    for n in [9,15,20,50,200]:
        x[f"ema{n}"]=ema(x.close,n)
    x["rsi"]=rsi(x.close)
    x["atr"]=atr(x)
    x["adx"]=adx(x)
    vol=x.volume.replace(0,np.nan)
    typical=(x.high+x.low+x.close)/3
    x["vwap"]=(typical*vol).cumsum()/vol.cumsum()
    x["range"]=x.high-x.low
    x["body"]=(x.close-x.open).abs()
    x["upper_wick"]=x.high-x[["open","close"]].max(axis=1)
    x["lower_wick"]=x[["open","close"]].min(axis=1)-x.low
    return x

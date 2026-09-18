import pandas as pd

def resample(df,rule):
    work = df.copy()
    if work.empty:
        return work
    if not isinstance(work.index, pd.DatetimeIndex):
        work.index = pd.to_datetime(work.index, utc=True, errors="coerce")
    work = work[~pd.isna(work.index)].sort_index()
    if work.empty:
        return work
    return work.resample(rule).agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()

def run(df,signal_fn,mode,horizon=30):
    rows=[]
    for i in range(250,len(df)-horizon):
        window=df.iloc[:i+1].copy()
        sig=signal_fn(window,mode)
        if sig["direction"] not in {"BUY","SELL"}: continue
        p=sig["plan"]; future=df.iloc[i+1:i+1+horizon]
        outcome="OPEN"; exit_price=float(future.close.iloc[-1])
        for _,r in future.iterrows():
            if sig["direction"]=="BUY":
                if r.low<=p["sl"]: outcome,exit_price="LOSS",p["sl"]; break
                if r.high>=p["tp"]: outcome,exit_price="WIN",p["tp"]; break
            else:
                if r.high>=p["sl"]: outcome,exit_price="LOSS",p["sl"]; break
                if r.low<=p["tp"]: outcome,exit_price="WIN",p["tp"]; break
        risk=abs(p["entry"]-p["sl"])
        rmult=(exit_price-p["entry"])/risk if sig["direction"]=="BUY" else (p["entry"]-exit_price)/risk
        rows.append({"time":df.index[i],"direction":sig["direction"],"score":sig["score"],
                     "entry":p["entry"],"sl":p["sl"],"tp":p["tp"],"exit":exit_price,
                     "outcome":outcome,"r_multiple":rmult})
    return pd.DataFrame(rows)

def metrics(results):
    if results.empty: return {}
    closed=results[results.outcome.isin(["WIN","LOSS"])]
    wins=int((closed.outcome=="WIN").sum()); losses=int((closed.outcome=="LOSS").sum())
    gp=float(closed.loc[closed.r_multiple>0,"r_multiple"].sum())
    gl=float(-closed.loc[closed.r_multiple<0,"r_multiple"].sum())
    pf=gp/gl if gl else None
    eq=results.r_multiple.cumsum(); dd=float((eq-eq.cummax()).min())
    return {"signals":len(results),"wins":wins,"losses":losses,
            "win_rate":round(wins/(wins+losses)*100,2) if wins+losses else 0,
            "profit_factor":round(pf,2) if pf is not None else None,
            "avg_r":round(float(results.r_multiple.mean()),3),
            "max_drawdown_r":round(dd,3)}

def detect_structure(df,swing=3,lookback=80):
    x=df.tail(lookback)
    highs=[]; lows=[]
    if len(x)>=2*swing+1:
        h=x.high.to_numpy(); l=x.low.to_numpy(); idx=list(x.index)
        for i in range(swing,len(x)-swing):
            if h[i]==max(h[i-swing:i+swing+1]): highs.append((idx[i],float(h[i])))
            if l[i]==min(l[i-swing:i+swing+1]): lows.append((idx[i],float(l[i])))
    label="NEUTRAL"
    if len(highs)>=2 and len(lows)>=2:
        hh=highs[-1][1]>highs[-2][1]; hl=lows[-1][1]>lows[-2][1]
        lh=highs[-1][1]<highs[-2][1]; ll=lows[-1][1]<lows[-2][1]
        label="BULLISH" if hh and hl else "BEARISH" if lh and ll else "NEUTRAL"
    return {
        "label":label,
        "support":float(x.low.min()),
        "resistance":float(x.high.max()),
        "last_swing_high":highs[-1][1] if highs else None,
        "last_swing_low":lows[-1][1] if lows else None,
    }

def breakout(df,lookback=20):
    if len(df)<lookback+2: return False,False
    prior=df.iloc[-lookback-1:-1]
    last=df.iloc[-1]
    return bool(last.close>prior.high.max()),bool(last.close<prior.low.min())

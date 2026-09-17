def detect_regime(df):
    if len(df)<210: return "WARMING_UP"
    r=df.iloc[-1]
    if r.adx>=25 and r.ema20>r.ema50: return "TRENDING_BULLISH"
    if r.adx>=25 and r.ema20<r.ema50: return "TRENDING_BEARISH"
    med=df.atr.tail(100).median()
    if med and r.atr>1.5*med: return "HIGH_VOLATILITY"
    return "RANGING_OR_NEUTRAL"

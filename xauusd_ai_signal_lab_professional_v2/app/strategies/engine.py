from app.strategies.modes import MODE_RULES
from app.structure.market_structure import detect_structure,breakout

def score_setup(mode,context,setup,trigger):
    c=context.iloc[-1]; s=setup.iloc[-1]; t=trigger.iloc[-1]
    buy=sell=0; rb=[]; rs=[]

    if c.ema20>c.ema50: buy+=25; rb.append("Higher-timeframe trend bullish")
    elif c.ema20<c.ema50: sell+=25; rs.append("Higher-timeframe trend bearish")

    st=detect_structure(setup)
    if st["label"]=="BULLISH": buy+=20; rb.append("Setup structure bullish")
    elif st["label"]=="BEARISH": sell+=20; rs.append("Setup structure bearish")

    if s.ema9>s.ema15: buy+=10; rb.append("Setup EMA9 > EMA15")
    elif s.ema9<s.ema15: sell+=10; rs.append("Setup EMA9 < EMA15")

    if t.ema9>t.ema15: buy+=10; rb.append("Trigger EMA9 > EMA15")
    elif t.ema9<t.ema15: sell+=10; rs.append("Trigger EMA9 < EMA15")

    if t.rsi>=55: buy+=10; rb.append(f"Trigger RSI supportive ({t.rsi:.1f})")
    elif t.rsi<=45: sell+=10; rs.append(f"Trigger RSI supportive ({t.rsi:.1f})")

    b,u=breakout(trigger,15)
    if b: buy+=15; rb.append("Trigger upside breakout")
    if u: sell+=15; rs.append("Trigger downside breakout")

    if t.close>t.vwap: buy+=5; rb.append("Price above VWAP")
    elif t.close<t.vwap: sell+=5; rs.append("Price below VWAP")

    if t.adx<15:
        buy=max(0,buy-10); sell=max(0,sell-10)

    direction="BUY" if buy>sell else "SELL" if sell>buy else "WAIT"
    if max(buy,sell)<MODE_RULES[mode]["min_score"]:
        direction="WAIT"

    return {
        "direction":direction,
        "score":int(max(buy,sell)),
        "buy_score":int(buy),
        "sell_score":int(sell),
        "reasons":rb if direction=="BUY" else rs if direction=="SELL" else ["Confirmation incomplete"],
        "structure":st,
        "atr":float(t.atr) if t.atr==t.atr else 0.0,
    }

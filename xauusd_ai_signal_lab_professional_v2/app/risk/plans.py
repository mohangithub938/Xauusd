from app.strategies.modes import MODE_RULES

def build_plan(mode,direction,bid,ask,atr,sl_atr=None):
    if direction not in {"BUY","SELL"} or atr<=0:
        return {"entry":None,"sl":None,"tp":None,"rr":None,"risk_distance":None}
    rules=MODE_RULES[mode]
    mult=rules["sl_atr"] if sl_atr is None else sl_atr
    rr=2.0 if mode=="SCALP" else rules["rr"]
    entry=float(ask if direction=="BUY" else bid)
    risk=float(atr*mult)
    sl=entry-risk if direction=="BUY" else entry+risk
    tp=entry+risk*rr if direction=="BUY" else entry-risk*rr
    return {"entry":entry,"sl":sl,"tp":tp,"rr":rr,"risk_distance":risk}

import requests
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

print("=== XAUUSD AI Signal Lab Preflight ===")
try:
    r=requests.get("https://biquote.io/api/XAUUSD",
                   params={"allowStale":"false"},
                   headers={"Accept":"application/json","User-Agent":"XAUUSD-AI-Signal-Lab/2.0"},
                   timeout=(5,10))
    r.raise_for_status()
    q=r.json()
    print("[OK] XAUUSD REST",r.status_code,"Bid:",q.get("bid"),"Ask:",q.get("ask"),"Age:",q.get("quoteAgeSeconds"),"State:",q.get("marketState"))
except Exception as e:
    print("[FAIL] XAUUSD REST feed:",e)
    raise SystemExit(2)

try:
    import streamlit,pandas,numpy,plotly,groq,pysignalr,websocket
    print("[OK] Python packages available")
except Exception as e:
    print("[FAIL] Packages:",e)
    raise SystemExit(1)

print("[OK] SignalR dependency available")
print("=== Preflight complete ===")

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.append(str(Path(__file__).resolve().parents[2]))

IST_TZ = ZoneInfo("Asia/Kolkata")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from app.ai.chat import answer as chat_answer
from app.ai.groq_service import explain
from app.alerts.email import send as send_email
from app.backtest.engine import metrics as backtest_metrics, resample, run as backtest_run
from app.config.settings import settings
from app.data.biquote import FeedError
from app.data.live_stream import XAUUSDTickStream
from app.indicators.technical import add_technicals
from app.regime.regime import detect_regime
from app.risk.plans import build_plan
from app.storage.alert_state import can_send, mark_sent
from app.storage.journal import init_db, log_signal, recent
from app.strategies.engine import score_setup
from app.strategies.modes import MODE_RULES

st.set_page_config(page_title="XAUUSD Signal Lab", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
init_db()

# ------------------------------
# Light, professional visual system
# ------------------------------
st.markdown("""
<style>
:root{--ink:#172233;--muted:#6c7a8d;--line:#e4e9ef;--canvas:#f5f7fa;--card:#fff;--blue:#2d63d7;--blue-soft:#edf3ff;--green:#11845a;--green-soft:#eaf8f1;--red:#c84b58;--red-soft:#fff0f2;--amber:#9c6806;--amber-soft:#fff6e3}
.stApp{background:var(--canvas);color:var(--ink)}
[data-testid="stHeader"]{background:rgba(245,247,250,.97);border-bottom:1px solid var(--line)}
[data-testid="stSidebar"]{background:#ffffff;border-right:1px solid var(--line)}
[data-testid="stSidebarContent"]{padding:.95rem .85rem 1.3rem}
[data-testid="stSidebar"] *{color:var(--ink)!important}
[data-testid="stSidebar"] .stCaption{color:var(--muted)!important}
.block-container{max-width:1850px;padding:1.15rem 1.55rem 3.5rem}
.navbrand{padding:4px 7px 13px}.navbrand .eyebrow{font-size:.66rem;font-weight:850;letter-spacing:.16em;color:#8995a5}.navbrand .name{font-size:1.22rem;font-weight:900;letter-spacing:-.03em}.navbrand .sub{font-size:.73rem;color:var(--muted);line-height:1.35;margin-top:4px}
.navlabel{font-size:.65rem;text-transform:uppercase;letter-spacing:.14em;font-weight:850;color:#8a96a5;margin:15px 7px 7px}
.livebox{background:#fbfcfe;border:1px solid var(--line);border-radius:13px;padding:10px 11px}.liveok{color:var(--green)}.livebad{color:var(--red)}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px}.dotok{background:#20a06f;box-shadow:0 0 0 4px rgba(32,160,111,.1)}.dotbad{background:#d05a68;box-shadow:0 0 0 4px rgba(208,90,104,.1)}
.hero{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px 24px;box-shadow:0 8px 26px rgba(25,38,55,.045);margin-bottom:14px}.hero-row{display:flex;justify-content:space-between;gap:20px;align-items:center}.eyebrow{font-size:.68rem;text-transform:uppercase;letter-spacing:.15em;font-weight:850;color:#8793a2}.hero h1{font-size:2rem;line-height:1.05;margin:.16rem 0 .35rem;letter-spacing:-.045em}.hero p{color:var(--muted);font-size:.84rem;line-height:1.5;max-width:1100px;margin:0}.pricebig{font-size:1.85rem;font-weight:950;letter-spacing:-.05em;text-align:right}.pricemeta{font-size:.71rem;color:var(--muted);text-align:right;margin-top:2px}
.card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:16px 17px;box-shadow:0 6px 20px rgba(25,38,55,.03)}.cardtitle{font-size:.68rem;text-transform:uppercase;letter-spacing:.11em;font-weight:850;color:#8591a0;margin-bottom:7px}.tiny{font-size:.72rem;color:var(--muted);line-height:1.45}
.signal{border-radius:18px;padding:17px;border:1px solid var(--line)}.buy{background:var(--green-soft);border-color:#c9e8da}.sell{background:var(--red-soft);border-color:#efd0d5}.wait{background:#f8fafc;border-color:#dfe5ec}.signalword{font-size:2rem;font-weight:950;letter-spacing:-.05em}.score{font-size:1.55rem;font-weight:950}
.reason{border:1px solid #e8edf2;background:#fbfcfe;border-radius:10px;padding:8px 10px;margin:6px 0;font-size:.77rem;color:#344255}.section{display:flex;justify-content:space-between;align-items:end;margin:17px 0 8px}.section strong{font-size:.96rem}.section span{font-size:.71rem;color:var(--muted)}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px 12px;box-shadow:0 4px 16px rgba(25,38,55,.02)}
[data-testid="stMetricLabel"]{font-size:.66rem!important;text-transform:uppercase!important;letter-spacing:.05em!important;color:#7d8998!important}.stButton>button{border-radius:10px;border:1px solid #d9e0e8;background:#fff;font-weight:750}.stButton>button:hover{color:var(--blue);border-color:#9eb7ea}
[data-testid="stChatMessage"]{background:#fff;border:1px solid var(--line);border-radius:14px}.alert{background:#f1f6ff;border:1px solid #d5e0f7;color:#39577e;border-radius:11px;padding:10px 12px;font-size:.76rem}.successline{background:var(--green-soft);border:1px solid #c9e8da;color:#186846;border-radius:11px;padding:10px 12px;font-size:.76rem}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# Session configuration
# ------------------------------
def init_state():
    defaults = {
        "page":"Market", "mode":"SCALP", "refresh_sec":2,
        "min_score":MODE_RULES["SCALP"]["min_score"], "sl_atr":float(MODE_RULES["SCALP"]["sl_atr"]),
        "groq_key":settings.groq_key, "groq_model":settings.groq_model,
        "email_enabled":False, "email_threshold":50, "email_cooldown":15,
        "chat_messages":[], "pending_question":"",
    }
    for k,v in defaults.items():
        if k not in st.session_state: st.session_state[k]=v
init_state()

# ------------------------------
# Sidebar: navigation + compact controls
# ------------------------------
with st.sidebar:
    st.markdown('<div class="navbrand"><div class="eyebrow">XAUUSD / SPOT CFD</div><div class="name">Signal Lab</div><div class="sub">Market intelligence · signal engine · AI copilot · alerts</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="navlabel">Workspace</div>', unsafe_allow_html=True)
    pages=["Market","Signals","AI Copilot","Backtest","Settings"]
    st.session_state.page=st.radio("Workspace", pages, index=pages.index(st.session_state.page), label_visibility="collapsed")
    st.markdown('<div class="navlabel">Quick controls</div>', unsafe_allow_html=True)
    new_mode=st.selectbox("Trading mode", ["SCALP","INTRADAY","SWING"], index=["SCALP","INTRADAY","SWING"].index(st.session_state.mode))
    if new_mode != st.session_state.mode:
        st.session_state.mode=new_mode
        st.session_state.min_score=MODE_RULES[new_mode]["min_score"]
        st.session_state.sl_atr=float(MODE_RULES[new_mode]["sl_atr"])
    st.session_state.min_score=st.slider("Minimum signal score",60,95,int(st.session_state.min_score))
    st.session_state.sl_atr=st.slider("SL = ATR ×",0.5,2.5,float(st.session_state.sl_atr),0.1)
    st.markdown('<div class="navlabel">Stream</div>', unsafe_allow_html=True)
    stream_badge=st.empty()
    st.markdown('<div class="navlabel">Display</div>', unsafe_allow_html=True)
    st.session_state.refresh_sec=st.slider("Dashboard refresh",1,10,int(st.session_state.refresh_sec))
    st.caption("Display refresh only. The market tick stream is independent.")

@st.cache_resource
def stream_client():
    client=XAUUSDTickStream(settings.biquote_base_url,"XAUUSD",1000)
    client.start(); return client

stream=stream_client()
try:
    q=stream.latest_quote(); seed=stream.completed_candles()
except FeedError as exc:
    st.error(str(exc)); st.stop()
except Exception as exc:
    st.error(f"Live stream startup failed: {exc}"); st.stop()
status=stream.snapshot(); stream_on=bool(status.get("connected"))
stream_badge.markdown(
    f'<div class="livebox"><span class="dot {"dotok" if stream_on else "dotbad"}"></span><b class="{"liveok" if stream_on else "livebad"}">{"LIVE TICK STREAM" if stream_on else "RECONNECTING"}</b><div class="tiny" style="margin-top:5px">{status.get("tick_count",0):,} ticks · {status.get("completed_candles",0):,} candles · {status.get("reconnects",0)} reconnects</div></div>',
    unsafe_allow_html=True,
)
if st.session_state.page in {"Market","Signals"}:
    st_autorefresh(interval=int(st.session_state.refresh_sec)*1000,key="dashboard_refresh")

# ------------------------------
# Analysis snapshot
# ------------------------------
def tf(df, rule): return add_technicals(resample(df,rule))
m1=add_technicals(seed); m5=tf(seed,"5min"); m15=tf(seed,"15min"); h1=tf(seed,"1h"); h4=tf(seed,"4h")
mode=st.session_state.mode
if mode=="SCALP": context,setup,trigger,tf_label=m15,m5,m1,"15m → 5m → 1m"
elif mode=="INTRADAY": context,setup,trigger,tf_label=h1,m15,m5,"1H → 15m → 5m"
else: context,setup,trigger,tf_label=h4,h1,m15,"4H → 1H → 15m"
if len(trigger)<220:
    st.warning(f"Warming up: {len(trigger)} completed trigger candles loaded. Keep the stream running so history can build.")
    st.stop()
analysis=score_setup(mode,context,setup,trigger)
regime=detect_regime(trigger); row=trigger.iloc[-1]
direction=analysis["direction"] if analysis["score"]>=st.session_state.min_score else "WAIT"
plan=build_plan(mode,direction,q["bid"],q["ask"],analysis["atr"],st.session_state.sl_atr)
signal_ts = trigger.index[-1].tz_localize("UTC").tz_convert(IST_TZ).isoformat() if trigger.index[-1].tzinfo is None else trigger.index[-1].tz_convert(IST_TZ).isoformat(); signal_key=f'{mode}|{signal_ts}|{direction}|{analysis["score"]}'

# Auto Gmail alert with automatic Groq explanation
if st.session_state.email_enabled and direction in {"BUY","SELL"} and analysis["score"]>=st.session_state.email_threshold:
    try:
        if can_send("gmail",signal_key,int(st.session_state.email_cooldown)*60):
            snap={"symbol":"XAUUSD","mode":mode,"direction":direction,"score":analysis["score"],"regime":regime,"bid":q["bid"],"ask":q["ask"],"spread":q["spread"],"entry":plan["entry"],"sl":plan["sl"],"tp":plan["tp"],"rr":plan["rr"],"reasons":analysis["reasons"],"rsi":float(row.rsi),"atr":float(row.atr),"adx":float(row.adx)}
            groq_text="Groq explanation unavailable."
            if st.session_state.groq_key:
                try: groq_text=explain(st.session_state.groq_key,st.session_state.groq_model,snap)
                except Exception as ge: groq_text=f"Groq unavailable: {ge}"
            subject=f'XAUUSD {mode} {direction} — Strong Signal {analysis["score"]}/100'
            body=(f'XAUUSD STRONG SIGNAL\n\nMODE: {mode}\nDIRECTION: {direction}\nSCORE: {analysis["score"]}/100\nREGIME: {regime}\n\nMARKET\nBid: {q["bid"]:.4f}\nAsk: {q["ask"]:.4f}\nSpread: {q["spread"]:.4f}\nTick age: {q["quoteAgeSeconds"]:.1f}s\n\nTRADE PLAN\nEntry: {plan["entry"]:.4f}\nSL: {plan["sl"]:.4f}\nTP: {plan["tp"]:.4f}\nR:R: 1:{plan["rr"]:.1f}\n\nEVIDENCE\n'+'\n'.join(f'- {x}' for x in analysis["reasons"])+f'\n\nGROQ ANALYSIS\n--------------\n{groq_text}\n\nData path: BiQuote SignalR tick stream → local 1m candles.\nNo order was executed by this application.\n')
            send_email(settings.gmail_sender,settings.gmail_app_password,settings.gmail_recipient,subject,body); mark_sent("gmail",signal_key); st.toast("Strong-signal email sent.",icon="📧")
    except Exception as exc: st.warning(f"Email alert failed: {exc}")

if "last_journal_key" not in st.session_state: st.session_state.last_journal_key=None
if direction in {"BUY","SELL"} and signal_key!=st.session_state.last_journal_key:
    log_signal({"timestamp":signal_ts,"mode":mode,"direction":direction,"score":analysis["score"],"plan":plan,"bid":q["bid"],"ask":q["ask"],"spread":q["spread"],"regime":regime,"reasons":analysis["reasons"]})
    st.session_state.last_journal_key=signal_key
journal=recent(250)

# ------------------------------
# Helpers
# ------------------------------
def header(title, subtitle):
    st.markdown(f'<div class="hero"><div class="hero-row"><div><div class="eyebrow">XAUUSD · Spot / CFD</div><h1>{title}</h1><p>{subtitle}</p></div><div><div class="pricebig">{q["mid"]:.2f}</div><div class="pricemeta">Bid {q["bid"]:.2f} · Ask {q["ask"]:.2f} · Spread {q["spread"]:.2f}</div></div></div></div>',unsafe_allow_html=True)

def sigclass(d): return "buy" if d=="BUY" else "sell" if d=="SELL" else "wait"

def journal_items(df, limit=30):
    out=[]
    if df.empty:return out
    for _,x in df.head(limit).iterrows():
        out.append({"timestamp":str(x.get("ts")),"mode":x.get("mode"),"direction":x.get("direction"),"score":x.get("score"),"entry":x.get("entry"),"sl":x.get("sl"),"tp":x.get("tp"),"rr":x.get("rr"),"regime":x.get("regime"),"status":x.get("status"),"reasons":x.get("reasons")})
    return out

chat_context={"now_ist":datetime.now(IST_TZ).isoformat(),"current_quote":{"bid":q["bid"],"ask":q["ask"],"mid":q["mid"],"spread":q["spread"],"quote_age_seconds":q["quoteAgeSeconds"],"market_open":q.get("marketOpen")},"current_signal":{"mode":mode,"direction":direction,"score":analysis["score"],"minimum_score":st.session_state.min_score,"regime":regime,"timeframe_chain":tf_label,"reasons":analysis["reasons"],"entry":plan["entry"],"sl":plan["sl"],"tp":plan["tp"],"rr":plan["rr"],"rsi":float(row.rsi),"atr":float(row.atr),"adx":float(row.adx)},"stream":{"connected":stream_on,"tick_count":status.get("tick_count",0),"completed_candles":status.get("completed_candles",0),"reconnects":status.get("reconnects",0)},"recent_journal":journal_items(journal)}

# ------------------------------
# MARKET PAGE
# ------------------------------
if st.session_state.page=="Market":
    header("Market Command Center","Your primary trading view: live price, clean chart, engine state and a deterministic 1:2 scalp plan where applicable.")
    c=st.columns(4); c[0].metric("LIVE PRICE",f'{q["mid"]:.2f}',f'Spread {q["spread"]:.2f}'); c[1].metric("SIGNAL",direction,f'{analysis["score"]}/100'); c[2].metric("REGIME",regime,mode); c[3].metric("STREAM","CONNECTED" if stream_on else "RECONNECTING",f'{status.get("tick_count",0):,} ticks')
    st.markdown(f'<div class="section"><strong>Price & structure</strong><span>{tf_label} · completed candles · live tick feed</span></div>',unsafe_allow_html=True)
    left,right=st.columns([2.25,1],gap="large")
    with left:
        view=trigger.tail(300); fig=go.Figure()
        fig.add_trace(go.Candlestick(x=view.index,open=view.open,high=view.high,low=view.low,close=view.close,name="XAUUSD",increasing_line_color="#14865d",decreasing_line_color="#c84b58",increasing_fillcolor="#edf9f3",decreasing_fillcolor="#fff1f3"))
        for col,label,w,dash in [("ema9","EMA 9",1.8,"solid"),("ema15","EMA 15",1.7,"solid"),("vwap","VWAP",1.2,"dot")]:
            if col in view.columns: fig.add_trace(go.Scatter(x=view.index,y=view[col],name=label,line={"width":w,"dash":dash}))
        if not journal.empty:
            j=journal.copy(); j["ts"]=pd.to_datetime(j["ts"],utc=True,errors="coerce"); j=j.dropna(subset=["ts"]); j=j[j["ts"]>=view.index.min()]
            for dn,sym in [("BUY","triangle-up"),("SELL","triangle-down")]:
                s=j[j.direction.eq(dn)]
                if not s.empty: fig.add_trace(go.Scatter(x=s.ts,y=s.entry,mode="markers",name=f"{dn} signal",marker={"symbol":sym,"size":11},customdata=s[["score"]].to_numpy(),hovertemplate=f'{dn} · score %{{customdata[0]}}<extra></extra>'))
        fig.update_layout(height=590,margin={"l":5,"r":10,"t":8,"b":6},paper_bgcolor="#fff",plot_bgcolor="#fff",xaxis_rangeslider_visible=False,legend={"orientation":"h","y":1.02,"x":0},xaxis={"showgrid":False},yaxis={"gridcolor":"#edf1f5"},font={"color":"#425166"},hovermode="x unified")
        st.plotly_chart(fig,use_container_width=True,config={"displaylogo":False,"scrollZoom":True})
        cc=stream.current_candle()
        if cc: st.markdown(f'<div class="card"><span class="eyebrow">FORMING 1M</span> &nbsp; <b>O {cc["open"]:.2f}</b> &nbsp; <b>H {cc["high"]:.2f}</b> &nbsp; <b>L {cc["low"]:.2f}</b> &nbsp; <b>C {cc["close"]:.2f}</b> <span class="tiny"> · {int(cc["volume"])} ticks</span></div>',unsafe_allow_html=True)
    with right:
        st.markdown(f'<div class="signal {sigclass(direction)}"><div class="eyebrow">CURRENT ENGINE STATE</div><div class="signalword">{direction}</div><div style="display:flex;justify-content:space-between;align-items:center"><span class="tiny">Score threshold {st.session_state.min_score}</span><span class="score">{analysis["score"]}/100</span></div></div>',unsafe_allow_html=True)
        st.markdown('<div class="section"><strong>Trade plan</strong><span>Python-calculated · no order execution</span></div>',unsafe_allow_html=True)
        p=st.columns(2); p[0].metric("ENTRY","—" if plan["entry"] is None else f'{plan["entry"]:.2f}'); p[1].metric("STOP","—" if plan["sl"] is None else f'{plan["sl"]:.2f}'); p[0].metric("TARGET","—" if plan["tp"] is None else f'{plan["tp"]:.2f}'); p[1].metric("R:R","—" if plan["rr"] is None else f'1:{plan["rr"]:.1f}')
        st.markdown('<div class="section"><strong>Why this state?</strong><span>Engine evidence</span></div>',unsafe_allow_html=True)
        for r in analysis["reasons"][:7]: st.markdown(f'<div class="reason">{r}</div>',unsafe_allow_html=True)
        k=st.columns(3); k[0].metric("RSI",f'{row.rsi:.1f}'); k[1].metric("ATR",f'{row.atr:.2f}'); k[2].metric("ADX",f'{row.adx:.1f}')

# ------------------------------
# SIGNALS PAGE
# ------------------------------
elif st.session_state.page=="Signals":
    header("Signal Desk","A dedicated workspace for reviewing qualified signals without crowding the live market screen.")
    c=st.columns(4); c[0].metric("RECORDED",len(journal)); c[1].metric("BUY",int((journal.direction=="BUY").sum()) if not journal.empty else 0); c[2].metric("SELL",int((journal.direction=="SELL").sum()) if not journal.empty else 0); c[3].metric("CURRENT",direction,f'{analysis["score"]}/100')
    if journal.empty: st.info("No qualified BUY/SELL signals have been recorded yet.")
    else:
        show=journal.copy(); show["ts"]=pd.to_datetime(show["ts"],utc=True,errors="coerce").dt.tz_convert(IST_TZ).dt.strftime("%Y-%m-%d %H:%M:%S IST"); show=show[["ts","mode","direction","score","entry","sl","tp","rr","regime","status"]].rename(columns={"ts":"Timestamp","mode":"Mode","direction":"Direction","score":"Score","entry":"Entry","sl":"SL","tp":"TP","rr":"R:R","regime":"Regime","status":"Status"}); st.dataframe(show,use_container_width=True,hide_index=True)
        latest=journal.iloc[0]; st.markdown('<div class="section"><strong>Latest setup</strong><span>Most recently recorded qualified signal</span></div>',unsafe_allow_html=True)
        a,b=st.columns([1.0,2.2]); a.markdown(f'<div class="signal {sigclass(str(latest.direction))}"><div class="eyebrow">{latest.mode}</div><div class="signalword">{latest.direction}</div><div class="tiny">Score {int(latest.score)}/100 · {latest.regime}</div></div>',unsafe_allow_html=True); x=b.columns(4); x[0].metric("Entry",f'{float(latest.entry):.2f}'); x[1].metric("SL",f'{float(latest.sl):.2f}'); x[2].metric("TP",f'{float(latest.tp):.2f}'); x[3].metric("R:R",f'1:{float(latest.rr):.1f}'); st.markdown(f'<div class="tiny" style="margin-top:10px"><b>Evidence:</b> {latest.reasons}</div>',unsafe_allow_html=True)

# ------------------------------
# AI COPILOT PAGE
# ------------------------------
elif st.session_state.page=="AI Copilot":
    header("AI Copilot","Ask about current conditions, recent signals, the reason for WAIT, or whether the journal contains a signal you may have missed.")
    left,right=st.columns([1.65,.75],gap="large")
    with left:
        st.markdown('<div class="cardtitle">Suggested questions</div>',unsafe_allow_html=True)
        suggestions=["Did I miss any strong signals recently?","Why is the engine showing WAIT?","What was the last qualified signal?","What changed in the last few signals?","Explain the current setup simply."]
        sc=st.columns(3)
        for i,text in enumerate(suggestions):
            if sc[i%3].button(text,key=f"suggest_{i}",use_container_width=True): st.session_state.pending_question=text
        if st.button("Clear chat",key="clear_chat"): st.session_state.chat_messages=[]; st.session_state.pending_question=""; st.rerun()
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        question=st.chat_input("Ask about XAUUSD, signals, WAIT, or the journal…")
        if st.session_state.pending_question:
            question=st.session_state.pending_question; st.session_state.pending_question=""
        if question:
            st.session_state.chat_messages.append({"role":"user","content":question})
            with st.chat_message("user"): st.markdown(question)
            if not st.session_state.groq_key: reply="Add your Groq API key in Settings before using the copilot."
            else:
                try: reply=chat_answer(st.session_state.groq_key,st.session_state.groq_model,question,chat_context)
                except Exception as exc: reply=f"Groq request failed: {exc}"
            st.session_state.chat_messages.append({"role":"assistant","content":reply})
            with st.chat_message("assistant"): st.markdown(reply)
    with right:
        st.markdown('<div class="card"><div class="cardtitle">Live context</div>',unsafe_allow_html=True); st.metric("Signal",direction,f'{analysis["score"]}/100'); st.metric("Regime",regime,mode); st.metric("Quote age",f'{q["quoteAgeSeconds"]:.1f}s'); st.markdown('</div>',unsafe_allow_html=True)
        st.markdown('<div class="section"><strong>Data boundary</strong></div>',unsafe_allow_html=True)
        st.markdown('<div class="alert">The copilot uses the live snapshot + recorded journal. It will not invent a missed signal that the journal does not contain.</div>',unsafe_allow_html=True)

# ------------------------------
# BACKTEST PAGE
# ------------------------------
elif st.session_state.page=="Backtest":
    header("Research Lab","Run the deterministic strategy over historical OHLC data. Results are research outputs, not a guarantee of future performance.")
    uploaded=st.file_uploader("Upload OHLC CSV",type=["csv"])
    if uploaded:
        df=pd.read_csv(uploaded); st.write("Columns:",", ".join(df.columns)); date_col=st.selectbox("Datetime column",list(df.columns),index=0)
        if not {"open","high","low","close"}.issubset(df.columns): st.error("CSV needs open, high, low and close columns."); st.stop()
        df[date_col]=pd.to_datetime(df[date_col],errors="coerce",utc=True); df=df.dropna(subset=[date_col]).set_index(date_col).sort_index();
        if "volume" not in df.columns: df["volume"]=1
        if st.button("Run backtest",type="primary"):
            def sig_fn(window,md):
                if md=="SCALP": ctx,stp,trg=add_technicals(resample(window,"15min")),add_technicals(resample(window,"5min")),add_technicals(resample(window,"1min"))
                elif md=="INTRADAY": ctx,stp,trg=add_technicals(resample(window,"1h")),add_technicals(resample(window,"15min")),add_technicals(resample(window,"5min"))
                else: ctx,stp,trg=add_technicals(resample(window,"4h")),add_technicals(resample(window,"1h")),add_technicals(resample(window,"15min"))
                an=score_setup(md,ctx,stp,trg); d=an["direction"] if an["score"]>=st.session_state.min_score else "WAIT"; p=build_plan(md,d,float(window.close.iloc[-1]),float(window.close.iloc[-1]),an["atr"],st.session_state.sl_atr); return {"direction":d,"score":an["score"],"plan":p}
            with st.spinner("Running backtest…"): results=backtest_run(df,sig_fn,mode,horizon=30)
            mm=backtest_metrics(results)
            if not mm: st.warning("No trades/signals were generated for this dataset and configuration.")
            else:
                k=st.columns(5); k[0].metric("Signals",mm["signals"]); k[1].metric("Wins",mm["wins"]); k[2].metric("Losses",mm["losses"]); k[3].metric("Win rate",f'{mm["win_rate"]:.2f}%'); k[4].metric("Profit factor","—" if mm["profit_factor"] is None else mm["profit_factor"]); st.dataframe(results,use_container_width=True,hide_index=True)

# ------------------------------
# SETTINGS PAGE
# ------------------------------
else:
    header("Settings & Control","Configuration is separated from the market view so the primary dashboard stays clean.")
    a,b=st.columns(2,gap="large")
    with a:
        st.markdown('<div class="cardtitle">ENGINE</div>',unsafe_allow_html=True)
        st.session_state.refresh_sec=st.slider("Dashboard refresh",1,10,int(st.session_state.refresh_sec),key="settings_refresh")
        nm=st.selectbox("Trading mode",["SCALP","INTRADAY","SWING"],index=["SCALP","INTRADAY","SWING"].index(st.session_state.mode),key="settings_mode")
        if nm!=st.session_state.mode: st.session_state.mode=nm; st.session_state.min_score=MODE_RULES[nm]["min_score"]; st.session_state.sl_atr=float(MODE_RULES[nm]["sl_atr"])
        st.session_state.min_score=st.slider("Minimum signal score",50,95,int(st.session_state.min_score),key="settings_score")
        st.session_state.sl_atr=st.slider("SL = ATR ×",0.5,2.5,float(st.session_state.sl_atr),0.1,key="settings_atr")
        st.markdown(f'<div class="successline">Live feed: <b>{"CONNECTED" if stream_on else "RECONNECTING"}</b> · BiQuote SignalR → local 1m candle builder</div>',unsafe_allow_html=True)
    with b:
        st.markdown('<div class="cardtitle">GROQ AI</div>',unsafe_allow_html=True)
        st.caption("Groq key is configured in app/config/settings.py and is not shown in the dashboard.")
        st.session_state.groq_model=st.selectbox("Groq model",["openai/gpt-oss-120b","openai/gpt-oss-20b"],index=0 if st.session_state.groq_model=="openai/gpt-oss-120b" else 1)
        st.markdown('<div class="cardtitle" style="margin-top:16px">GMAIL ALERTS</div>',unsafe_allow_html=True)
        st.session_state.email_enabled=st.checkbox("Automatic strong-signal emails",value=st.session_state.email_enabled)
        st.caption("Credentials are configured in app/config/settings.py and are not shown in the dashboard.")
        st.session_state.email_threshold=st.selectbox(
            "Strong-signal threshold",
            [45, 50, 60, 70, 80],
            index=[45, 50, 60, 70, 80].index(int(st.session_state.email_threshold)),
            key="settings_email_threshold",
        )
        st.session_state.email_cooldown=st.slider("Email cooldown (minutes)",1,60,int(st.session_state.email_cooldown),key="settings_email_cooldown")
    st.markdown('<div class="alert">Automatic path: strong new signal → Python calculates Entry/SL/TP → Groq explains → Gmail sends. The AI Copilot is separate and optional. No order execution.</div>',unsafe_allow_html=True)

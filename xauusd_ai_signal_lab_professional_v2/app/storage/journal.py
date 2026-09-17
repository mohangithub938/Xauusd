from pathlib import Path
import sqlite3
import pandas as pd
DB=Path("xauusd_signal_journal.sqlite3")

def init_db():
    con=sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS signals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT,mode TEXT,direction TEXT,score INTEGER,
        entry REAL,sl REAL,tp REAL,rr REAL,bid REAL,ask REAL,spread REAL,regime TEXT,status TEXT,reasons TEXT)""")
    con.commit(); con.close()

def log_signal(s):
    init_db(); p=s["plan"]; con=sqlite3.connect(DB)
    con.execute("""INSERT INTO signals(
        ts,mode,direction,score,entry,sl,tp,rr,bid,ask,spread,regime,status,reasons)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (s["timestamp"],s["mode"],s["direction"],s["score"],p["entry"],p["sl"],p["tp"],p["rr"],
         s["bid"],s["ask"],s["spread"],s["regime"],s.get("status","TRIGGERED")," | ".join(s["reasons"])))
    con.commit(); con.close()

def recent(limit=250):
    init_db(); con=sqlite3.connect(DB)
    df=pd.read_sql_query("SELECT * FROM signals ORDER BY id DESC LIMIT ?",con,params=(limit,))
    con.close(); return df

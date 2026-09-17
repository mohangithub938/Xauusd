from pathlib import Path
import sqlite3,time
DB=Path("xauusd_alert_state.sqlite3")

def _db():
    con=sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS state(channel TEXT PRIMARY KEY,last_key TEXT,last_sent REAL)")
    con.commit()
    return con

def can_send(channel,key,cooldown_seconds):
    con=_db(); row=con.execute("SELECT last_key,last_sent FROM state WHERE channel=?",(channel,)).fetchone(); con.close()
    if not row: return True
    last_key,last_sent=row
    return last_key!=key and (time.time()-float(last_sent)>=cooldown_seconds)

def mark_sent(channel,key):
    con=_db()
    con.execute("""INSERT INTO state(channel,last_key,last_sent) VALUES(?,?,?)
                   ON CONFLICT(channel) DO UPDATE SET last_key=excluded.last_key,last_sent=excluded.last_sent""",
                (channel,key,time.time()))
    con.commit(); con.close()

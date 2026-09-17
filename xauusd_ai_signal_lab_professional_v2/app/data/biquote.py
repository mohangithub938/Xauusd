from __future__ import annotations

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import requests
import pandas as pd

class FeedError(RuntimeError):
    pass

class BiQuote:
    def __init__(self, base_url="https://biquote.io", timeout=8):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "XAUUSD-AI-Signal-Lab/1.0",
        })

    def _get(self, path, params=None):
        try:
            r = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                timeout=(4, self.timeout)
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.SSLError as exc:
            raise FeedError(
                "SSL/TLS verification failed. Run: pip install -r requirements.txt "
                "in the same virtual environment and restart the app."
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise FeedError("XAUUSD feed timed out. Check network/VPN/proxy.") from exc
        except requests.exceptions.RequestException as exc:
            raise FeedError(f"XAUUSD feed request failed: {exc}") from exc
        except ValueError as exc:
            raise FeedError("XAUUSD feed returned invalid JSON.") from exc

    def latest(self, symbol="XAUUSD"):
        data = self._get(f"/api/{symbol}", {"allowStale": "false"})
        if data.get("stale") is True:
            raise FeedError("Provider returned a stale XAUUSD quote.")
        if "bid" not in data or "ask" not in data:
            raise FeedError("Quote response is missing bid/ask.")
        return data

    def ohlc(self, symbol="XAUUSD", interval="1m", limit=1000):
        data = self._get(
            f"/api/{symbol}/ohlc",
            {"interval": interval, "limit": min(int(limit), 1000)}
        )
        bars = data.get("bars")
        if not isinstance(bars, list) or not bars:
            raise FeedError("No XAUUSD OHLC bars returned.")
        df = pd.DataFrame(bars)
        if "openTime" not in df.columns:
            raise FeedError("OHLC response is missing openTime.")
        df["openTime"] = pd.to_datetime(df["openTime"], utc=True, errors="coerce")
        df = df.dropna(subset=["openTime"]).set_index("openTime").sort_index()
        for col in ["open","high","low","close"]:
            if col not in df.columns:
                raise FeedError(f"OHLC response is missing {col}.")
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "tickVolume" in df.columns:
            df["volume"] = pd.to_numeric(df["tickVolume"], errors="coerce").fillna(0)
        elif "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        else:
            df["volume"] = 0
        if "isOpen" in df.columns:
            df = df[~df["isOpen"].fillna(False)]
        df = df[["open","high","low","close","volume"]].dropna()
        if df.empty:
            raise FeedError("No valid completed XAUUSD candles after cleaning.")
        return df

def normalize_quote(q):
    bid = float(q["bid"])
    ask = float(q["ask"])
    return {
        "symbol": q.get("symbol", "XAUUSD"),
        "bid": bid,
        "ask": ask,
        "mid": float(q.get("mid", (bid+ask)/2)),
        "spread": float(q.get("spread", ask-bid)),
        "timestamp": q.get("timestamp"),
        "marketState": q.get("marketState", "unknown"),
        "quoteAgeSeconds": float(q.get("quoteAgeSeconds", 999)),
        "source": q.get("source", ""),
        "stale": bool(q.get("stale", False)),
    }

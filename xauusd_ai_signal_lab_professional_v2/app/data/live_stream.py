from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

IST_TZ = ZoneInfo("Asia/Kolkata")

from app.data.biquote import BiQuote, FeedError, normalize_quote

try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass


@dataclass
class StreamStatus:
    connected: bool = False
    started: bool = False
    last_tick_time: float = 0.0
    tick_count: int = 0
    completed_candles: int = 0
    current_candle_start: str = ""
    last_error: str = ""
    reconnects: int = 0


class XAUUSDTickStream:
    """Persistent XAUUSD SignalR tick stream + local 1-minute candle builder.

    The stream runs in a daemon thread so Streamlit reruns do not recreate the
    network connection. Historical 1m candles are seeded once from REST, then
    every incoming tick updates the forming 1m candle. Strategy analysis should
    use completed_candles() so trigger confirmation happens on closed candles.
    """

    def __init__(self, base_url: str = "https://biquote.io", symbol: str = "XAUUSD", history_limit: int = 1000):
        self.base_url = base_url.rstrip("/")
        self.symbol = symbol.upper()
        self.history_limit = max(300, min(int(history_limit), 1500))
        self.feed = BiQuote(self.base_url)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._bars = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        self._current: dict[str, Any] | None = None
        self._quote: dict[str, Any] | None = None
        self.status = StreamStatus()
        self._seeded = False

    def start(self) -> None:
        with self._lock:
            if self.status.started and self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self.status.started = True
            if not self._seeded:
                try:
                    seed = self.feed.ohlc(self.symbol, "1m", self.history_limit)
                    initial_quote = normalize_quote(self.feed.latest(self.symbol))
                    with self._lock:
                        self._bars = seed.tail(self.history_limit).copy()
                        self._quote = initial_quote
                        self.status.completed_candles = len(self._bars)
                        self._seeded = True
                except Exception as exc:
                    self.status.last_error = f"REST startup seed failed: {exc}"
                    # Keep streaming attempt alive; dashboard can show the failure.

            self._thread = threading.Thread(target=self._run_thread, name="xauusd-signalr", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            self.status.connected = False

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._async_loop())
        except Exception as exc:
            with self._lock:
                self.status.connected = False
                self.status.last_error = f"Stream thread stopped: {exc}"

    async def _async_loop(self) -> None:
        try:
            from pysignalr.client import SignalRClient
        except Exception as exc:
            with self._lock:
                self.status.last_error = "Missing pysignalr. Run: pip install -r requirements.txt"
            return

        while not self._stop.is_set():
            opened = False
            try:
                client = SignalRClient(f"{self.base_url}/hubs/tick")

                async def on_open() -> None:
                    nonlocal opened
                    opened = True
                    with self._lock:
                        self.status.connected = True
                        self.status.last_error = ""
                    # BiQuote's documented Subscribe method takes string[].
                    await client.send("Subscribe", [[self.symbol]])

                async def on_close() -> None:
                    with self._lock:
                        self.status.connected = False

                async def on_error(message) -> None:
                    err = getattr(message, "error", None) or str(message)
                    with self._lock:
                        self.status.connected = False
                        self.status.last_error = f"SignalR error: {err}"

                async def on_tick(message) -> None:
                    payload = message
                    # pysignalr delivers event arguments as a list; BiQuote sends one tick object.
                    if isinstance(payload, list):
                        if not payload:
                            return
                        payload = payload[0]
                    if isinstance(payload, dict):
                        self._handle_tick(payload)

                client.on_open(on_open)
                client.on_close(on_close)
                client.on_error(on_error)
                client.on("ReceiveTick", on_tick)

                await client.run()
            except Exception as exc:
                with self._lock:
                    self.status.connected = False
                    self.status.last_error = f"SignalR connection failed: {exc}"
                    if opened:
                        self.status.reconnects += 1

            if not self._stop.is_set():
                # Small bounded backoff; this is the reconnect delay, not price polling.
                await asyncio.sleep(3.0)

    @staticmethod
    def _tick_time(tick: dict[str, Any]) -> pd.Timestamp:
        raw = tick.get("timestamp") or tick.get("time") or tick.get("timestampUtc") or tick.get("serverTime")
        if raw is None:
            return pd.Timestamp.now(tz=IST_TZ)
        ts = pd.to_datetime(raw, utc=True, errors="coerce")
        if pd.isna(ts):
            return pd.Timestamp.now(tz=IST_TZ)
        return ts.tz_convert(IST_TZ)

    def _handle_tick(self, tick: dict[str, Any]) -> None:
        try:
            symbol = str(tick.get("symbol", self.symbol)).upper()
            if symbol != self.symbol:
                return
            bid = float(tick["bid"])
            ask = float(tick["ask"])
        except (KeyError, TypeError, ValueError):
            return

        ts = self._tick_time(tick)
        # Candles use mid, while execution levels remain bid/ask in the UI.
        mid = float(tick.get("mid", (bid + ask) / 2.0))
        minute = ts.floor("min")

        with self._lock:
            self._quote = normalize_quote({
                **tick,
                "symbol": self.symbol,
                "bid": bid,
                "ask": ask,
                "mid": mid,
                "spread": float(tick.get("spread", ask - bid)),
                "timestamp": tick.get("timestamp") or ts.tz_convert(IST_TZ).isoformat(),
                "quoteAgeSeconds": 0.0,
                "stale": False,
            })
            self.status.last_tick_time = time.time()
            self.status.tick_count += 1

            if self._current is None:
                self._current = {
                    "start": minute,
                    "open": mid,
                    "high": mid,
                    "low": mid,
                    "close": mid,
                    "volume": 1,
                }
            elif minute == self._current["start"]:
                self._current["high"] = max(float(self._current["high"]), mid)
                self._current["low"] = min(float(self._current["low"]), mid)
                self._current["close"] = mid
                self._current["volume"] = int(self._current["volume"]) + 1
            else:
                self._finalize_current()
                # If several minutes passed without ticks, do not invent candles.
                self._current = {
                    "start": minute,
                    "open": mid,
                    "high": mid,
                    "low": mid,
                    "close": mid,
                    "volume": 1,
                }

            ts_start = pd.Timestamp(self._current["start"])
            self.status.current_candle_start = ts_start.tz_convert(IST_TZ).isoformat() if ts_start.tzinfo else ts_start.tz_localize(IST_TZ).isoformat()

    def _finalize_current(self) -> None:
        if not self._current:
            return
        idx = pd.Timestamp(self._current["start"])
        row = pd.DataFrame(
            {
                "open": [float(self._current["open"])],
                "high": [float(self._current["high"])],
                "low": [float(self._current["low"])],
                "close": [float(self._current["close"])],
                "volume": [float(self._current["volume"])],
            },
            index=pd.DatetimeIndex([idx]),
        )
        self._bars = pd.concat([self._bars, row]).sort_index()
        self._bars = self._bars[~self._bars.index.duplicated(keep="last")].tail(self.history_limit)
        self.status.completed_candles = len(self._bars)

    def latest_quote(self) -> dict[str, Any]:
        with self._lock:
            quote = dict(self._quote) if self._quote else None
        if quote:
            if self.status.last_tick_time:
                age = max(0.0, time.time() - self.status.last_tick_time)
            else:
                # Startup REST quote has a provider age; do not poll REST on every UI refresh.
                age = float(quote.get("quoteAgeSeconds", 999.0))
            quote["quoteAgeSeconds"] = age
            quote["stale"] = age > 10.0
            return quote
        raise FeedError("No XAUUSD quote is available yet. Waiting for the initial REST seed or tick stream.")

    def completed_candles(self) -> pd.DataFrame:
        with self._lock:
            return self._bars.copy()

    def current_candle(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._current) if self._current else None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "connected": self.status.connected,
                "started": self.status.started,
                "last_tick_time": self.status.last_tick_time,
                "tick_count": self.status.tick_count,
                "completed_candles": self.status.completed_candles,
                "current_candle_start": self.status.current_candle_start,
                "last_error": self.status.last_error,
                "reconnects": self.status.reconnects,
            }

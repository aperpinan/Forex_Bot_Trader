"""Download EUR/USD 5-minute candles from the tastyfx MT5 terminal (with tastyfx's real spread per candle) -> data/eurusd_5m_tastyfx.json"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mt5_conexion import conectar  # noqa: E402

SALIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "eurusd_5m_tastyfx.json")
mt5 = conectar()
try:
    mt5.symbol_select("EURUSD.FX", True)
    fin = dt.datetime.now(dt.timezone.utc)
    velas = None
    for dias in (365, 180, 120, 90, 60):
        velas = mt5.copy_rates_range("EURUSD.FX", mt5.TIMEFRAME_M5, fin - dt.timedelta(days=dias), fin)
        if velas is not None and len(velas):
            break
    # time, open, high, low, close (bid prices), spread in points
    filas = [(int(v["time"]), float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]), int(v["spread"]))
             for v in velas]
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    json.dump(filas, open(SALIDA, "w"))
    sp = sorted(f[5] for f in filas)
    print(f"{len(filas)} candles {dt.datetime.fromtimestamp(filas[0][0], dt.timezone.utc):%Y-%m-%d} -> "
          f"{dt.datetime.fromtimestamp(filas[-1][0], dt.timezone.utc):%Y-%m-%d %H:%M} UTC; spread points median {sp[len(sp) // 2]}, "
          f"90% {sp[int(len(sp) * .9)]}, max {sp[-1]}")
finally:
    mt5.shutdown()

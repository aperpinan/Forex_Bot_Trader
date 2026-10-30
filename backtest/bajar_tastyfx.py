"""Download 5-minute candles from the tastyfx MT5 terminal (with tastyfx's real spread per candle).

    python bajar_tastyfx.py                      -> EURUSD.FX -> data/eurusd_5m_tastyfx.json
    python bajar_tastyfx.py USDJPY.FX USDCHF.FX  -> data/usdjpy_5m_tastyfx.json, data/usdchf_5m_tastyfx.json
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mt5_conexion import conectar  # noqa: E402

DATOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def bajar(mt5, sym):
    mt5.symbol_select(sym, True)
    fin = dt.datetime.now(dt.timezone.utc)
    velas = None
    for dias in (365, 180, 120, 90, 60):
        velas = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M5, fin - dt.timedelta(days=dias), fin)
        if velas is not None and len(velas):
            break
    # time, open, high, low, close (bid prices), spread in points
    filas = [(int(v["time"]), float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]), int(v["spread"]))
             for v in velas]
    salida = os.path.join(DATOS, sym.split(".")[0].lower() + "_5m_tastyfx.json")
    os.makedirs(DATOS, exist_ok=True)
    json.dump(filas, open(salida, "w"))
    sp = sorted(f[5] for f in filas)
    print(f"{sym}: {len(filas)} candles {dt.datetime.fromtimestamp(filas[0][0], dt.timezone.utc):%Y-%m-%d} -> "
          f"{dt.datetime.fromtimestamp(filas[-1][0], dt.timezone.utc):%Y-%m-%d %H:%M} UTC; spread points median "
          f"{sp[len(sp) // 2]}, 90% {sp[int(len(sp) * .9)]}, max {sp[-1]}")


mt5 = conectar()
try:
    for s in sys.argv[1:] or ["EURUSD.FX"]:
        bajar(mt5, s)
finally:
    mt5.shutdown()

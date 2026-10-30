"""Extra exits on top of the per-pair settings, with tastyfx's shared SL / TP per pair (US FIFO rule):

  early   : once the stack is X pips in profit (from the newest entry), close it on the opposite RSI signal
  trailing: once it is A pips in profit, the stop follows the best price D pips behind (TP stays)

Inside a 5-minute candle the order of high and low is unknown: the stop is checked at the level it had BEFORE the
candle, and the trail is moved with that candle's extreme only afterwards (pessimistic).

    python salidas.py
"""
import itertools
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
LOTES = 0.5
# pair: (pip, US$ per pip for 1 lot, RSI level, TP, SL) = the settings the bot uses since 2026-10-30 11:28
PARES = {"eurusd": (0.0001, 10.0, 25, 25, 25), "usdjpy": (0.01, 6.36, 25, 30, 30), "usdchf": (0.0001, 12.16, 30, 50, 50),
         "gbpusd": (0.0001, 10.0, 30, 25, 40), "audusd": (0.0001, 10.0, 25, 20, 70)}
N_RSI, MAXPOS = 7, 3


def rsi(c, n):
    out = [None] * len(c)
    g = l = 0.0
    for i in range(1, len(c)):
        d = c[i] - c[i - 1]
        up, dn = max(d, 0), max(-d, 0)
        if i <= n:
            g += up / n; l += dn / n
            if i == n:
                out[i] = 100 - 100 / (1 + g / l) if l else 100
        else:
            g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n
            out[i] = 100 - 100 / (1 + g / l) if l else 100
    return out


def correr(bars, R, pip, level, tp, sl, desde, hasta, temprano=None, trail=None):
    abiertas, res = [], []
    lado, ultima = 0, None
    stop = obj = mejor = None
    for i in range(max(desde, N_RSI + 2), hasta - 1):
        p, q = R[i - 1], R[i]
        s = 1 if p < level <= q else (-1 if p > 100 - level >= q else 0)
        if abiertas:
            _, o, h, l, c, _ = bars[i]
            salida = None
            if (l <= stop) if lado > 0 else (h >= stop):
                salida = stop
            elif (h >= obj) if lado > 0 else (l <= obj):
                salida = obj
            elif temprano is not None and s == -lado and lado * (c - ultima) / pip >= temprano:
                salida = c                                  # opposite signal on a closed candle while in profit
            if salida is not None:
                for e, coste in abiertas:
                    res.append(lado * (salida - e) / pip - coste)
                abiertas = []
                continue
            if trail is not None:
                act, dist = trail
                mejor = max(mejor, h) if lado > 0 else min(mejor, l)
                if lado * (mejor - ultima) / pip >= act:
                    nuevo = mejor - lado * dist * pip
                    stop = max(stop, nuevo) if lado > 0 else min(stop, nuevo)
        if not s or len(abiertas) >= MAXPOS or (abiertas and s != lado):
            continue
        e = bars[i + 1][1]
        abiertas.append((e, bars[i + 1][5] / 10.0))
        lado, ultima, mejor = s, e, e
        obj, stop = e + s * tp * pip, e - s * sl * pip      # tastyfx: the whole stack takes the newest levels
    for e, coste in abiertas:
        res.append(lado * (bars[hasta - 1][4] - e) / pip - coste)
    return res


for par, (pip, usd_lote, level, tp, sl) in PARES.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    usd = usd_lote * LOTES
    casos = [("as now", None, None)]
    casos += [(f"early exit at >= {x} pips", x, None) for x in (10, 15, 20) if x < tp]
    casos += [(f"trailing from {a}, {d} behind", None, (a, d))
              for a, d in itertools.product((10, 15, 20), (5, 10, 15)) if a < tp and d <= a]
    print(f"\n{par.upper()} RSI {level}/{100 - level} TP {tp} SL {sl}: $ per period | total | win%")
    for nombre, x, tr in casos:
        partes = [round(sum(correr(bars, R, pip, level, tp, sl, cortes[k], cortes[k + 1], x, tr)) * usd) for k in range(3)]
        t = correr(bars, R, pip, level, tp, sl, 0, N, x, tr)
        w = 100 * sum(1 for v in t if v > 0) / max(1, len(t))
        print(f"  {nombre:28}: {partes} | {sum(t) * usd:+7.0f} | {w:3.0f}%")

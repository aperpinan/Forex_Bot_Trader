"""Targets in dollars per trade at 0.5 lots ($25, $50, $75, $100) with the stop as a multiple of the target
(1/3 = risk $1 to make $3 ... 3 = risk $3 to make $1, which wins ~3 times out of 4). Same bot rules otherwise:
RSI(7) reversion, up to 3 trades per pair in one direction, real spread, stop counted first if both hit in a candle.

    python objetivo_dolares.py
"""
import itertools
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
LOTES = 0.5
# pair: (pip size, US$ per pip for 1 lot at today's prices, from tastyfx's tick values)
PARES = {"eurusd": (0.0001, 10.0), "usdjpy": (0.01, 6.36), "usdchf": (0.0001, 12.16), "gbpusd": (0.0001, 10.0),
         "audusd": (0.0001, 10.0), "usdcad": (0.0001, 7.16), "nzdusd": (0.0001, 10.0)}
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


def correr(bars, R, pip, level, tp, sl, desde, hasta):
    def salida(i, s):
        e = bars[i + 1][1]
        obj, stop = e + s * tp * pip, e - s * sl * pip
        for j in range(i + 1, hasta):
            _, o, h, l, c, _ = bars[j]
            if (l <= stop) if s > 0 else (h >= stop):
                return j, -sl
            if (h >= obj) if s > 0 else (l <= obj):
                return j, tp
        return hasta - 1, s * (bars[hasta - 1][4] - e) / pip

    abiertas, res = [], []
    for i in range(max(desde, N_RSI + 2), hasta - 1):
        abiertas = [t for t in abiertas if t[0] > i]
        p, q = R[i - 1], R[i]
        s = 1 if p < level <= q else (-1 if p > 100 - level >= q else 0)
        if not s or len(abiertas) >= MAXPOS or any(t[1] != s for t in abiertas):
            continue
        j, pips = salida(i, s)
        res.append(pips - bars[i + 1][5] / 10.0)
        abiertas.append((j + 1, s))
    return res


resumen = []
for par, (pip, usd_lote) in PARES.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    usd_pip = usd_lote * LOTES
    filas = []
    for level, dolares, ratio in itertools.product((20, 25, 30), (25, 50, 75, 100), (1 / 3, 1 / 2, 1, 2, 3)):
        tp = dolares / usd_pip
        sl = tp * ratio
        partes = [sum(correr(bars, R, pip, level, tp, sl, cortes[k], cortes[k + 1])) * usd_pip for k in range(3)]
        t = correr(bars, R, pip, level, tp, sl, 0, N)
        filas.append((sum(t) * usd_pip, level, dolares, ratio, tp, sl, [round(x) for x in partes], len(t),
                      100 * sum(1 for x in t if x > 0) / max(1, len(t))))
    filas.sort(reverse=True)
    buenos = [f for f in filas if min(f[6]) > 0]
    print(f"\n{par.upper()} (0.5 lots = ${usd_pip:.2f}/pip): settings positive in all 3 periods: {len(buenos)} of {len(filas)}")
    for tot, level, dol, ratio, tp, sl, partes, n, w in (buenos or filas)[:4]:
        print(f"  RSI {level}/{100 - level}  win ${dol:>3} ({tp:4.1f} pips) / lose ${dol * ratio:5.0f} ({sl:5.1f} pips): "
              f"periods ${partes} | total ${tot:+8.0f} | {n:4} trades ({n / 26:.0f}/wk) | {w:3.0f}% win")

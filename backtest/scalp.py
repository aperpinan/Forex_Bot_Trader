""""Penny catcher" test: small take-profits, looser RSI levels for more trades. Same bot rules otherwise
(RSI(7) reversion, up to 3 trades per pair in one direction, real spread). If target and stop are both touched in
the same 5-minute candle the stop is counted (we can't see inside the candle), which is pessimistic for tiny targets.

    python scalp.py
"""
import itertools
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
PIPS = {"eurusd": 0.0001, "usdjpy": 0.01, "usdchf": 0.0001, "gbpusd": 0.0001, "audusd": 0.0001,
        "usdcad": 0.0001, "nzdusd": 0.0001}          # USD/MXN left out: its 50+ pip spread rules out small targets
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


for par, pip in PIPS.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    filas = []
    for level, tp, sl in itertools.product((20, 25, 30, 35), (2, 3, 5, 8, 10), (5, 10, 15, 20, 30)):
        partes = [sum(correr(bars, R, pip, level, tp, sl, cortes[k], cortes[k + 1])) for k in range(3)]
        t = correr(bars, R, pip, level, tp, sl, 0, N)
        filas.append((sum(t), level, tp, sl, [round(x) for x in partes], len(t),
                      100 * sum(1 for x in t if x > 0) / max(1, len(t))))
    filas.sort(reverse=True)
    buenos = [f for f in filas if min(f[4]) > 0]
    print(f"\n{par.upper()}: small-target settings positive in all 3 periods: {len(buenos)} of {len(filas)}")
    for tot, level, tp, sl, partes, n, w in (buenos or filas)[:3]:
        print(f"  RSI {level}/{100 - level} TP {tp:>2} SL {sl:>2}: {partes} | {tot:+6.0f} pips | {n:5} trades "
              f"({n / 26:.0f}/week) | {w:3.0f}% win | {tot / max(1, n):+.2f} pips/trade")

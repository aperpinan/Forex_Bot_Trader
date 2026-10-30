"""Bot rules on every pair: RSI(7) reversion 20/80, up to 3 trades open, all in the same direction, real spread paid.
TP / SL tested per pair (USD/MXN moves and costs much more per pip). 6 months split in 3 periods of 2 months.

    python pares.py            (needs data/<pair>_5m_tastyfx.json from bajar_tastyfx.py)
"""
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
PARES = {"eurusd": (0.0001, (10, 15, 20, 30, 40, 50)), "usdchf": (0.0001, (10, 15, 20, 30, 40, 50)),
         "usdjpy": (0.01, (10, 15, 20, 30, 40, 50)), "usdmxn": (0.0001, (150, 200, 300, 400, 600, 800)),
         "usdcad": (0.0001, (10, 15, 20, 30, 40, 50)), "audusd": (0.0001, (10, 15, 20, 30, 40, 50)),
         "nzdusd": (0.0001, (10, 15, 20, 30, 40, 50)), "gbpusd": (0.0001, (10, 15, 20, 30, 40, 50))}
LEVEL, N_RSI, MAXPOS = 20, 7, 3


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


def correr(bars, R, pip, tp, sl, desde, hasta):
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
    eq = pk = dd = 0.0
    for i in range(max(desde, N_RSI + 2), hasta - 1):
        for t in [t for t in abiertas if t[0] <= i]:
            abiertas.remove(t)
            eq += t[1]; pk = max(pk, eq); dd = max(dd, pk - eq)
        p, q = R[i - 1], R[i]
        s = 1 if p < LEVEL <= q else (-1 if p > 100 - LEVEL >= q else 0)
        if not s or len(abiertas) >= MAXPOS or any(t[2] != s for t in abiertas):
            continue
        j, pips = salida(i, s)
        pips -= bars[i + 1][5] / 10.0                    # spread: points -> pips (10 points per pip on all four)
        abiertas.append((j + 1, pips, s))
        res.append(pips)
    for t in abiertas:
        eq += t[1]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return res, dd


for par, (pip, medidas) in PARES.items():
    ruta = os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")
    if not os.path.exists(ruta):
        continue
    bars = json.load(open(ruta))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    sp = sorted(b[5] for b in bars)[N // 2] / 10
    print(f"\n{par.upper()}  {N} candles, median spread {sp:.1f} pips.  TP/SL in pips: periods | total | trades | win% | drawdown")
    filas = []
    for tp in medidas:
        for sl in medidas:
            partes = [round(sum(correr(bars, R, pip, tp, sl, cortes[k], cortes[k + 1])[0])) for k in range(3)]
            t, dd = correr(bars, R, pip, tp, sl, 0, N)
            filas.append((sum(t), tp, sl, partes, len(t), 100 * sum(1 for x in t if x > 0) / max(1, len(t)), dd))
    filas.sort(reverse=True)
    for tot, tp, sl, partes, n, w, dd in filas[:5] + [f for f in filas if (f[1], f[2]) == (30, 30)]:
        marca = "  <- all 3 periods positive" if min(partes) > 0 else ""
        print(f"  TP {tp:>3} SL {sl:>3}: {partes} | {tot:+7.0f} | {n:4} | {w:3.0f}% | {dd:5.0f}{marca}")
    print(f"  settings positive in all 3 periods: {sum(1 for f in filas if min(f[3]) > 0)} of {len(filas)}")

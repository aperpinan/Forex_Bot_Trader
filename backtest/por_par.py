"""Pick each pair's own RSI level, take-profit and stop-loss.

Every trade pays that pair's real tastyfx spread, so pairs with a wider spread end up needing wider targets.
To avoid picking luck out of many combinations, a setting only qualifies if:
  - it makes money in each of the three 2-month periods, and
  - its neighbours (next take-profit / stop-loss up and down, same RSI level) also make money over the 6 months.
Qualified settings are ranked by their WORST period. Same rules as the bot otherwise: RSI(7) reversion, up to 3
trades per pair in one direction, stop counted first if both are touched in one candle.

    python por_par.py
"""
import itertools
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
LOTES = 0.5
NORMAL = (10, 15, 20, 25, 30, 40, 50, 70)
# pair: (pip size, US$ per pip for 1 lot at today's prices, take-profit / stop-loss sizes to try, in pips)
PARES = {"eurusd": (0.0001, 10.0, NORMAL), "usdjpy": (0.01, 6.36, NORMAL), "usdchf": (0.0001, 12.16, NORMAL),
         "gbpusd": (0.0001, 10.0, NORMAL), "audusd": (0.0001, 10.0, NORMAL), "usdcad": (0.0001, 7.16, NORMAL),
         "nzdusd": (0.0001, 10.0, NORMAL), "usdmxn": (0.0001, 0.53, (150, 200, 300, 400, 600, 800, 1000, 1500))}
NIVELES = (20, 25, 30)
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


def caida(t, usd):
    eq = pk = d = 0.0
    for x in t:
        eq += x * usd; pk = max(pk, eq); d = max(d, pk - eq)
    return d


elegidos = {}
for par, (pip, usd_lote, medidas) in PARES.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    usd = usd_lote * LOTES
    sp = sorted(b[5] for b in bars)[N // 2] / 10
    tabla = {}
    for level, tp, sl in itertools.product(NIVELES, medidas, medidas):
        partes = [sum(correr(bars, R, pip, level, tp, sl, cortes[k], cortes[k + 1])) for k in range(3)]
        t = correr(bars, R, pip, level, tp, sl, 0, N)
        tabla[(level, tp, sl)] = (partes, t)

    def vecinos(level, tp, sl):
        i, j = medidas.index(tp), medidas.index(sl)
        for a, b in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if 0 <= a < len(medidas) and 0 <= b < len(medidas):
                yield (level, medidas[a], medidas[b])

    buenos = []
    for k, (partes, t) in tabla.items():
        if min(partes) > 0 and all(sum(tabla[v][1]) > 0 for v in vecinos(*k)):
            buenos.append((min(partes), k))
    buenos.sort(reverse=True)
    print(f"\n{par.upper()}  median spread {sp:.1f} pips, 0.5 lots = ${usd:.2f}/pip. "
          f"Robust settings: {len(buenos)} of {len(tabla)}")
    for _, (level, tp, sl) in buenos[:3]:
        partes, t = tabla[(level, tp, sl)]
        w = 100 * sum(1 for x in t if x > 0) / len(t)
        print(f"  RSI {level}/{100 - level} TP {tp:>4} SL {sl:>4} pips (win ${tp * usd:.0f} / lose ${sl * usd:.0f}): "
              f"periods ${[round(x * usd) for x in partes]} | total ${sum(t) * usd:+.0f} | {len(t) / 26:.0f}/wk | "
              f"{w:.0f}% win | worst drawdown ${caida(t, usd):.0f}")
    if buenos:
        elegidos[par] = buenos[0][1]
    ahora = (20, 300, 300) if par == "usdmxn" else (20, 15, 30) if par == "audusd" else (20, 30, 30)
    partes, t = tabla[ahora]
    print(f"  now: RSI 20/80 TP {ahora[1]} SL {ahora[2]}: periods ${[round(x * usd) for x in partes]} | "
          f"total ${sum(t) * usd:+.0f} | worst drawdown ${caida(t, usd):.0f}")
print("\nchosen:", elegidos)

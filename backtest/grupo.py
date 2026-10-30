"""Group close test: when one trade of a pair hits its take-profit, close the pair's other open trades at that
moment if together they are above zero. Compared with letting each trade run to its own TP / SL.
Same rules as the bot: RSI(7) 20/80, up to 3 trades per pair, all in one direction, real spread.

    python grupo.py     (needs data/<pair>_5m_tastyfx.json)
"""
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
PARES = {"eurusd": (0.0001, 30, 30), "usdjpy": (0.01, 30, 30), "gbpusd": (0.0001, 30, 30), "audusd": (0.0001, 15, 30)}
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


def correr(bars, R, pip, tp, sl, grupo, desde, hasta):
    """Bar by bar. Open trades: dict(entry, side, cost). Returns list of results in pips."""
    abiertas, res = [], []
    eq = pk = dd = 0.0
    for i in range(max(desde, N_RSI + 2), hasta):
        _, o, h, l, c, sp = bars[i]
        # exits on this bar (stop first if both are touched)
        tp_hit = False
        for t in list(abiertas):
            s, e = t["side"], t["entry"]
            stop, obj = e - s * sl * pip, e + s * tp * pip
            if (l <= stop) if s > 0 else (h >= stop):
                r = -sl - t["cost"]
            elif (h >= obj) if s > 0 else (l <= obj):
                r = tp - t["cost"]
                tp_hit = True
            else:
                continue
            abiertas.remove(t); res.append(r); eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
            if tp_hit and grupo and abiertas:
                ganado = r
                flot = [s2 * (c - t2["entry"]) / pip - t2["cost"] for t2 in abiertas for s2 in [t2["side"]]]
                if ganado + sum(flot) > 0:
                    for f in flot:
                        res.append(f); eq += f; pk = max(pk, eq); dd = max(dd, pk - eq)
                    abiertas = []
                    break
        # new signal on this closed bar -> enter at next bar's open
        if i + 1 >= hasta:
            break
        p, q = R[i - 1], R[i]
        s = 1 if p < LEVEL <= q else (-1 if p > 100 - LEVEL >= q else 0)
        if s and len(abiertas) < MAXPOS and all(t["side"] == s for t in abiertas):
            abiertas.append({"entry": bars[i + 1][1], "side": s, "cost": bars[i + 1][5] / 10.0})
    for t in abiertas:
        r = t["side"] * (bars[hasta - 1][4] - t["entry"]) / pip - t["cost"]
        res.append(r); eq += r; pk = max(pk, eq); dd = max(dd, pk - eq)
    return res, dd


for par, (pip, tp, sl) in PARES.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    R = rsi([b[4] for b in bars], N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    print(f"\n{par.upper()} TP {tp} / SL {sl}: periods | total pips | trades | win% | worst drawdown")
    for grupo in (False, True):
        partes = [round(sum(correr(bars, R, pip, tp, sl, grupo, cortes[k], cortes[k + 1])[0])) for k in range(3)]
        t, dd = correr(bars, R, pip, tp, sl, grupo, 0, N)
        w = 100 * sum(1 for x in t if x > 0) / max(1, len(t))
        print(f"  {'group close' if grupo else 'each alone '}: {partes} | {sum(t):+6.0f} | {len(t):4} | {w:3.0f}% | {dd:5.0f}")

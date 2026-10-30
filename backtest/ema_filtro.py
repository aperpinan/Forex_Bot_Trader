"""EMA trend filter on top of the bot's RSI rules: buy dips only above the EMA, sell spikes only below it
("with trend"), or the opposite ("against trend"). Same rules otherwise: RSI(7) 20/80, up to 3 trades per pair,
one direction, real spread, each trade to its own TP / SL. 6 months in 3 periods.

    python ema_filtro.py
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


def ema(c, n):
    k, out, e = 2 / (n + 1), [], c[0]
    for x in c:
        e = x * k + e * (1 - k)
        out.append(e)
    return out


def correr(bars, R, E, modo, pip, tp, sl, desde, hasta):
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
    for i in range(max(desde, 300), hasta - 1):
        for t in [t for t in abiertas if t[0] <= i]:
            abiertas.remove(t)
            eq += t[1]; pk = max(pk, eq); dd = max(dd, pk - eq)
        p, q = R[i - 1], R[i]
        s = 1 if p < LEVEL <= q else (-1 if p > 100 - LEVEL >= q else 0)
        if not s:
            continue
        if E is not None:
            arriba = bars[i][4] > E[i]
            con_tendencia = (s > 0) == arriba
            if (modo == "with" and not con_tendencia) or (modo == "against" and con_tendencia):
                continue
        if len(abiertas) >= MAXPOS or any(t[2] != s for t in abiertas):
            continue
        j, pips = salida(i, s)
        pips -= bars[i + 1][5] / 10.0
        abiertas.append((j + 1, pips, s))
        res.append(pips)
    for t in abiertas:
        eq += t[1]; pk = max(pk, eq); dd = max(dd, pk - eq)
    return res, dd


for par, (pip, tp, sl) in PARES.items():
    bars = json.load(open(os.path.join(AQUI, "..", "data", f"{par}_5m_tastyfx.json")))
    closes = [b[4] for b in bars]
    R = rsi(closes, N_RSI)
    N = len(bars)
    cortes = [0, N // 3, 2 * N // 3, N]
    print(f"\n{par.upper()} TP {tp} / SL {sl}: periods | total pips | trades | win% | worst drawdown")
    casos = [("RSI only (now)", None, None)]
    for n in (50, 200, 600):            # 600 x 5 min = EMA 50 on the hourly chart
        E = ema(closes, n)
        casos += [(f"EMA{n} with trend", E, "with"), (f"EMA{n} against trend", E, "against")]
    for nombre, E, modo in casos:
        partes = [round(sum(correr(bars, R, E, modo, pip, tp, sl, cortes[k], cortes[k + 1])[0])) for k in range(3)]
        t, dd = correr(bars, R, E, modo, pip, tp, sl, 0, N)
        w = 100 * sum(1 for x in t if x > 0) / max(1, len(t))
        marca = "  <- all 3 positive" if min(partes) > 0 else ""
        print(f"  {nombre:20}: {partes} | {sum(t):+6.0f} | {len(t):4} | {w:3.0f}% | {dd:5.0f}{marca}")

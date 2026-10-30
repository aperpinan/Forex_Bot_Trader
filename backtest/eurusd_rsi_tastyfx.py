"""Same RSI test as eurusd_rsi.py, on tastyfx's own MT5 history and paying each candle's real spread.
6 months split into 3 periods of 2 months: a setting is only trusted if it makes money in all three."""
import itertools
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
bars = json.load(open(os.path.join(AQUI, "..", "data", "eurusd_5m_tastyfx.json")))
PIP = 0.0001
closes = [b[4] for b in bars]


def rsi(c, n=14):
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


RSI = {n: rsi(closes, n) for n in (7, 14)}


def senal(modo, r, i, a, extremo):
    p, q = r[i - 1], r[i]
    if p is None or q is None:
        return 0
    if modo == "momentum":
        if p < 50 + a <= q < extremo:
            return 1
        if p > 50 - a >= q > 100 - extremo:
            return -1
    else:
        if p < a <= q:
            return 1
        if p > 100 - a >= q:
            return -1
    return 0


def correr(modo, n, a, extremo, tp, sl, desde, hasta):
    """Prices are bid; spread (points) of the entry candle is paid once. Stop first if both are hit in one candle."""
    r = RSI[n]
    trades = []
    i = max(desde, n + 2)
    while i < hasta - 1:
        s = senal(modo, r, i, a, extremo)
        if not s:
            i += 1
            continue
        e = bars[i + 1][1]
        coste = bars[i + 1][5] / 10.0                # points -> pips
        obj, stop = e + s * tp * PIP, e - s * sl * PIP
        j, res = i + 1, None
        while j < hasta:
            _, o, h, l, c, _sp = bars[j]
            if (l <= stop) if s > 0 else (h >= stop):
                res = -sl; break
            if (h >= obj) if s > 0 else (l <= obj):
                res = tp; break
            j += 1
        if res is None:
            res = s * (bars[hasta - 1][4] - e) / PIP
        trades.append(res - coste)
        i = j + 1
    return trades


def stats(t):
    if not t:
        return {"trades": 0, "win%": 0, "pips": 0, "avg_win": 0, "avg_loss": 0, "max_dd_pips": 0}
    eq = pk = dd = 0.0
    for x in t:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    g = [x for x in t if x > 0]
    return {"trades": len(t), "win%": round(100 * len(g) / len(t), 1), "pips": round(sum(t), 1),
            "avg_win": round(sum(g) / len(g), 1) if g else 0,
            "avg_loss": round(sum(x for x in t if x <= 0) / max(1, len(t) - len(g)), 1), "max_dd_pips": round(dd, 1)}


N = len(bars)
cortes = [0, N // 3, 2 * N // 3, N]
res = []
for modo, n, tp, sl in itertools.product(("momentum", "reversion"), (7, 14), (5, 10, 15, 20, 30), (5, 10, 15, 20, 30)):
    for a, ext in ((5, 80), (10, 80), (15, 85)) if modo == "momentum" else ((20, 0), (25, 0), (30, 0)):
        k = (modo, n, a, ext, tp, sl)
        partes = [stats(correr(*k, cortes[x], cortes[x + 1]))["pips"] for x in range(3)]
        res.append((k, partes, stats(correr(*k, 0, N))))
res.sort(key=lambda x: -x[2]["pips"])
print(f"{N} tastyfx candles (6 months), real spread per trade. 3 periods of ~2 months.\n")
print("TOP 10 over 6 months (pips per period | total):")
for k, p, s in res[:10]:
    print(f"  {k[0]:9} RSI{k[1]:<2} level {k[2]:<2} TP {k[4]:>2} SL {k[5]:>2} | {p[0]:>7} {p[1]:>7} {p[2]:>7} | {s['pips']:>7} "
          f"({s['trades']} tr, {s['win%']}% win, dd {s['max_dd_pips']})")
print(f"\nProfitable over 6 months: {sum(1 for _, _, s in res if s['pips'] > 0)} of {len(res)}")
print(f"Profitable in ALL three periods: {sum(1 for _, p, _ in res if min(p) > 0)} of {len(res)}")
for k, p, s in res:
    if k == ("reversion", 14, 30, 0, 30, 5):
        print(f"\nOur chosen setting (reversion RSI14 30/70, TP 30 SL 5): periods {p}, total {s}")
json.dump([(k, p, s) for k, p, s in res], open(os.path.join(AQUI, "..", "data", "rsi_tastyfx_out.json"), "w"))

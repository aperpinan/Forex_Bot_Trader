"""EUR/USD 5-min RSI backtest: one position at a time, exit only at take-profit or stop-loss.
Entry at the next bar's open after the signal; if TP and SL both fall inside one bar, it counts the STOP (conservative).
Cost = spread in pips paid once per trade. First half of the data picks the settings, second half checks them."""
import json, itertools, os
AQUI = os.path.dirname(os.path.abspath(__file__))

bars = json.load(open(os.path.join(AQUI, "..", "data", "eurusd_5m.json")))
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
    if modo == "momentum":                 # pushes past 50±a, but not already overextended
        if p < 50 + a <= q < extremo:
            return 1
        if p > 50 - a >= q > 100 - extremo:
            return -1
    else:                                  # mean reversion: comes back from oversold / overbought
        if p < a <= q:
            return 1
        if p > 100 - a >= q:
            return -1
    return 0


def correr(modo, n, a, extremo, tp, sl, spread, desde, hasta):
    r = RSI[n]
    trades = []
    i = max(desde, n + 2)
    while i < hasta - 1:
        s = senal(modo, r, i, a, extremo)
        if not s:
            i += 1
            continue
        e = bars[i + 1][1]
        obj, stop = e + s * tp * PIP, e - s * sl * PIP
        j = i + 1
        res = None
        while j < hasta:
            _, o, h, l, c = bars[j]
            golpe_sl = l <= stop if s > 0 else h >= stop
            golpe_tp = h >= obj if s > 0 else l <= obj
            if golpe_sl:
                res = -sl; break
            if golpe_tp:
                res = tp; break
            j += 1
        if res is None:                    # data ran out: close at last price
            res = s * (bars[hasta - 1][4] - e) / PIP
        trades.append(res - spread)
        i = j + 1
    return trades


def stats(t):
    if not t:
        return None
    eq = pk = dd = 0.0
    for x in t:
        eq += x; pk = max(pk, eq); dd = max(dd, pk - eq)
    g = [x for x in t if x > 0]
    return {"trades": len(t), "win%": round(100 * len(g) / len(t), 1), "pips": round(sum(t), 1),
            "avg_win": round(sum(g) / len(g), 1) if g else 0,
            "avg_loss": round(sum(x for x in t if x <= 0) / max(1, len(t) - len(g)), 1),
            "max_dd_pips": round(dd, 1)}


N = len(bars)
MID = N // 2
SPREAD = 1.0
grid = []
for modo, n, tp, sl in itertools.product(("momentum", "reversion"), (7, 14), (5, 10, 15, 20, 30), (5, 10, 15, 20, 30)):
    for a, ext in ((5, 80), (10, 80), (15, 85)) if modo == "momentum" else ((20, 0), (25, 0), (30, 0)):
        ins = stats(correr(modo, n, a, ext, tp, sl, SPREAD, 0, MID))
        if ins and ins["trades"] >= 30:
            grid.append(((modo, n, a, ext, tp, sl), ins))
grid.sort(key=lambda x: -x[1]["pips"])
print(f"{N} bars; first half picks, second half checks. Spread {SPREAD} pip per trade.\n")
print("TOP 8 on first half -> same settings on second half (out of sample):")
for k, ins in grid[:8]:
    out = stats(correr(*k, SPREAD, MID, N))
    print(f"  {k[0]:9} RSI{k[1]:<2} level {k[2]:<2} TP {k[4]:>2} SL {k[5]:>2} | first half {ins['pips']:>7} pips "
          f"({ins['trades']} tr, {ins['win%']}% win) | second half {out['pips']:>7} pips ({out['trades']} tr, {out['win%']}% win, "
          f"avg +{out['avg_win']}/{out['avg_loss']}, max dd {out['max_dd_pips']})")
pos = sum(1 for _, s in grid if s["pips"] > 0)
print(f"\nSettings with profit on first half: {pos} of {len(grid)}")
full = [(k, stats(correr(*k, SPREAD, 0, N))) for k, _ in grid]
print("Settings with profit over all 60 days:", sum(1 for _, s in full if s['pips'] > 0), "of", len(full))
# a simple, 'natural' version of each family over the whole period, with costs 0 / 0.8 / 1.0 / 1.5
for k in (("momentum", 14, 10, 80, 10, 10), ("reversion", 14, 30, 0, 10, 10), ("momentum", 14, 10, 80, 20, 10)):
    print("\nWhole period", k[0], f"RSI{k[1]} level {k[2]} TP {k[4]} SL {k[5]}:")
    for sp in (0.0, 0.8, 1.0, 1.5):
        print(f"   spread {sp}: {stats(correr(*k, sp, 0, N))}")
json.dump({"top": [(k, s) for k, s in grid[:8]]}, open(os.path.join(AQUI, "..", "data", "eurusd_rsi_out.json"), "w"))

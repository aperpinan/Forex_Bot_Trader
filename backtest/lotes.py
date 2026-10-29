import runpy, io, contextlib, os
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eurusd_rsi.py"))
correr, stats, N = g["correr"], g["stats"], g["N"]
LOTES = (("micro 1,000", 0.10), ("mini 10,000", 1.0), ("standard 100,000", 10.0))
MARGEN = {"micro 1,000": 22, "mini 10,000": 224, "standard 100,000": 2235}   # US 50:1 on EUR/USD at ~1.117
for nombre, k in (("Best-looking (reversion RSI14, TP 30 / SL 5)", ("reversion", 14, 30, 0, 30, 5)),
                  ("Simple momentum like Pista (RSI14 past 60, TP 20 / SL 10)", ("momentum", 14, 10, 80, 20, 10)),
                  ("Simple reversion (RSI14 back from 30/70, TP 10 / SL 10)", ("reversion", 14, 30, 0, 10, 10))):
    s = stats(correr(*k, 1.0, 0, N))
    print(f"{nombre}: {s['trades']} trades in 60 days, {s['win%']}% win, {s['pips']:+} pips, worst drawdown {s['max_dd_pips']} pips")
    for lote, usd in LOTES:
        print(f"   {lote:>17}: total {s['pips'] * usd:+9.2f} $ | avg win {s['avg_win'] * usd:+7.2f} $, avg loss {s['avg_loss'] * usd:+7.2f} $ | "
              f"worst drawdown -{s['max_dd_pips'] * usd:.2f} $ | margin {MARGEN[lote]} $")

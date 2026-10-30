"""Connection test: account, EUR/USD contract details, live price and the last 5-minute candles. Places NO orders."""
import datetime as dt

from mt5_conexion import conectar

mt5 = conectar()
try:
    a = mt5.account_info()
    print(f"Account {a.login} on {a.server} ({'DEMO' if a.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else 'REAL'}): "
          f"balance {a.balance:,.2f} {a.currency}, leverage 1:{a.leverage}, trading allowed: {a.trade_allowed}, "
          f"algo trading on in terminal: {mt5.terminal_info().trade_allowed}")
    nombres = [s.name for s in mt5.symbols_get() or []]
    eur = next((n for n in nombres if n.replace("/", "").replace(".", "").upper().startswith("EURUSD")), None)
    print(f"{len(nombres)} symbols. EUR/USD symbol: {eur}")
    mt5.symbol_select(eur, True)
    s = mt5.symbol_info(eur)
    print(f"  contract {s.trade_contract_size:,.0f}, min lot {s.volume_min}, lot step {s.volume_step}, max lot {s.volume_max}, "
          f"digits {s.digits}, stops level {s.trade_stops_level} points, filling {s.filling_mode}")
    t = mt5.symbol_info_tick(eur)
    print(f"  now: bid {t.bid}  ask {t.ask}  spread {(t.ask - t.bid) * 10000:.1f} pips")
    velas = mt5.copy_rates_from_pos(eur, mt5.TIMEFRAME_M5, 0, 5)
    for v in velas:
        print(f"  {dt.datetime.fromtimestamp(int(v['time']), dt.timezone.utc):%m-%d %H:%M} UTC  "
              f"O {v['open']} H {v['high']} L {v['low']} C {v['close']}  spread {v['spread']} points")
    hist = mt5.copy_rates_from_pos(eur, mt5.TIMEFRAME_M5, 0, 100000)
    print(f"  5-minute history available: {len(hist)} candles, from "
          f"{dt.datetime.fromtimestamp(int(hist[0]['time']), dt.timezone.utc):%Y-%m-%d}")
finally:
    mt5.shutdown()

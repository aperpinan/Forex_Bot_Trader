# Forex_Bot_Trader — context for Claude

Owner: aperpinan (GitHub https://github.com/aperpinan/Forex_Bot_Trader, public repo). Writes in Spanish or English:
answer in the language of their last message.

## What it is
RSI bot for EUR/USD 5-minute candles on **tastyfx** (IG US), through the **tastyfx MetaTrader 5** desktop terminal on
this Windows PC and the official `MetaTrader5` Python package (`.venv`). tastyfx's old WebSocket API no longer exists.

- Terminal: `C:\Program Files\tastyfx MetaTrader 5\terminal64.exe`. Demo account on server tastyfx-DEMO
  (login in `.env`, never committed). Symbol `EURUSD.FX`: min 0.01 lot, FOK filling, ~0.8 pip spread, stops >= 2 pips.
- Strategy (`config.json`): RSI(7) mean reversion: buy when RSI comes back up through 20, sell back down through 80;
  TP 30 / SL 30 pips attached to the order; 0.5 lots (was 0.01 until 2026-10-30); up to 3 trades open
  (`max_open_positions`, was 1), ALWAYS all in the same direction: a signal the other way is skipped (owner's rule);
  magic 202610, comment "RSI bot".
- PAIRS (since 2026-10-30): `config.json` "pairs" lists EURUSD.FX, USDJPY.FX, USDCHF.FX, USDMXN.FX; top-level strategy /
  lots / max_open_positions are defaults, each pair can override them. Rule per pair: up to 3 trades, all one direction;
  different pairs are independent. Pip = 0.01 on JPY, 0.0001 on the others (`pip_de`). tastyfx has no CHF/USD, only USD/CHF.
- Backtest per pair (`backtest/pares.py`, same rules, 6 months): USD/JPY TP/SL 30 = +1298 pips, positive in all 3 periods
  (19/36 TP/SL settings were); USD/CHF: no setting positive in all 3 periods (30/30 = -147); USD/MXN loses with every
  setting (spread ~50-90 pips, tastyfx min stop 150 pips). Owner chose: CHF and MXN trade at 0.01 lots only to collect
  data; MXN uses TP/SL 300 pips. EUR/USD and USD/JPY at 0.5 lots.
- Added the same day: GBP/USD (30/30 = +694, periods 302/-31/341) at 0.5 lots; AUD/USD at 0.5 lots with TP 15 / SL 30
  (+1039, all 3 periods positive; 30/30 was only +17); USD/CAD and NZD/USD lose with every setting -> 0.01 lots, data only.
  Rule used: passes the backtest -> 0.5 lots, fails -> 0.01 lots. tastyfx has NO gold, oil, indices or crypto
  (65 symbols, all "Spot FX (USA)").
- Stacking backtest (2026-10-30, 20/80, TP/SL 30): max 1 = +750 pips / 155 trades / dd 189; max 2 = +1456 / 271 / dd 311;
  max 3 = +1499 / 355 / dd 412; max 5 = +1637 / 458 / dd 589, all positive in all 3 periods. Looser levels (25/75,
  30/70) with stacking lose money: to get more trades, stack, don't loosen the levels.
- Data for tuning: `trades` also keeps spread_pips, atr_pips, hour_utc, stack (1st/2nd/3rd of the stack),
  mfe_pips / mae_pips (best / worst the trade got while open), minutes. Table `signals` keeps EVERY signal, taken or
  skipped, with the reason (paused, other direction open, limit reached, Algo Trading off, rejected).
- The bot never moves SL/TP after opening; manual drags and manual closes by the owner are kept and recorded.
  It refuses a real-money account unless `config.json` has `"allow_real_money": true`.

## Running
- `INICIAR_BOT.bat` starts `bot.py` with pythonw in the background (single copy: lock on port 48911).
  `PARAR_BOT.bat` stops it. `STOP.txt` = no new trades. Not auto-started after reboot.
- `bot.log` (all activity, "alive" summary every 10 min) and `trades.db` (table `trades`, close_reason) are the
  places to look when asked how it is doing.
- `INICIAR_PANEL.bat` starts `panel.py` (+ `panel.html`): web panel on http://localhost:8080, bound to 127.0.0.1, buttons need
  a per-run token. Shows account, open trade, RSI, history, log; pause/resume (STOP.txt), edit config.json, close the
  bot's trade, start/stop/restart the bot.
- Desktop folder "Forex Bot Trader" has shortcuts for the owner. MT5 must stay open with Algo Trading on.

## Backtests (`backtest/`)
- `bajar_tastyfx.py` downloads ~6 months of tastyfx 5-min candles with real spread; `eurusd_rsi_tastyfx.py` tests
  300 settings over 3 two-month periods. Chosen setting: +750 pips, 155 trades, 60% wins, worst drawdown 189 pips
  (May 3 - Oct 30, 2026); only 15/300 settings were positive in all three periods.
- A spread filter (skip if spread > 1.5-3 pips) lowered the result (750 -> ~688), so it is not used.
- The first pick from Yahoo data (RSI14, TP 30 / SL 5) lost on tastyfx data: don't go back to it.

## History
Started 2026-10-29. Test trade #4919685 (0.01 lot, -0.07 $ = spread) was made by hand through the bot's code to
check the order cycle; it is not in `trades.db`.

Planned next: small MQL5 indicator to draw the bot's signals on the chart; compare live demo results with the
backtest after a few weeks before any real money.

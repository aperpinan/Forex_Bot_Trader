# Forex_Bot_Trader — context for Claude

Owner: aperpinan (GitHub https://github.com/aperpinan/Forex_Bot_Trader, public repo). Writes in Spanish or English:
answer in the language of their last message.

## What it is
RSI bot for EUR/USD 5-minute candles on **tastyfx** (IG US), through the **tastyfx MetaTrader 5** desktop terminal on
this Windows PC and the official `MetaTrader5` Python package (`.venv`). tastyfx's old WebSocket API no longer exists.

- Terminal: `C:\Program Files\tastyfx MetaTrader 5\terminal64.exe`. Demo account on server tastyfx-DEMO
  (login in `.env`, never committed). Symbol `EURUSD.FX`: min 0.01 lot, FOK filling, ~0.8 pip spread, stops >= 2 pips.
- Strategy (`config.json`): RSI(7) mean reversion: buy when RSI comes back up through 20, sell back down through 80;
  TP 30 / SL 30 pips attached to the order; 0.01 lots; one trade at a time; magic 202610, comment "RSI bot".
- The bot never moves SL/TP after opening; manual drags and manual closes by the owner are kept and recorded.
  It refuses a real-money account unless `config.json` has `"allow_real_money": true`.

## Running
- `INICIAR_BOT.bat` starts `bot.py` with pythonw in the background (single copy: lock on port 48911).
  `PARAR_BOT.bat` stops it. `STOP.txt` = no new trades. Not auto-started after reboot.
- `bot.log` (all activity, "alive" summary every 10 min) and `trades.db` (table `trades`, close_reason) are the
  places to look when asked how it is doing.
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

# Forex_Bot_Trader

RSI bot for EUR/USD on 5-minute candles, traded on tastyfx (IG US) through MetaTrader 5 and its Python package.
**Demo account only until the forward test shows it works.**

## Strategy (current settings in `config.json`)
- RSI(7) on 5-minute closes.
- Mean reversion: buy when RSI comes back up through 20, sell when it comes back down through 80.
- Each trade exits only at its take-profit (30 pips) or stop-loss (30 pips). One position at a time.
- Size: `lots` in standard lots (1 lot = 100,000 EUR; 0.01 = 1,000 = about $0.10 per pip).

## Backtest (`backtest/`)
- `bajar_eurusd.py`: downloads the last 60 days of EUR/USD 5-minute bars into `data/`.
- `eurusd_rsi.py`: tests 257 RSI / take-profit / stop-loss combinations (first half picks, second half checks).
- `lotes.py`: shows the results in dollars for micro, mini and standard lots.
- `bajar_tastyfx.py`: downloads 6 months of EUR/USD 5-minute candles from the tastyfx MT5 terminal, with real spreads.
- `eurusd_rsi_tastyfx.py`: the same test on that data, paying each candle's spread, split into 3 periods of 2 months.

Result on tastyfx data, May 3 - Oct 30, 2026: the settings above made +750 pips (155 trades, 60% wins,
worst drawdown 189 pips) and were positive in all three periods (+322 / +159 / +132).
Only 15 of 300 settings were positive in all three. The first pick from Yahoo's 60 days (RSI14, TP 30 / SL 5)
lost 46 pips over the 6 months.

## tastyfx connection: MetaTrader 5
tastyfx's old WebSocket API is gone (its servers no longer resolve and its help page is 404, checked 2026-10-29).
The bot talks to the MetaTrader 5 desktop terminal on this PC with the official `MetaTrader5` Python package:
- Server: `tastyfx-Demo` (practice) / `tastyfx-LIVE` (real money).
- In MT5, Tools > Options > Expert Advisors: allow algorithmic trading.

## Credentials
Put them in `.env` (never committed; see `.gitignore`):
```
MT5_LOGIN=...
MT5_PASSWORD=...
MT5_SERVER=tastyfx-Demo
```

## Running the bot
- `INICIAR_BOT.bat`: starts `bot.py` in the background (MT5 must be installed; it opens it if closed).
- `PARAR_BOT.bat`: stops it. Open trades keep their stop-loss and take-profit on tastyfx's server.
- `STOP.txt` in this folder: the bot keeps running and recording, but opens no new trades.
- `bot.log`: everything it does. `trades.db`: every trade with how it closed (take-profit, stop-loss, or by you).
- The bot refuses to run on a real-money account unless `config.json` has `"allow_real_money": true`.

On the MT5 chart its trades are labeled `RSI bot` (magic number 202610). You can drag their stop / target or close
them by hand: the bot keeps your change and records it. It never touches trades you open yourself.

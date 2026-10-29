# Forex_Bot_Trader

RSI bot for EUR/USD on 5-minute candles, traded on tastyfx (IG US) through MetaTrader 5 and its Python package.
**Demo account only until the forward test shows it works.**

## Strategy (current settings in `config.json`)
- RSI(14) on 5-minute closes.
- Mean reversion: buy when RSI comes back up through 30, sell when it comes back down through 70.
- Each trade exits only at its take-profit (30 pips) or stop-loss (5 pips). One position at a time.
- Size: `lots` in standard lots (1 lot = 100,000 EUR; 0.01 = 1,000 = about $0.10 per pip).

## Backtest (`backtest/`)
- `bajar_eurusd.py`: downloads the last 60 days of EUR/USD 5-minute bars into `data/`.
- `eurusd_rsi.py`: tests 257 RSI / take-profit / stop-loss combinations (first half picks, second half checks).
- `lotes.py`: shows the results in dollars for micro, mini and standard lots.

Result on Aug 6 - Oct 29, 2026, with 1 pip of spread per trade: the settings above made +249 pips
(221 trades, 20% wins, worst drawdown 144 pips). Most other settings lost money.

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

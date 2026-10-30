"""RSI bot for EUR/USD on tastyfx MT5 (demo first).

Every closed 5-minute candle: RSI on the closes. Mean reversion: RSI back up through `level` -> buy, back down through
100 - `level` -> sell. The stop-loss and take-profit go WITH the order, so they live on tastyfx's server.
Up to max_open_positions trades at once, always all in the same direction: a signal the other way is skipped.
Only its own trades (magic number) are touched. It never moves a stop or target after opening: if you drag them on
the chart or close the trade by hand, it keeps your change and writes it down.

Stop it opening new trades: create a file STOP.txt in this folder (open trades keep their stop / target).
"""
import datetime as dt
import json
import os
import sqlite3
import sys
import time

from mt5_conexion import conectar

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")
LOG = os.path.join(AQUI, "bot.log")
DB = os.path.join(AQUI, "trades.db")
PARAR = os.path.join(AQUI, "STOP.txt")
PIP = 0.0001
CADA_S = 2.0
AVISO_CADA_S = 600


def log(msg):
    linea = f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(linea, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def rsi(closes, n):
    """Wilder RSI, same formula as the backtest. Returns the list (None while warming up)."""
    out = [None] * len(closes)
    g = l = 0.0
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        up, dn = max(d, 0.0), max(-d, 0.0)
        if i <= n:
            g += up / n
            l += dn / n
            if i == n:
                out[i] = 100 - 100 / (1 + g / l) if l else 100.0
        else:
            g = (g * (n - 1) + up) / n
            l = (l * (n - 1) + dn) / n
            out[i] = 100 - 100 / (1 + g / l) if l else 100.0
    return out


def senal(prev, ahora, level):
    if prev is None or ahora is None:
        return 0
    if prev < level <= ahora:
        return 1                 # back up out of oversold -> buy
    if prev > 100 - level >= ahora:
        return -1                # back down out of overbought -> sell
    return 0


def atr_pips(r, n=14):
    """Average true range of the last n closed candles, in pips (how much the market is moving)."""
    tr = [max(float(r[i]["high"]) - float(r[i]["low"]), abs(float(r[i]["high"]) - float(r[i - 1]["close"])),
              abs(float(r[i]["low"]) - float(r[i - 1]["close"]))) for i in range(len(r) - n, len(r))]
    return sum(tr) / n / PIP


# Extra facts kept per trade so the settings can later be tuned on real results:
# market state at entry, and how far the price went for (mfe) and against (mae) the trade while it was open.
COLUMNAS_NUEVAS = {"spread_pips": "REAL", "atr_pips": "REAL", "hour_utc": "INTEGER", "stack": "INTEGER",
                   "mfe_pips": "REAL", "mae_pips": "REAL", "minutes": "REAL"}


def abrir_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS trades (
        ticket INTEGER PRIMARY KEY, symbol TEXT, side TEXT, lots REAL, open_time TEXT, open_price REAL,
        sl REAL, tp REAL, rsi_prev REAL, rsi_now REAL, candle TEXT, status TEXT,
        close_time TEXT, close_price REAL, close_reason TEXT, profit REAL, pips REAL, note TEXT)""")
    hay = {x[1] for x in con.execute("PRAGMA table_info(trades)")}
    for col, tipo in COLUMNAS_NUEVAS.items():
        if col not in hay:
            con.execute(f"ALTER TABLE trades ADD COLUMN {col} {tipo}")
    # every signal, taken or not, with the reason: shows what was missed and why
    con.execute("""CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, candle TEXT, side TEXT, rsi_prev REAL, rsi_now REAL,
        close REAL, spread_pips REAL, atr_pips REAL, hour_utc INTEGER, open_same INTEGER, open_other INTEGER,
        action TEXT, ticket INTEGER)""")
    con.commit()
    return con


class Bot:
    def __init__(self):
        self.cfg = json.load(open(CONFIG, encoding="utf-8"))
        self.sym = self.cfg["symbol"]
        self.st = self.cfg["strategy"]
        self.magic = int(self.cfg["magic"])
        self.mt5 = conectar()
        self.db = abrir_db()
        self.ultima_vela = None
        self.ult_aviso = 0.0
        self.ult_algo_off = 0.0
        if not self.mt5.symbol_select(self.sym, True):
            raise RuntimeError(f"symbol {self.sym} not available")
        a = self.mt5.account_info()
        modo = "DEMO" if a.trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO else "REAL MONEY"
        log(f"START: account {a.login} on {a.server} ({modo}), balance {a.balance:,.2f} {a.currency}. "
            f"{self.sym} RSI{self.st['rsi_period']} {self.st['mode']} {self.st['rsi_level']}/{100 - self.st['rsi_level']}, "
            f"TP {self.st['take_profit_pips']} / SL {self.st['stop_loss_pips']} pips, {self.cfg['lots']} lots.")
        if modo != "DEMO" and not self.cfg.get("allow_real_money"):
            raise RuntimeError("this is a REAL MONEY account and config.json does not have allow_real_money: true")

    # ------------------------------------------------------------------ positions
    def mias(self):
        return [p for p in (self.mt5.positions_get(symbol=self.sym) or []) if p.magic == self.magic]

    def revisar_abiertas(self):
        """Trades in the db still 'open': note manual SL/TP moves, and record how each one closed."""
        vivas = {p.ticket: p for p in self.mias()}
        for (ticket, side, sl, tp, open_price, note, mfe, mae) in self.db.execute(
                "SELECT ticket, side, sl, tp, open_price, note, mfe_pips, mae_pips FROM trades WHERE status='open'").fetchall():
            p = vivas.get(ticket)
            if p is not None:
                ahora = (p.price_current - open_price) / PIP * (1 if side == "buy" else -1)
                if mfe is None or ahora > mfe + 0.05 or mae is None or ahora < mae - 0.05:
                    self.db.execute("UPDATE trades SET mfe_pips=?, mae_pips=? WHERE ticket=?",
                                    (round(max(ahora, mfe if mfe is not None else ahora), 1),
                                     round(min(ahora, mae if mae is not None else ahora), 1), ticket))
                    self.db.commit()
                if (abs(p.sl - sl) > 1e-6 or abs(p.tp - tp) > 1e-6):
                    nota = f"you moved SL {sl:.5f}->{p.sl:.5f}, TP {tp:.5f}->{p.tp:.5f}"
                    log(f"#{ticket} {nota} (the bot keeps your levels)")
                    self.db.execute("UPDATE trades SET sl=?, tp=?, note=? WHERE ticket=?",
                                    (p.sl, p.tp, ((note + "; ") if note else "") + nota, ticket))
                    self.db.commit()
                continue
            self.cerrada(ticket, side, open_price)

    def cerrada(self, ticket, side, open_price):
        deals = self.mt5.history_deals_get(position=ticket) or []
        salida = [d for d in deals if d.entry in (self.mt5.DEAL_ENTRY_OUT, self.mt5.DEAL_ENTRY_OUT_BY)]
        if not salida:
            self.mt5.history_select(dt.datetime.now() - dt.timedelta(days=7), dt.datetime.now() + dt.timedelta(days=1))
            deals = self.mt5.history_deals_get(position=ticket) or []
            salida = [d for d in deals if d.entry in (self.mt5.DEAL_ENTRY_OUT, self.mt5.DEAL_ENTRY_OUT_BY)]
            if not salida:
                return                       # history not there yet: try again next loop
        d = salida[-1]
        razones = {self.mt5.DEAL_REASON_SL: "stop-loss", self.mt5.DEAL_REASON_TP: "take-profit",
                   self.mt5.DEAL_REASON_CLIENT: "closed by you (PC)", self.mt5.DEAL_REASON_MOBILE: "closed by you (phone)",
                   self.mt5.DEAL_REASON_WEB: "closed by you (web)", self.mt5.DEAL_REASON_EXPERT: "closed by a program",
                   self.mt5.DEAL_REASON_SO: "stop-out (margin)"}
        razon = razones.get(d.reason, f"reason {d.reason}")
        if d.reason == self.mt5.DEAL_REASON_EXPERT and "panel" in (d.comment or ""):
            razon = "closed by you (panel)"
        profit = sum(x.profit + x.commission + x.swap + x.fee for x in deals)
        pips = (d.price - open_price) / PIP * (1 if side == "buy" else -1)
        entrada = next((x for x in deals if x.entry == self.mt5.DEAL_ENTRY_IN), None)
        minutos = round((d.time - entrada.time) / 60, 1) if entrada else None
        self.db.execute("UPDATE trades SET status='closed', close_time=?, close_price=?, close_reason=?, profit=?, pips=?, "
                        "minutes=?, mfe_pips=MAX(COALESCE(mfe_pips, ?), ?), mae_pips=MIN(COALESCE(mae_pips, ?), ?) "
                        "WHERE ticket=?", (dt.datetime.fromtimestamp(d.time).isoformat(" "), d.price, razon, profit, pips,
                                           minutos, pips, pips, pips, pips, ticket))
        self.db.commit()
        log(f"#{ticket} CLOSED ({razon}) at {d.price:.5f}: {pips:+.1f} pips, {profit:+.2f} $")

    # ------------------------------------------------------------------ signal and order
    def nueva_vela(self):
        """True once per closed 5-minute candle."""
        r = self.mt5.copy_rates_from_pos(self.sym, self.mt5.TIMEFRAME_M5, 1, 1)
        if r is None or not len(r):
            return False
        t = int(r[0]["time"])
        if t == self.ultima_vela:
            return False
        primera = self.ultima_vela is None
        self.ultima_vela = t
        return not primera                   # on start-up just remember the candle, don't trade a stale signal

    def mirar_senal(self):
        n = int(self.st["rsi_period"])
        r = self.mt5.copy_rates_from_pos(self.sym, self.mt5.TIMEFRAME_M5, 1, 600)      # closed candles only
        if r is None or len(r) < n + 2:
            log("not enough candles for RSI")
            return
        closes = [float(x["close"]) for x in r]
        valores = rsi(closes, n)
        prev, ahora = valores[-2], valores[-1]
        s = senal(prev, ahora, float(self.st["rsi_level"]))
        t_vela = dt.datetime.fromtimestamp(int(r[-1]["time"]), dt.timezone.utc)
        vela = t_vela.strftime("%m-%d %H:%M UTC")
        if not s:
            return
        lado = "BUY" if s > 0 else "SELL"
        tick = self.mt5.symbol_info_tick(self.sym)
        abiertas = self.mias()
        tipo = self.mt5.POSITION_TYPE_BUY if s > 0 else self.mt5.POSITION_TYPE_SELL
        mismo = sum(1 for p in abiertas if p.type == tipo)
        hechos = {"candle": vela, "side": lado.lower(), "rsi_prev": prev, "rsi_now": ahora, "close": closes[-1],
                  "spread_pips": round((tick.ask - tick.bid) / PIP, 1) if tick else None,
                  "atr_pips": round(atr_pips(r), 1), "hour_utc": t_vela.hour,
                  "open_same": mismo, "open_other": len(abiertas) - mismo}
        texto = f"signal {lado} (RSI {prev:.1f} -> {ahora:.1f}, candle {vela})"
        maximo = int(self.cfg.get("max_open_positions", 1))
        if os.path.exists(PARAR):
            motivo = "skipped: paused (STOP.txt)"
        elif len(abiertas) - mismo:
            motivo = f"skipped: {len(abiertas) - mismo} trade(s) open the other way (only one direction at a time)"
        elif mismo >= maximo:
            motivo = f"skipped: already {mismo} trade(s) open, the limit is {maximo}"
        elif not self.mt5.terminal_info().trade_allowed:
            motivo = "skipped: Algo Trading is OFF in MT5 (click the Algo Trading button)"
        else:
            ticket = self.abrir(s, prev, ahora, vela, hechos)
            self.anotar_senal(hechos, f"opened #{ticket}" if ticket else "rejected by tastyfx", ticket)
            return
        log(f"{texto} {motivo}")
        self.anotar_senal(hechos, motivo, None)

    def anotar_senal(self, h, accion, ticket):
        self.db.execute("INSERT INTO signals (time, candle, side, rsi_prev, rsi_now, close, spread_pips, atr_pips, hour_utc, "
                        "open_same, open_other, action, ticket) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (dt.datetime.now().isoformat(" ", "seconds"), h["candle"], h["side"], h["rsi_prev"], h["rsi_now"],
                         h["close"], h["spread_pips"], h["atr_pips"], h["hour_utc"], h["open_same"], h["open_other"],
                         accion, ticket))
        self.db.commit()

    def abrir(self, s, prev, ahora, vela, hechos):
        mt5 = self.mt5
        tick = mt5.symbol_info_tick(self.sym)
        info = mt5.symbol_info(self.sym)
        precio = tick.ask if s > 0 else tick.bid
        tp_d = float(self.st["take_profit_pips"]) * PIP
        sl_d = float(self.st["stop_loss_pips"]) * PIP
        sl = round(precio - s * sl_d, info.digits)
        tp = round(precio + s * tp_d, info.digits)
        llenado = mt5.ORDER_FILLING_FOK if info.filling_mode & 1 else mt5.ORDER_FILLING_IOC
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": self.sym, "volume": float(self.cfg["lots"]),
               "type": mt5.ORDER_TYPE_BUY if s > 0 else mt5.ORDER_TYPE_SELL, "price": precio, "sl": sl, "tp": tp,
               "deviation": 10, "magic": self.magic, "comment": self.cfg.get("comment", "RSI bot"),
               "type_time": mt5.ORDER_TIME_GTC, "type_filling": llenado}
        lado = "buy" if s > 0 else "sell"
        res = mt5.order_send(req)
        if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
            log(f"{lado.upper()} REJECTED (RSI {prev:.1f} -> {ahora:.1f}): "
                f"{res.retcode if res else mt5.last_error()} {res.comment if res else ''}")
            return None
        pos = next((p for p in self.mias() if p.ticket == res.order), None)
        ticket = pos.ticket if pos else res.order
        sl, tp = (pos.sl, pos.tp) if pos else (sl, tp)
        self.db.execute("INSERT OR REPLACE INTO trades (ticket, symbol, side, lots, open_time, open_price, sl, tp, rsi_prev, "
                        "rsi_now, candle, status, spread_pips, atr_pips, hour_utc, stack, mfe_pips, mae_pips) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?, 'open', ?,?,?,?, 0, 0)",
                        (ticket, self.sym, lado, res.volume, dt.datetime.now().isoformat(" ", "seconds"), res.price,
                         sl, tp, prev, ahora, vela, hechos["spread_pips"], hechos["atr_pips"], hechos["hour_utc"],
                         hechos["open_same"] + 1))
        self.db.commit()
        log(f"#{ticket} {lado.upper()} {res.volume} lots at {res.price:.5f} (RSI {prev:.1f} -> {ahora:.1f}, candle {vela}); "
            f"SL {sl:.5f}, TP {tp:.5f}; trade {hechos['open_same'] + 1} of max {self.cfg.get('max_open_positions', 1)}")
        return ticket

    # ------------------------------------------------------------------ loop
    def resumen(self):
        hoy = dt.date.today().isoformat()
        r = self.db.execute("SELECT COUNT(*), COALESCE(SUM(profit),0), COALESCE(SUM(pips),0), "
                            "COALESCE(SUM(CASE WHEN profit>0 THEN 1 ELSE 0 END),0) FROM trades WHERE status='closed'").fetchone()
        h = self.db.execute("SELECT COUNT(*), COALESCE(SUM(profit),0) FROM trades WHERE status='closed' AND close_time>=?",
                            (hoy,)).fetchone()
        a = self.mt5.account_info()
        return (f"alive: today {h[0]} trades {h[1]:+.2f} $ | total {r[0]} trades, {r[3]} won, {r[2]:+.1f} pips, "
                f"{r[1]:+.2f} $ | open {len(self.mias())} | balance {a.balance:,.2f}, equity {a.equity:,.2f}")

    def correr(self):
        while True:
            try:
                if not self.mt5.terminal_info() or not self.mt5.terminal_info().connected:
                    log("MT5 not connected: reconnecting")
                    self.mt5.shutdown()
                    time.sleep(10)
                    self.mt5 = conectar()
                    continue
                self.revisar_abiertas()
                if self.nueva_vela():
                    self.mirar_senal()
                if not self.mt5.terminal_info().trade_allowed and time.time() - self.ult_algo_off > AVISO_CADA_S:
                    self.ult_algo_off = time.time()
                    log("WARNING: Algo Trading is OFF in MT5, the bot cannot open trades")
                if time.time() - self.ult_aviso > AVISO_CADA_S:
                    self.ult_aviso = time.time()
                    log(self.resumen())
            except Exception as e:        # keep running: a hiccup must not leave trades unwatched
                log(f"error: {type(e).__name__}: {e}")
                time.sleep(10)
            time.sleep(CADA_S)


def solo_uno():
    """Only one copy at a time (two copies would open two trades on the same signal)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 48911))
    except OSError:
        log("another copy of the bot is already running: this one exits")
        sys.exit(3)
    return s


if __name__ == "__main__":
    _candado = solo_uno()
    try:
        Bot().correr()
    except KeyboardInterrupt:
        log("stopped by hand")
    except Exception as e:
        log(f"STOPPED: {type(e).__name__}: {e}")
        sys.exit(1)

"""Web panel for the RSI bot: http://localhost:8282 on this PC, http://<this PC's IP>:8282 from the home network.

Other devices must log in with PANEL_PASSWORD from .env; this PC itself needs no password.

Shows the account, every pair (price, RSI, open trades), the trade history and the end of bot.log. Lets you pause /
resume new trades (STOP.txt), change the settings in config.json, close the bot's open trade and start / stop the bot.
It only touches the bot's own trades (magic number). Start it with INICIAR_PANEL.bat.
"""
import datetime as dt
import ipaddress
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from bot import ajustes_par, pares, pip_de, rsi
from mt5_conexion import conectar, leer_env

AQUI = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(AQUI, "config.json")
LOG = os.path.join(AQUI, "bot.log")
DB = os.path.join(AQUI, "trades.db")
PARAR = os.path.join(AQUI, "STOP.txt")
HTML = os.path.join(AQUI, "panel.html")
PYTHONW = os.path.join(AQUI, ".venv", "Scripts", "pythonw.exe")
POWERSHELL = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
PUERTO = 8282
PUERTO_BOT = 48911
PIP = 0.0001
TOKEN = secrets.token_hex(16)        # every button sends it: other web pages can't press them
SESIONES = set()                     # login cookies handed out since the panel started
FALLOS = {}                          # ip -> (wrong passwords in a row, time of the last one)
NOMBRES = {"localhost", socket.gethostname().lower()}

# settings the panel may change, with their allowed range
AJUSTES = {
    "lots": (float, 0.01, 10.0),
    "max_open_positions": (int, 1, 5),
    "rsi_period": (int, 2, 50),
    "rsi_level": (float, 5, 45),
    "take_profit_pips": (float, 2, 2000),
    "stop_loss_pips": (float, 2, 2000),
}
DE_ESTRATEGIA = {"rsi_period", "rsi_level", "take_profit_pips", "stop_loss_pips"}

candado_mt5 = threading.Lock()       # the MetaTrader5 package is not thread-safe
mt5 = None


def log_bot(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}\n")


def leer_cfg():
    return json.load(open(CONFIG, encoding="utf-8"))


def con_mt5(fn):
    """Run fn(mt5) under the lock, reconnecting once if the terminal dropped."""
    global mt5
    with candado_mt5:
        if mt5 is None or not mt5.terminal_info():
            mt5 = conectar()
        return fn(mt5)


# ------------------------------------------------------------------ bot process
def bot_corriendo():
    """The bot holds port 48911 while it runs."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", PUERTO_BOT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def parar_bot():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | "
          "Where-Object { $_.CommandLine -like '*Forex_Bot_Trader\\bot.py*' } | "
          "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    subprocess.run([POWERSHELL, "-NoProfile", "-Command", ps], capture_output=True, timeout=30,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(20):                  # wait until its port is free, so a restart can start it again
        if not bot_corriendo():
            break
        time.sleep(0.5)
    log_bot("stopped from the panel")


def arrancar_bot():
    if bot_corriendo():
        return
    subprocess.Popen([PYTHONW, os.path.join(AQUI, "bot.py")], cwd=AQUI,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


# ------------------------------------------------------------------ status
def estado():
    cfg = leer_cfg()
    magic, st = int(cfg["magic"]), cfg["strategy"]
    simbolos = pares(cfg)

    def de_mt5(m):
        a = m.account_info()
        t = m.terminal_info()
        pos = [p for p in (m.positions_get() or []) if p.magic == magic]
        datos = {}
        for sym in simbolos:
            m.symbol_select(sym, True)
            datos[sym] = (m.symbol_info(sym), m.symbol_info_tick(sym), m.copy_rates_from_pos(sym, m.TIMEFRAME_M5, 1, 600))
        return a, t, pos, datos, m.ACCOUNT_TRADE_MODE_DEMO

    a, t, pos, datos, demo = con_mt5(de_mt5)
    lista, digitos = [], {}
    for sym in simbolos:
        info, tick, r = datos[sym]
        aj = ajustes_par(cfg, sym)
        pip = pip_de(info) if info else PIP
        digitos[sym] = info.digits if info else 5
        valores = rsi([float(x["close"]) for x in r], int(aj["rsi_period"])) if r is not None and len(r) else []
        ultimas = [round(v, 1) for v in valores[-72:] if v is not None]
        suyas = [p for p in pos if p.symbol == sym]
        lista.append({
            "symbol": sym, "name": sym.split(".")[0][:3] + "/" + sym.split(".")[0][3:], "digits": digitos[sym],
            "bid": tick.bid if tick else None, "ask": tick.ask if tick else None,
            "spread": round((tick.ask - tick.bid) / pip, 1) if tick else None,
            "rsi": ultimas[-1] if ultimas else None, "rsi_prev": ultimas[-2] if len(ultimas) > 1 else None,
            "history": ultimas, "low": float(aj["rsi_level"]), "high": 100 - float(aj["rsi_level"]),
            "candle": dt.datetime.fromtimestamp(int(r[-1]["time"]), dt.timezone.utc).strftime("%H:%M UTC") if ultimas else "",
            "open": len(suyas), "direction": ("buy" if suyas[0].type == 0 else "sell") if suyas else "",
            "lots": aj["lots"], "tp": aj["take_profit_pips"], "sl": aj["stop_loss_pips"],
            "max": aj["max_open_positions"],
            "settings": {k: aj[k] for k in AJUSTES}, "own": sorted(k for k in (cfg.get("pairs") or {}).get(sym, {}) if k in AJUSTES),
            # dollars per pip for 1 lot, from tastyfx's own tick value (USD account)
            "usd_per_pip_lot": round(info.trade_tick_value * pip / info.trade_tick_size, 2) if info else None})

    abiertas = []
    for p in pos:
        lado = "buy" if p.type == 0 else "sell"
        info = datos.get(p.symbol, (None,))[0]
        pip = pip_de(info) if info else PIP
        pips = (p.price_current - p.price_open) / pip * (1 if lado == "buy" else -1)
        abiertas.append({"ticket": p.ticket, "symbol": p.symbol, "digits": digitos.get(p.symbol, 5), "side": lado,
                         "lots": p.volume, "open_price": p.price_open,
                         "sl": p.sl, "tp": p.tp, "now": p.price_current, "pips": round(pips, 1),
                         "profit": round(p.profit + p.swap, 2),
                         "open_time": dt.datetime.fromtimestamp(p.time, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")})

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cerradas = [dict(x) for x in con.execute(
        "SELECT ticket, symbol, side, lots, open_time, open_price, close_time, close_price, close_reason, pips, profit, note "
        "FROM trades WHERE status='closed' ORDER BY close_time")]
    for x in cerradas:
        x["digits"] = digitos.get(x["symbol"], 5)
    con.close()
    ganadas = sum(1 for x in cerradas if (x["profit"] or 0) > 0)
    curva, acum = [], 0.0
    for x in cerradas:
        acum += x["profit"] or 0
        curva.append(round(acum, 2))

    lineas = open(LOG, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(LOG) else []
    vivo = next((l[1:20] for l in reversed(lineas) if "alive:" in l or "START:" in l), "")

    return {
        "bot_running": bot_corriendo(), "paused": os.path.exists(PARAR), "last_alive": vivo,
        "account": {"login": a.login, "server": a.server, "demo": a.trade_mode == demo, "balance": a.balance,
                    "equity": a.equity, "currency": a.currency},
        "algo_trading": bool(t.trade_allowed), "connected": bool(t.connected),
        "pairs": lista,
        "config": {"lots": cfg["lots"], "max_open_positions": cfg.get("max_open_positions", 1),
                   **{k: st[k] for k in DE_ESTRATEGIA},
                   "overrides": {s: v for s, v in (cfg.get("pairs") or {}).items() if v}},
        "open": abiertas,
        "closed": cerradas[::-1][:100],
        "stats": {"trades": len(cerradas), "won": ganadas, "lost": len(cerradas) - ganadas,
                  "won_usd": round(sum(x["profit"] for x in cerradas if (x["profit"] or 0) > 0), 2),
                  "lost_usd": round(sum(x["profit"] or 0 for x in cerradas if (x["profit"] or 0) <= 0), 2),
                  # pips only add up within one pair (a USD/MXN pip is worth far less than a EUR/USD pip)
                  "by_pair": [{"name": q["name"], "trades": len(t), "won": sum(1 for x in t if (x["profit"] or 0) > 0),
                               "pips": round(sum(x["pips"] or 0 for x in t), 1),
                               "profit": round(sum(x["profit"] or 0 for x in t), 2)}
                              for q in lista for t in [[x for x in cerradas if x["symbol"] == q["symbol"]]] if t],
                  "profit": round(acum, 2)},
        "curve": curva,
        "events": [l for l in lineas if "alive:" not in l][-25:][::-1],
        "log": lineas[-40:][::-1],
    }


# ------------------------------------------------------------------ actions
def guardar_ajustes(nuevos):
    """Without "pair": change the defaults. With "pair": change that pair's own settings; a value equal to the
    default is stored as "use the default". "reset": true drops all of the pair's own settings."""
    cfg = leer_cfg()
    nuevos = dict(nuevos)
    par = nuevos.pop("pair", None) or None
    if par is not None and par not in (cfg.get("pairs") or {}):
        raise ValueError(f"unknown pair {par}")
    cambios = []
    if par and nuevos.pop("reset", False):
        if cfg["pairs"][par]:
            cambios.append(f"{par} back to the defaults (was {cfg['pairs'][par]})")
            cfg["pairs"][par] = {}
        nuevos = {}
    for k, v in nuevos.items():
        if k not in AJUSTES:
            raise ValueError(f"unknown setting {k}")
        tipo, lo, hi = AJUSTES[k]
        v = tipo(v)
        if not lo <= v <= hi:
            raise ValueError(f"{k} must be between {lo} and {hi}")
        if k == "lots":
            v = round(v, 2)
        if par:
            propio = cfg["pairs"][par]
            defecto = cfg["strategy"][k] if k in DE_ESTRATEGIA else cfg.get(k)
            antes = propio.get(k, defecto)
            if antes != v:
                cambios.append(f"{par} {k} {antes} -> {v}")
            if v == defecto:
                propio.pop(k, None)
            else:
                propio[k] = v
            continue
        destino = cfg["strategy"] if k in DE_ESTRATEGIA else cfg
        if destino.get(k) != v:
            cambios.append(f"default {k} {destino.get(k)} -> {v}")
            destino[k] = v
    if cambios:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        log_bot("settings changed from the panel: " + ", ".join(cambios))
    return cambios


def cerrar(ticket):
    cfg = leer_cfg()
    magic = int(cfg["magic"])

    def hacer(m):
        p = next(iter(m.positions_get(ticket=ticket) or []), None)
        if p is None:
            return "that trade is no longer open"
        if p.magic != magic:
            return "that trade is not the bot's: the panel does not touch it"
        tick = m.symbol_info_tick(p.symbol)
        info = m.symbol_info(p.symbol)
        compra = p.type == 0
        req = {"action": m.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "position": p.ticket,
               "type": m.ORDER_TYPE_SELL if compra else m.ORDER_TYPE_BUY, "price": tick.bid if compra else tick.ask,
               "deviation": 10, "magic": magic, "comment": "closed from panel", "type_time": m.ORDER_TIME_GTC,
               "type_filling": m.ORDER_FILLING_FOK if info.filling_mode & 1 else m.ORDER_FILLING_IOC}
        res = m.order_send(req)
        if res is None or res.retcode != m.TRADE_RETCODE_DONE:
            return f"close rejected: {res.retcode if res else m.last_error()} {res.comment if res else ''}"
        return None

    error = con_mt5(hacer)
    if not error:
        log_bot(f"#{ticket} closed from the panel")
    return error


# ------------------------------------------------------------------ web server
def clave_panel():
    """PANEL_PASSWORD from .env; the first time, make one up and save it there."""
    clave = leer_env().get("PANEL_PASSWORD")
    if not clave:
        clave = secrets.token_urlsafe(9)
        with open(os.path.join(AQUI, ".env"), "a", encoding="utf-8") as f:
            f.write(f"\nPANEL_PASSWORD={clave}\n")
    return clave


def ips_propias():
    try:
        ips = set(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        ips = set()
    return ips | {"127.0.0.1", "::1"}


CLAVE = clave_panel()

LOGIN = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>RSI Bot panel</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0f1115;color:#e6e8ec;font:15px "Segoe UI",system-ui,sans-serif}
form{background:#181b22;border:1px solid #2a2f3a;border-radius:12px;padding:26px;display:flex;flex-direction:column;gap:12px;width:290px}
input,button{font:inherit;padding:9px 11px;border-radius:8px;border:1px solid #2a2f3a;background:#0f1115;color:#e6e8ec}
button{background:#4c8dff;border-color:#4c8dff;color:#fff;cursor:pointer}.e{color:#e5484d;font-size:13px}
</style></head><body><form method="post" action="/login"><b>RSI Bot panel</b>
<input type="password" name="password" placeholder="Password" autofocus>__ERROR__<button>Log in</button></form></body></html>"""


class Panel(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, codigo, cuerpo, tipo="application/json", cabeceras=()):
        datos = cuerpo.encode("utf-8") if isinstance(cuerpo, str) else json.dumps(cuerpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(datos)))
        for k, v in cabeceras:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(datos)

    def host_valido(self):
        """Only a plain IP or this PC's name: blocks web pages that point their own domain at this PC."""
        h = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]").lower()
        if h in NOMBRES:
            return True
        try:
            ipaddress.ip_address(h)
            return True
        except ValueError:
            return False

    def dentro(self):
        """This PC itself, or a device that logged in."""
        if self.client_address[0] in ips_propias():
            return True
        c = SimpleCookie(self.headers.get("Cookie") or "")
        return "panel" in c and c["panel"].value in SESIONES

    def do_GET(self):
        if not self.host_valido():
            return self.responder(403, {"error": "forbidden"})
        if not self.dentro():
            if self.path.startswith("/api/"):
                return self.responder(401, {"error": "log in again"})
            return self.responder(200, LOGIN.replace("__ERROR__", ""), "text/html")
        if self.path == "/":
            return self.responder(200, open(HTML, encoding="utf-8").read().replace("__TOKEN__", TOKEN), "text/html")
        if self.path == "/api/status":
            try:
                return self.responder(200, estado())
            except Exception as e:
                return self.responder(500, {"error": f"{type(e).__name__}: {e}"})
        self.responder(404, {"error": "not found"})

    def login(self):
        ip = self.client_address[0]
        n, cuando = FALLOS.get(ip, (0, 0))
        if n >= 5 and time.time() - cuando < 60:
            return self.responder(429, LOGIN.replace("__ERROR__", '<span class="e">Too many tries: wait a minute.</span>'), "text/html")
        largo = int(self.headers.get("Content-Length") or 0)
        clave = parse_qs(self.rfile.read(largo).decode("utf-8", "replace")).get("password", [""])[0]
        if not secrets.compare_digest(clave.encode(), CLAVE.encode()):
            FALLOS[ip] = (n + 1, time.time())
            time.sleep(1)
            log_bot(f"panel: wrong password from {ip}")
            return self.responder(401, LOGIN.replace("__ERROR__", '<span class="e">Wrong password.</span>'), "text/html")
        FALLOS.pop(ip, None)
        sesion = secrets.token_urlsafe(24)
        SESIONES.add(sesion)
        log_bot(f"panel: logged in from {ip}")
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", f"panel={sesion}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if not self.host_valido():
            return self.responder(403, {"error": "forbidden"})
        if self.path == "/login":
            return self.login()
        if not self.dentro():
            return self.responder(401, {"error": "log in again"})
        if self.headers.get("X-Token") != TOKEN:
            return self.responder(403, {"error": "forbidden: reload the page"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            datos = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/pause":
                if datos.get("on"):
                    open(PARAR, "w").write("created from the panel\n")
                    log_bot("paused from the panel (STOP.txt): no new trades")
                elif os.path.exists(PARAR):
                    os.remove(PARAR)
                    log_bot("resumed from the panel: new trades allowed")
                return self.responder(200, {"ok": True})
            if self.path == "/api/settings":
                cambios = guardar_ajustes(datos)
                return self.responder(200, {"ok": True, "changes": cambios})
            if self.path == "/api/close":
                error = cerrar(int(datos["ticket"]))
                return self.responder(400 if error else 200, {"error": error} if error else {"ok": True})
            if self.path == "/api/bot":
                accion = datos.get("action")
                if accion in ("stop", "restart"):
                    parar_bot()
                if accion in ("start", "restart"):
                    arrancar_bot()
                return self.responder(200, {"ok": True})
            self.responder(404, {"error": "not found"})
        except ValueError as e:
            self.responder(400, {"error": str(e)})
        except Exception as e:
            self.responder(500, {"error": f"{type(e).__name__}: {e}"})


if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = False      # on Windows reuse would let two panels share the port
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Panel)
    except OSError:                      # already running: just open it
        webbrowser.open(f"http://localhost:{PUERTO}")
        sys.exit(0)
    if "--no-browser" not in sys.argv:
        webbrowser.open(f"http://localhost:{PUERTO}")
    servidor.serve_forever()

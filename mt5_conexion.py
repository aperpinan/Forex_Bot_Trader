"""Connection to the tastyfx MetaTrader 5 terminal on this PC, with the login from .env."""
import os

import MetaTrader5 as mt5

AQUI = os.path.dirname(os.path.abspath(__file__))
TERMINAL = r"C:\Program Files\tastyfx MetaTrader 5\terminal64.exe"


def leer_env(ruta=os.path.join(AQUI, ".env")):
    """KEY=value lines from .env (credentials stay on this PC)."""
    env = {}
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def conectar():
    env = leer_env()
    ok = mt5.initialize(path=TERMINAL, login=int(env["MT5_LOGIN"]), password=env["MT5_PASSWORD"],
                        server=env["MT5_SERVER"], timeout=60000)
    if not ok:
        raise RuntimeError(f"MT5 did not connect: {mt5.last_error()}")
    return mt5

"""Download EUR/USD 5-min bars (last 60 days) from Yahoo's chart API -> eurusd_5m.json"""
import json, os, urllib.request
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "eurusd_5m.json")
url = "https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X?interval=5m&range=60d"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
d = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
q = d["indicators"]["quote"][0]
bars = [(t, o, h, l, c) for t, o, h, l, c in zip(d["timestamp"], q["open"], q["high"], q["low"], q["close"])
        if None not in (o, h, l, c)]
json.dump(bars, open(DATA, "w"))
import time
print(len(bars), "bars", time.strftime("%Y-%m-%d %H:%M", time.gmtime(bars[0][0])), "->",
      time.strftime("%Y-%m-%d %H:%M", time.gmtime(bars[-1][0])), "UTC; last close", bars[-1][4])

import requests
import json

url = "https://api.chart-img.com/v2/tradingview/advanced-chart"
headers = {
    "x-api-key": "REDACTED-ROTATED-CHART-IMG-KEY",
    "Content-Type": "application/json",
}
payload = {
    "symbol": "BINANCE:BTCUSDT",
    "interval": "1h",
    "style": "heikinAshi",
    "theme": "dark",
    "width": 800,
    "height": 500,
    "timezone": "America/Mexico_City",
    "studies": [
        {
            "name": "Moving Average",
            "input": {
                "length": 1,
                "source": "open",
                "offset": 0,
                "smoothingLine": "SMA",
                "smoothingLength": 1,
            },
            "override": {
                "Plot.color": "rgb(33,150,243)",
                "Plot.linewidth": 2,
                "Plot.plottype": "line",
            },
        },
        {
            "name": "Moving Average",
            "input": {
                "length": 2,
                "source": "open",
                "offset": 0,
                "smoothingLine": "SMA",
                "smoothingLength": 2,
            },
            "override": {
                "Plot.color": "rgb(255,235,59)",
                "Plot.linewidth": 2,
                "Plot.plottype": "line",
            },
        },
    ],
}

r = requests.post(url, headers=headers, json=payload)
print("Status:", r.status_code)
ct = r.headers.get("content-type", "")
print("Content-Type:", ct)
if "image" in ct:
    path = r"C:\Users\Dell\.gemini\antigravity\brain\5020eaff-d09c-4048-8655-97a3d1292ece\artifacts\chart_dorothy_btc.png"
    with open(path, "wb") as f:
        f.write(r.content)
    print("Saved", len(r.content), "bytes to", path)
else:
    print(r.text[:500])

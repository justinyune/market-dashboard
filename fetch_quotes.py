import json
import urllib.request
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
]
INDICES = [
    ("KOSDAQ", "코스닥 지수"),
]


def get_datas(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as res:
        j = json.loads(res.read().decode("utf-8"))
    return j["datas"][0]


def num(s):
    return float(str(s).replace(",", ""))


items = []

for code, name in STOCKS:
    try:
        d = get_datas(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code}")
        items.append({
            "name": name,
            "code": code,
            "price": num(d["closePrice"]),
            "diff": num(d["compareToPreviousClosePrice"]),
            "pct": num(d["fluctuationsRatio"]),
            "krw": True,
        })
    except Exception as e:
        items.append({"name": name, "error": str(e)})

for code, name in INDICES:
    try:
        d = get_datas(f"https://polling.finance.naver.com/api/realtime/domestic/index/{code}")
        items.append({
            "name": name,
            "code": code,
            "price": num(d["closePrice"]),
            "diff": num(d["compareToPreviousClosePrice"]),
            "pct": num(d["fluctuationsRatio"]),
            "krw": False,
        })
    except Exception as e:
        items.append({"name": name, "error": str(e)})

kst = datetime.now(timezone(timedelta(hours=9)))
out = {"updated": kst.strftime("%m/%d %H:%M"), "items": items}

with open("quotes.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(json.dumps(out, ensure_ascii=False))

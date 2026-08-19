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

# --- 코스피200 선물 (야간 포함) 후보 엔드포인트 순차 시도 ---
FUT_CANDIDATES = [
    ("polling-index-FUT", "https://polling.finance.naver.com/api/realtime/domestic/index/FUT"),
    ("polling-index-K2G", "https://polling.finance.naver.com/api/realtime/domestic/index/K2G"),
    ("polling-futures", "https://polling.finance.naver.com/api/realtime/domestic/futures/FUT"),
    ("m-api-index-FUT", "https://m.stock.naver.com/api/index/FUT/basic"),
]

fut_item = None
fut_debug = []
for tag, url in FUT_CANDIDATES:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as res:
            j = json.loads(res.read().decode("utf-8"))
        d = j["datas"][0] if "datas" in j else j
        price = num(d["closePrice"])
        fut_item = {
            "name": "코스피200 선물",
            "code": "FUT",
            "price": price,
            "diff": num(d.get("compareToPreviousClosePrice", 0)),
            "pct": num(d.get("fluctuationsRatio", 0)),
            "krw": False,
        }
        fut_debug.append(tag + ": OK")
        break
    except Exception as e:
        fut_debug.append(tag + ": " + str(e)[:60])

if fut_item:
    items.insert(0, fut_item)  # 패널 맨 위에 표시

kst = datetime.now(timezone(timedelta(hours=9)))
out = {"updated": kst.strftime("%m/%d %H:%M"), "items": items, "fut_debug": fut_debug}

with open("quotes.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print(json.dumps(out, ensure_ascii=False))

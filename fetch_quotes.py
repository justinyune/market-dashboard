import json
import urllib.request
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
]
INDICES = [
    ("KOSPI", "코스피"),
    ("KOSDAQ", "코스닥"),
]
HISTORY_CODES = ["KOSPI", "KOSDAQ", "FUT"]  # 캔들차트용 일별 데이터
HISTORY_PAGES = 8  # 100개씩 8페이지 = 최대 800영업일 (60주선 계산용)


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode("utf-8"))


def num(s):
    return float(str(s).replace(",", ""))


items = []
debug = []

# --- 지수: 코스피, 코스닥 ---
for code_, name in INDICES:
    try:
        d = get_json(f"https://polling.finance.naver.com/api/realtime/domestic/index/{code_}")["datas"][0]
        items.append({
            "name": name, "code": code_, "group": "index",
            "price": num(d["closePrice"]),
            "diff": num(d["compareToPreviousClosePrice"]),
            "pct": num(d["fluctuationsRatio"]),
            "krw": False,
        })
    except Exception as e:
        items.append({"name": name, "code": code_, "group": "index", "error": str(e)[:60]})

# --- 코스피200 선물 (야간 포함: TradingView 1순위, 네이버 폴백) ---
def fut_tradingview():
    url = ("https://scanner.tradingview.com/symbol"
           "?symbol=KRX%3AK2I1!&fields=lp,ch,chp&no_404=true")
    d = get_json(url)
    price, ch, chp = d["lp"], d["ch"], d["chp"]
    if price is None:
        raise Exception("lp is null")
    return {
        "name": "코스피200 선물", "code": "FUT", "group": "index",
        "price": float(price),
        "diff": float(ch if ch is not None else 0),
        "pct": float(chp if chp is not None else 0),
        "krw": False,
    }


def fut_naver():
    d = get_json("https://polling.finance.naver.com/api/realtime/domestic/index/FUT")["datas"][0]
    return {
        "name": "코스피200 선물", "code": "FUT", "group": "index",
        "price": num(d["closePrice"]),
        "diff": num(d["compareToPreviousClosePrice"]),
        "pct": num(d["fluctuationsRatio"]),
        "krw": False,
    }


fut_item = None
for tag, fn in [("tv", fut_tradingview), ("naver", fut_naver)]:
    try:
        fut_item = fn()
        debug.append(f"FUT: {tag} OK")
        break
    except Exception as e:
        debug.append(f"FUT: {tag} " + str(e)[:50])
if fut_item:
    items.append(fut_item)

# --- 관심종목 ---
for code_, name in STOCKS:
    try:
        d = get_json(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_}")["datas"][0]
        items.append({
            "name": name, "code": code_, "group": "stock",
            "price": num(d["closePrice"]),
            "diff": num(d["compareToPreviousClosePrice"]),
            "pct": num(d["fluctuationsRatio"]),
            "krw": True,
        })
    except Exception as e:
        items.append({"name": name, "code": code_, "group": "stock", "error": str(e)[:60]})

# --- 지수 일별 시세 (자체 캔들차트용) ---
import re


def history_mapi(code_):
    bars = []
    for page in range(1, HISTORY_PAGES + 1):
        rows = get_json(f"https://m.stock.naver.com/api/index/{code_}/price?pageSize=100&page={page}")
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            try:
                bars.append({
                    "d": r["localTradedAt"][:10],
                    "o": num(r["openPrice"]),
                    "h": num(r["highPrice"]),
                    "l": num(r["lowPrice"]),
                    "c": num(r["closePrice"]),
                })
            except Exception:
                continue
        if len(rows) < 100:
            break
    return bars


def history_fchart(code_):
    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code_}&timeframe=day&count=800&requestType=0"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as res:
        xml = res.read().decode("euc-kr", errors="ignore")
    bars = []
    for m in re.finditer(r'data="(\d{8})\|([\d.]+)\|([\d.]+)\|([\d.]+)\|([\d.]+)\|', xml):
        d, o, h, l, c = m.groups()
        bars.append({
            "d": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "o": float(o), "h": float(h), "l": float(l), "c": float(c),
        })
    return bars


history = {}
for code_ in HISTORY_CODES:
    bars = []
    for tag, fn in [("mapi", history_mapi), ("fchart", history_fchart)]:
        try:
            bars = fn(code_)
            if bars:
                debug.append(f"history-{code_}: {tag} OK ({len(bars)})")
                break
            debug.append(f"history-{code_}: {tag} empty")
        except Exception as e:
            debug.append(f"history-{code_}: {tag} " + str(e)[:50])
    bars.sort(key=lambda b: b["d"])  # 과거 -> 현재
    if bars:
        history[code_] = bars

kst = datetime.now(timezone(timedelta(hours=9)))
out = {"updated": kst.strftime("%m/%d %H:%M"), "items": items, "history": history, "debug": debug}

with open("quotes.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print("items:", len(items), "history:", {k: len(v) for k, v in history.items()}, "debug:", debug)

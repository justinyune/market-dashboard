import json
import urllib.request
from datetime import datetime, timezone, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# (코드, 이름, 섹터ID)
STOCKS = [
    ("005930", "삼성전자", "tech"),
    ("000660", "SK하이닉스", "tech"),
    ("042700", "한미반도체", "tech"),
    ("403870", "HPSP", "tech"),
    ("138080", "오이솔루션", "tech"),
    ("012450", "한화에어로스페이스", "ind"),
    ("079550", "LIG넥스원", "ind"),
    ("329180", "HD현대중공업", "ind"),
    ("034020", "두산에너빌리티", "ind"),
    ("267260", "HD현대일렉트릭", "ind"),
    ("010120", "LS ELECTRIC", "ind"),
    ("035420", "NAVER", "comm"),
    ("035720", "카카오", "comm"),
    ("017670", "SK텔레콤", "comm"),
    ("030200", "KT", "comm"),
    ("005380", "현대차", "cyc"),
    ("000270", "기아", "cyc"),
    ("207940", "삼성바이오로직스", "health"),
    ("068270", "셀트리온", "health"),
    ("196170", "알테오젠", "health"),
    ("105560", "KB금융", "fin"),
    ("055550", "신한지주", "fin"),
    ("086790", "하나금융지주", "fin"),
    ("010950", "S-Oil", "energy"),
    ("078930", "GS", "energy"),
    ("015760", "한국전력", "util"),
    ("036460", "한국가스공사", "util"),
    ("005490", "POSCO홀딩스", "mat"),
    ("010130", "고려아연", "mat"),
    ("051910", "LG화학", "mat"),
    ("033780", "KT&G", "def"),
    ("271560", "오리온", "def"),
    ("088980", "맥쿼리인프라", "re"),
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

# --- 관심종목: 배치 조회(콤마 결합, 15개씩) -> 실패 시 개별 폴백 ---
def stock_item(d, code_, name, sector):
    return {
        "name": name, "code": code_, "group": "stock", "sector": sector,
        "price": num(d["closePrice"]),
        "diff": num(d["compareToPreviousClosePrice"]),
        "pct": num(d["fluctuationsRatio"]),
        "krw": True,
    }


# 내 매수 관심 (한국) — 여기에 (코드, 이름) 추가/삭제
MY_STOCKS = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
]

CHUNK = 15
for i in range(0, len(STOCKS), CHUNK):
    chunk = STOCKS[i:i + CHUNK]
    codes = ",".join(c for c, _, _ in chunk)
    got = {}
    try:
        datas = get_json(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{codes}")["datas"]
        for d in datas:
            got[str(d.get("itemCode") or d.get("cd") or "")] = d
        debug.append(f"batch{i//CHUNK}: OK ({len(datas)})")
    except Exception as e:
        debug.append(f"batch{i//CHUNK}: " + str(e)[:50])
    for code_, name, sector in chunk:
        d = got.get(code_)
        if d is None:
            try:
                d = get_json(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_}")["datas"][0]
            except Exception as e:
                items.append({"name": name, "code": code_, "group": "stock", "sector": sector, "error": str(e)[:50]})
                continue
        try:
            items.append(stock_item(d, code_, name, sector))
        except Exception as e:
            items.append({"name": name, "code": code_, "group": "stock", "sector": sector, "error": str(e)[:50]})

# --- 내 매수 관심 (한국) ---
if MY_STOCKS:
    codes = ",".join(c for c, _ in MY_STOCKS)
    got = {}
    try:
        for d in get_json(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{codes}")["datas"]:
            got[str(d.get("itemCode") or d.get("cd") or "")] = d
    except Exception as e:
        debug.append("my-batch: " + str(e)[:50])
    for code_, name in MY_STOCKS:
        d = got.get(code_)
        if d is None:
            try:
                d = get_json(f"https://polling.finance.naver.com/api/realtime/domestic/stock/{code_}")["datas"][0]
            except Exception as e:
                items.append({"name": name, "code": code_, "group": "mystock", "error": str(e)[:50]})
                continue
        try:
            it = stock_item(d, code_, name, "my")
            it["group"] = "mystock"
            items.append(it)
        except Exception as e:
            items.append({"name": name, "code": code_, "group": "mystock", "error": str(e)[:50]})


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

# --- 선물 인트라데이 누적 (주간 09:00~15:45 + 야간 18:00~다음날 05:00) ---
def in_session(dt):
    hm = dt.hour * 60 + dt.minute
    day_s, day_e = 9 * 60, 15 * 60 + 50      # 주간 (마감 여유 5분)
    night_s, night_e = 18 * 60, 5 * 60 + 5   # 야간 (자정 걸침)
    return (day_s <= hm <= day_e) or (hm >= night_s) or (hm <= night_e)


fut_intraday = []
try:
    with open("quotes.json", encoding="utf-8") as f:
        prev = json.load(f)
    fut_intraday = prev.get("fut_intraday", [])
except Exception:
    pass

# 세션 시작(직전 09:00 KST) 이전 포인트 제거
session_start = kst.replace(hour=9, minute=0, second=0, microsecond=0)
if kst.hour < 9:
    session_start -= timedelta(days=1)
start_ts = int(session_start.timestamp())
fut_intraday = [pt for pt in fut_intraday if pt.get("ts", 0) >= start_ts]

if fut_item and in_session(kst):
    label = kst.strftime("%H:%M")
    if not fut_intraday or fut_intraday[-1].get("t") != label:
        fut_intraday.append({
            "ts": int(kst.timestamp()),
            "t": label,
            "p": fut_item["price"],
        })
        # 기준선(전일 정산가) 저장: 현재가 - 변동
        base = round(fut_item["price"] - fut_item["diff"], 2)
    else:
        base = None
else:
    base = None

fut_base = None
if fut_item:
    fut_base = round(fut_item["price"] - fut_item["diff"], 2)

out = {"updated": kst.strftime("%m/%d %H:%M"), "items": items, "history": history,
       "fut_intraday": fut_intraday, "fut_base": fut_base, "debug": debug}

with open("quotes.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)

print("items:", len(items), "history:", {k: len(v) for k, v in history.items()}, "debug:", debug)

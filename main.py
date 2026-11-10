import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

INDEXES = {
    "^GSPC": "S&P 500", "^IXIC": "Nasdaq Composite", "^DJI": "Dow Jones",
    "^RUT": "Russell 2000", "^VIX": "VIX (Volatility)",
}
STOCKS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia",
    "AMZN": "Amazon", "GOOGL": "Alphabet", "META": "Meta",
    "TSLA": "Tesla", "JPM": "JPMorgan", "V": "Visa", "WMT": "Walmart",
    "ELPE.AT": "Hellenic Energy",
}
REFRESH_SECONDS = 60      # how often prices are refreshed
HISTORY_SECONDS = 300     # how often chart history is refreshed

cache = {"updated": None, "market_open": False, "indexes": [], "stocks": []}
history_cache = {"fetched": 0.0, "data": {}}


def market_is_open() -> bool:
    """US regular session: Mon-Fri 09:30-16:00 New York time (holidays ignored)."""
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def fetch_history(symbols: list) -> dict:
    """One request for all symbols: last 5 days, 30-minute candles."""
    out = {}
    try:
        df = yf.download(symbols, period="5d", interval="30m",
                         group_by="ticker", progress=False, threads=False)
        for s in symbols:
            try:
                closes = df[s]["Close"].dropna()
                out[s] = [round(float(v), 2) for v in closes.tolist()]
            except Exception:
                out[s] = []
    except Exception as e:
        print(f"History error: {e}")
    return out


def get_history() -> dict:
    now = time.time()
    if now - history_cache["fetched"] > HISTORY_SECONDS:
        new = fetch_history(list(INDEXES) + list(STOCKS))
        if any(new.values()):
            history_cache["data"] = new
        history_cache["fetched"] = now
    return history_cache["data"]


def fetch_group(symbols: dict, history: dict) -> list:
    rows = []
    for symbol, name in symbols.items():
        try:
            info = yf.Ticker(symbol).fast_info
            price = float(info.last_price)
            prev = float(info.previous_close)
            rows.append({
                "symbol": symbol, "name": name,
                "price": price,
                "change": price - prev,
                "change_pct": (price - prev) / prev * 100,
                "spark": history.get(symbol, []),
            })
        except Exception as e:
            print(f"Failed {symbol}: {e}")  # one bad symbol must not break the rest
    return rows


def fetch_all() -> dict:
    history = get_history()
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "market_open": market_is_open(),
        "indexes": fetch_group(INDEXES, history),
        "stocks": fetch_group(STOCKS, history),
    }


async def refresher():
    while True:
        try:
            cache.update(await asyncio.to_thread(fetch_all))
        except Exception as e:
            print(f"Refresh error: {e}")
        await asyncio.sleep(REFRESH_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(refresher())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/api/prices")
def prices():
    return cache


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Markets Dashboard</title>
<style>
:root{--bg:#f5f8fa;--card:#fff;--line:#e0e4e9;--text:#1d2129;--muted:#6b7683;--accent:#6001d2;--up:#188038;--down:#c5221f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line)}
.bar{max-width:1100px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.logo{font-weight:800;font-size:1.25rem;color:var(--accent);letter-spacing:-.3px}
.status{display:flex;align-items:center;gap:8px;font-size:.85rem;color:var(--muted)}
.dot{width:9px;height:9px;border-radius:50%;background:#9aa4af}
.dot.open{background:var(--up)}
main{max-width:1100px;margin:0 auto;padding:20px}
h2{font-size:1.05rem;margin:24px 0 12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .name{font-size:.85rem;color:var(--muted)}
.card .price{font-size:1.35rem;font-weight:700;margin:4px 0 2px}
.chg{font-size:.9rem;font-weight:600}
.up{color:var(--up)}.down{color:var(--down)}
.spark{width:100%;height:36px;margin-top:8px;display:block}
.panel{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
table{width:100%;border-collapse:collapse}
th{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);text-align:right;padding:10px 14px;border-bottom:1px solid var(--line);background:#fafbfc}
td{padding:12px 14px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
th:first-child,td:first-child{text-align:left}
tr:last-child td{border-bottom:none}
tbody tr:hover{background:#f7f3ff}
.sym{font-weight:700;color:var(--accent)}
.sub{font-size:.8rem;color:var(--muted)}
td.chart{width:150px}
td.chart .spark{margin:0;height:32px}
footer{max-width:1100px;margin:0 auto;padding:8px 20px 32px;color:var(--muted);font-size:.78rem}
@media(max-width:640px){.hide-sm{display:none}}
</style></head><body>
<header><div class="bar">
  <div class="logo">Markets</div>
  <div class="status"><span id="dot" class="dot"></span><span id="mkt">Loading...</span><span>&middot;</span><span id="upd">Updating...</span></div>
</div></header>
<main>
  <h2>US indexes</h2>
  <div class="cards" id="indexes"></div>
  <h2>Stocks</h2>
  <div class="panel"><table>
    <thead><tr><th>Symbol</th><th>Last price</th><th>Change</th><th>% Change</th><th class="hide-sm">5-day trend</th></tr></thead>
    <tbody id="stocks"></tbody>
  </table></div>
</main>
<footer>Data from Yahoo Finance via yfinance. Prices may be delayed. For information only, not investment advice.</footer>
<script>
const fmt = n => n.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const sign = n => (n>=0 ? '+' : '');
function spark(values, up){
  if(!values || values.length < 2) return '';
  const w=120, h=36, min=Math.min(...values), max=Math.max(...values), range=(max-min)||1;
  const pts = values.map((v,i) => ((i/(values.length-1))*w).toFixed(1)+','+(h-2-((v-min)/range)*(h-4)).toFixed(1)).join(' ');
  const color = up ? '#188038' : '#c5221f';
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline fill="none" stroke="${color}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" points="${pts}"/></svg>`;
}
function indexCard(r){
  const cls = r.change_pct>=0 ? 'up' : 'down';
  return `<div class="card"><div class="name">${r.name}</div><div class="price">${fmt(r.price)}</div>
    <div class="chg ${cls}">${sign(r.change)}${fmt(r.change)} (${sign(r.change_pct)}${fmt(r.change_pct)}%)</div>
    ${spark(r.spark, r.change_pct>=0)}</div>`;
}
function stockRow(r){
  const cls = r.change_pct>=0 ? 'up' : 'down';
  return `<tr><td><div class="sym">${r.symbol}</div><div class="sub">${r.name}</div></td>
    <td>${fmt(r.price)}</td>
    <td class="${cls}">${sign(r.change)}${fmt(r.change)}</td>
    <td class="${cls}">${sign(r.change_pct)}${fmt(r.change_pct)}%</td>
    <td class="chart hide-sm">${spark(r.spark, r.change_pct>=0)}</td></tr>`;
}
async function load(){
  try{
    const d = await (await fetch('/api/prices')).json();
    document.getElementById('indexes').innerHTML = d.indexes.map(indexCard).join('');
    document.getElementById('stocks').innerHTML = d.stocks.map(stockRow).join('');
    document.getElementById('dot').className = 'dot' + (d.market_open ? ' open' : '');
    document.getElementById('mkt').textContent = d.market_open ? 'US market open' : 'US market closed';
    if(d.updated){ document.getElementById('upd').textContent = 'Updated ' + new Date(d.updated).toLocaleTimeString(); }
  }catch(e){
    document.getElementById('upd').textContent = 'Data unavailable';
  }
}
load(); setInterval(load, 10000);
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE

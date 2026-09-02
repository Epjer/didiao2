import requests
import time
from datetime import datetime

# ==================== 只改这里 ====================
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=23ff0ac2-4fa7-44ed-a609-936f2efc1718"

TRADERS = [
    {"name": "十年一梦A", "uniqueCode": "FA5E8E09479C7C88"},
    {"name": "成都开心哥", "uniqueCode": "8C7DC3E73FECAEE3"},
    {"name": "小夕&夏天", "uniqueCode": "845654750896108623"},
    {"name": "币圈大鲨鱼Lin", "uniqueCode": "8FB6049D049B4FE2"},
]
# ==================================================

# ========== 自适应参数（不用手动改） ==========
num_traders = len(TRADERS)

if num_traders <= 3:
    REQUEST_GAP = 0.25
    LOOP_SLEEP = 2
elif num_traders <= 5:
    REQUEST_GAP = 0.32
    LOOP_SLEEP = 3
else:
    REQUEST_GAP = 0.42
    LOOP_SLEEP = 4

ASSET_CACHE_SECONDS = 300
# ==============================================

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; OKX-Monitor/1.5)",
    "Accept": "application/json"
})

asset_cache = {}

def send_wechat(title, content):
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n\n{content}"
        }
    }
    try:
        r = session.post(WEBHOOK, json=data, timeout=10)
        if r.status_code == 200:
            print("微信推送成功")
        else:
            print(f"微信推送异常: {r.status_code} {r.text}")
    except Exception as e:
        print("推送失败：", e)

def get_open_time_str(p):
    if p.get("openTime"):
        try:
            ts = int(p["openTime"]) / 1000
            return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S")
        except:
            return str(p.get("openTime"))
    return "未知"

def get_trader_invest_amt(code):
    now = time.time()
    cache = asset_cache.get(code)
    if cache and (now - cache["update_time"] < ASSET_CACHE_SECONDS):
        return cache["investAmt"]

    url = f"https://www.okx.com/api/v5/copytrading/public-stats?uniqueCode={code}&lastDays=1"
    data = safe_get(url, retry=1)

    invest_amt = 0.0
    if data and data.get("code") == "0" and data.get("data"):
        try:
            invest_amt = float(data["data"][0].get("investAmt", 0))
        except:
            invest_amt = 0.0

    asset_cache[code] = {"investAmt": invest_amt, "update_time": now}
    return invest_amt

def format_position(p, invest_amt=None):
    pos_side = p.get("posSide", "")
    if pos_side == "long":
        side = "多"
    elif pos_side == "short":
        side = "空"
    else:
        side = f"净持仓({pos_side})" if pos_side else "未知方向"

    inst = p.get("instId") or "未知币种"
    lever = p.get("lever") or "?"
    open_px = p.get("openAvgPx") or "未知"
    size = p.get("subPos") or "未知"
    upl = p.get("upl") or "0"
    margin = p.get("margin") or "0"
    sub_pos_id = p.get("subPosId") or ""

    open_time_str = get_open_time_str(p)

    content = (
        f"{inst} {side} {lever}x\n"
        f"开仓价：{open_px} | 数量：{size}\n"
        f"保证金：{margin} | 浮盈：{upl}\n"
        f"接口开仓时间：{open_time_str}"
    )

    if sub_pos_id:
        content += f"\n仓位ID：{sub_pos_id[-8:]}"

    if invest_amt and invest_amt > 0:
        try:
            ratio = float(margin) / invest_amt * 100
            content += f"\n**占总资产：{ratio:.2f}%**"
        except:
            content += "\n占总资产：计算失败"
    else:
        content += "\n占总资产：未知"

    return content

def safe_get(url, retry=1):
    for attempt in range(retry + 1):
        try:
            resp = session.get(url, timeout=12)
            data = resp.json()
            if data.get("code") == "0":
                return data
            print(f"接口返回异常 (attempt {attempt+1}): {data.get('code')} {data.get('msg')}")
            if attempt < retry:
                time.sleep(1.2)
                continue
            return data
        except Exception as e:
            print(f"请求异常 (attempt {attempt+1}): {e}")
            if attempt < retry:
                time.sleep(1.2)
                continue
            return None
    return None

last_pos_ids = {t["uniqueCode"]: set() for t in TRADERS}
first_run = {t["uniqueCode"]: True for t in TRADERS}

print("=" * 50)
print("多交易员监控已启动（自适应版本）")
print(f"当前监控数量：{num_traders} 人")
print(f"请求间隔：{REQUEST_GAP}s | 循环休眠：{LOOP_SLEEP}s")
print("=" * 50)
for t in TRADERS:
    print(f"  - {t['name']} ({t['uniqueCode']})")
print()

while True:
    start_time = time.time()
    for trader in TRADERS:
        name = trader["name"]
        code = trader["uniqueCode"]
        current_url = f"https://www.okx.com/api/v5/copytrading/public-current-subpositions?uniqueCode={code}"
        history_url = f"https://www.okx.com/api/v5/copytrading/public-subpositions-history?uniqueCode={code}&limit=20"

        data = safe_get(current_url, retry=1)
        if not data or data.get("code") != "0":
            print(f"[{name}] 获取当前持仓失败，跳过")
            time.sleep(REQUEST_GAP)
            continue

        positions = data.get("data", [])
        current_ids = {p["subPosId"] for p in positions if p.get("subPosId")}

        invest_amt = get_trader_invest_amt(code)

        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] {name} 当前持仓：{len(positions)} | 总资产：{invest_amt:.2f}")

        if not first_run[code]:
            new_ids = current_ids - last_pos_ids[code]
            closed_ids = last_pos_ids[code] - current_ids

            if new_ids:
                for p in positions:
                    if p.get("subPosId") in new_ids:
                        title = f"【{name}】新开仓"
                        content = format_position(p, invest_amt=invest_amt)
                        send_wechat(title, content)
                        print(f"  → {name} 新开仓：{content}")

            if closed_ids:
                hist_data = safe_get(history_url, retry=1)
                if hist_data and hist_data.get("code") == "0":
                    hist = hist_data.get("data", [])
                    for h in hist:
                        if h.get("subPosId") in closed_ids:
                            side = "多" if h.get("posSide") == "long" else "空" if h.get("posSide") == "short" else h.get("posSide", "未知")
                            open_time_str = get_open_time_str(h)

                            title = f"【{name}】已平仓"
                            content = (
                                f"{h.get('instId') or '未知币种'} {side} {h.get('lever') or '?'}x\n"
                                f"开仓价：{h.get('openAvgPx') or '未知'}\n"
                                f"平仓价：{h.get('closeAvgPx') or '未知'}\n"
                                f"盈亏：{h.get('pnl')} ({h.get('pnlRatio')})\n"
                                f"接口开仓时间：{open_time_str}"
                            )
                            send_wechat(title, content)
                            print(f"  → {name} 平仓：{content}")
                else:
                    print(f"[{name}] 查询历史失败")

last_pos_ids[code] = current_ids
        first_run[code] = False

        time.sleep(REQUEST_GAP)

    elapsed = time.time() - start_time
    print(f"--- 本轮耗时 {elapsed:.1f}s，休眠 {LOOP_SLEEP}s ---\n")
    time.sleep(LOOP_SLEEP)

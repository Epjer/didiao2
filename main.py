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

# 请求间隔（秒），防止触发限速
REQUEST_GAP = 0.45
# 每轮结束后的休眠（秒），最终有效周期大约 6.5\~8.5 秒
LOOP_SLEEP = 4

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; OKX-Monitor/1.1)",
    "Accept": "application/json"
})

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

def format_position(p):
    side = "多" if p.get("posSide") == "long" else "空"
    inst = p.get("instId", "")
    lever = p.get("lever", "")
    open_px = p.get("openAvgPx", "")
    size = p.get("subPos", "")
    upl = p.get("upl", "")

    # 把毫秒时间戳转成可读时间
    open_time_str = ""
    if p.get("openTime"):
        try:
            ts = int(p["openTime"]) / 1000
            open_time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S")
        except:
            open_time_str = str(p.get("openTime"))

    return (f"{inst} {side} {lever}x | 开仓价 {open_px} | 数量 {size} | 浮盈 {upl}\n"
            f"接口开仓时间：{open_time_str}")

def safe_get(url, retry=1):
    """带简单重试的请求"""
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

print("多交易员监控已启动（稳健版 + openTime）...")
for t in TRADERS:
    print(f"  - {t['name']} ({t['uniqueCode']})")
print(f"请求间隔: {REQUEST_GAP}s | 循环休眠: {LOOP_SLEEP}s\n")

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
        current_ids = {p["subPosId"] for p in positions}

        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] {name} 当前持仓：{len(positions)}")

        if not first_run[code]:
            new_ids = current_ids - last_pos_ids[code]
            closed_ids = last_pos_ids[code] - current_ids

            # 新开仓
            if new_ids:
                for p in positions:
                    if p["subPosId"] in new_ids:
                        title = f"【{name}】新开仓"
                        content = format_position(p)
                        send_wechat(title, content)
                        print(f"  → {name} 新开仓：{content}")

            # 平仓
            if closed_ids:
                hist_data = safe_get(history_url, retry=1)
                if hist_data and hist_data.get("code") == "0":
                    hist = hist_data.get("data", [])
                    for h in hist:
                        if h.get("subPosId") in closed_ids:
                            side = "多" if h.get("posSide") == "long" else "空"
                            open_time_str = ""
                            if h.get("openTime"):
                                try:
                                    ts = int(h["openTime"]) / 1000
                                    open_time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S")
                                except:
                                    open_time_str = str(h.get("openTime"))

                            title = f"【{name}】已平仓"
                            content = (
                                f"{h.get('instId')} {side} {h.get('lever')}x\n"
                                f"开仓价：{h.get('openAvgPx')}\n"
                                f"平仓价：{h.get('closeAvgPx')}\n"
                                f"盈亏：{h.get('pnl')} ({h.get('pnlRatio')})\n"
                                f"接口开仓时间：{open_time_str}"
                            )
                            send_wechat(title, content)
                            print(f"  → {name} 平仓：{content}")
                else:
                    print(f"[{name}] 查询历史失败")

        last_pos_ids[code] = current_ids
        first_run[code] = False

        # 关键请求间隔，防止触发限速
        time.sleep(REQUEST_GAP)

    elapsed = time.time() - start_time
    print(f"--- 本轮耗时 {elapsed:.1f}s，休眠 {LOOP_SLEEP}s ---\n")
    time.sleep(LOOP_SLEEP)

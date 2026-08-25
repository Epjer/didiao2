import requests
import time
from datetime import datetime

# ==================== 只改这里 ====================
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=23ff0ac2-4fa7-44ed-a609-936f2efc1718"
# ==================================================

UNIQUE_CODE = "AFE05086676C8FC3"
TRADER_NAME = "低调潜水"

CURRENT_URL = f"https://www.okx.com/api/v5/copytrading/public-current-subpositions?uniqueCode={UNIQUE_CODE}"
HISTORY_URL = f"https://www.okx.com/api/v5/copytrading/public-subpositions-history?uniqueCode={UNIQUE_CODE}&limit=20"

def send_wechat(title, content):
    data = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n\n{content}"
        }
    }
    try:
        requests.post(WEBHOOK, json=data, timeout=10)
        print("微信推送成功")
    except Exception as e:
        print("推送失败：", e)

def format_position(p):
    side = "多" if p.get("posSide") == "long" else "空"
    inst = p.get("instId", "")
    lever = p.get("lever", "")
    open_px = p.get("openAvgPx", "")
    size = p.get("subPos", "")
    upl = p.get("upl", "")
    return f"{inst} {side} {lever}x | 开仓价 {open_px} | 数量 {size} | 浮盈 {upl}"

last_pos_ids = set()
first_run = True

print(f"开始监控【{TRADER_NAME}】持仓变化...")
print("按 Ctrl+C 可停止（云上会一直运行）")

while True:
    try:
        resp = requests.get(CURRENT_URL, timeout=15)
        data = resp.json()

        if data.get("code") != "0":
            print("接口异常：", data.get("msg"))
            time.sleep(15)
            continue

        positions = data.get("data", [])
        current_ids = {p["subPosId"] for p in positions}

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] 当前持仓数量：{len(positions)}")

        if not first_run:
            # 新开仓
            new_ids = current_ids - last_pos_ids
            # 已平仓
            closed_ids = last_pos_ids - current_ids

            if new_ids:
                for p in positions:
                    if p["subPosId"] in new_ids:
                        title = f"【{TRADER_NAME}】新开仓"
                        content = format_position(p)
                        send_wechat(title, content)
                        print("检测到新开仓：", content)

            if closed_ids:
                try:
                    hist = requests.get(HISTORY_URL, timeout=15).json().get("data", [])
                    for h in hist:
                        if h.get("subPosId") in closed_ids:
                            side = "多" if h.get("posSide") == "long" else "空"
                            title = f"【{TRADER_NAME}】已平仓"
                            content = (
                                f"{h.get('instId')} {side} {h.get('lever')}x\n"
                                f"开仓价：{h.get('openAvgPx')}\n"
                                f"平仓价：{h.get('closeAvgPx')}\n"
                                f"盈亏：{h.get('pnl')} ({h.get('pnlRatio')})"
                            )
                            send_wechat(title, content)
                            print("检测到平仓：", content)
                except Exception as e:
                    print("查询历史失败：", e)

        last_pos_ids = current_ids
        first_run = False

    except Exception as e:
        print("出错：", e)

    time.sleep(15)  # 每15秒检查一次
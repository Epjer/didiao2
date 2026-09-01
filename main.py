import requests
import time
from datetime import datetime

# ==================== 只改这里 ====================
WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=23ff0ac2-4fa7-44ed-a609-936f2efc1718"

# 监控的交易员列表
TRADERS = [
    {
        "name": "十年一梦A",
        "uniqueCode": "FA5E8E09479C7C88"
    },
    {
        "name": "成都开心哥",
        "uniqueCode": "8C7DC3E73FECAEE3"
    },
    {
        "name": "FFFD",
        "uniqueCode": "2F0C19E248311976"
    },
    {
        "name": "小夕&夏天",
        "uniqueCode": "845654750896108623"
    },
    {
        "name": "币圈大鲨鱼Lin",
        "uniqueCode": "8FB6049D049B4FE2"
    },
]
# ==================================================

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

last_pos_ids = {t["uniqueCode"]: set() for t in TRADERS}
first_run = {t["uniqueCode"]: True for t in TRADERS}

print("多交易员监控已启动...")
for t in TRADERS:
    print(f"  - {t['name']} ({t['uniqueCode']})")

while True:
    for trader in TRADERS:
        name = trader["name"]
        code = trader["uniqueCode"]
        current_url = f"https://www.okx.com/api/v5/copytrading/public-current-subpositions?uniqueCode={code}"
        history_url = f"https://www.okx.com/api/v5/copytrading/public-subpositions-history?uniqueCode={code}&limit=20"

        try:
            resp = requests.get(current_url, timeout=15)
            data = resp.json()

            if data.get("code") != "0":
                print(f"[{name}] 接口异常：", data.get("msg"))
                continue

            positions = data.get("data", [])
            current_ids = {p["subPosId"] for p in positions}

            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] {name} 当前持仓：{len(positions)}")

            if not first_run[code]:
                new_ids = current_ids - last_pos_ids[code]
                closed_ids = last_pos_ids[code] - current_ids

                if new_ids:
                    for p in positions:
                        if p["subPosId"] in new_ids:
                            title = f"【{name}】新开仓"
                            content = format_position(p)
                            send_wechat(title, content)
                            print(f"  → {name} 新开仓：{content}")

                if closed_ids:
                    try:
                        hist = requests.get(history_url, timeout=15).json().get("data", [])
                        for h in hist:
                            if h.get("subPosId") in closed_ids:
                                side = "多" if h.get("posSide") == "long" else "空"
                                title = f"【{name}】已平仓"
                                content = (
                                    f"{h.get('instId')} {side} {h.get('lever')}x\n"
                                    f"开仓价：{h.get('openAvgPx')}\n"
                                    f"平仓价：{h.get('closeAvgPx')}\n"
                                    f"盈亏：{h.get('pnl')} ({h.get('pnlRatio')})"
                                )
                                send_wechat(title, content)
                                print(f"  → {name} 平仓：{content}")
                    except Exception as e:
                        print(f"[{name}] 查询历史失败：", e)

            last_pos_ids[code] = current_ids
            first_run[code] = False

        except Exception as e:
            print(f"[{name}] 出错：", e)

    time.sleep(5)

#!/usr/bin/env python3
"""让赢家跑 — 移动止盈/止损看板 (R6 / R6b)

目的: 把"让赢家跑"做成可执行的数字, 而不是口号。
  - 对每只持仓, 算出建仓以来最高价、当前价、移动止盈位、距离。
  - 赢家用"从最高点回撤 N%"触发, 不用固定止盈点 (固定点=给赢家设天花板)。
  - 同时给"保本/保利"硬线: 移动止盈位一旦升到成本之上, 就锁定利润。

数据源: 腾讯日K (建仓至今最高) + 新浪实时 (当前价), 纯 urllib, 无第三方依赖。

持仓配置: monitor/holdings.json (见文件内 schema)。第一次运行会生成模板。

回撤阈值 (可在 holdings.json 每只覆盖, 默认按档位):
  核心 / 普通档: 回撤 18%  减半
  试错档:        回撤 15%  减半

用法:
  python3 scripts/core/winners_guard.py            # 看板
  python3 scripts/core/winners_guard.py --init     # 生成 holdings.json 模板
"""
import argparse
import json
import urllib.request
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MONITOR_DIR = PROJECT_ROOT / "monitor"
HOLDINGS_PATH = MONITOR_DIR / "holdings.json"

TODAY = date.today().isoformat()

DEFAULT_DRAWDOWN = {"核心": 0.18, "普通": 0.18, "试错": 0.15}

TEMPLATE = {
    "note": "持仓配置 (winners_guard 用). entry_date=建仓日(算最高点起点), tier=核心/普通/试错. trail 可选, 覆盖默认回撤.",
    "holdings": [
        {"name": "三七互娱", "code": "sz002555", "tier": "普通", "shares": 9700, "cost": 21.317, "entry_date": "2026-04-16"},
        {"name": "乐鑫科技", "code": "sh688018", "tier": "普通", "shares": 1027, "cost": 152.43, "entry_date": "2026-04-16"},
        {"name": "工业富联", "code": "sh601138", "tier": "核心", "shares": 2400, "cost": 63.19, "entry_date": "2026-05-12"},
        {"name": "平高电气", "code": "sh600312", "tier": "普通", "shares": 6300, "cost": 23.11, "entry_date": "2026-04-16"},
        {"name": "易点天下", "code": "sz301171", "tier": "普通", "shares": 3190, "cost": 34.78, "entry_date": "2026-04-16"},
        {"name": "汇川技术", "code": "sz300124", "tier": "普通", "shares": 1500, "cost": 84.84, "entry_date": "2026-04-16"},
        {"name": "天合光能", "code": "sh688599", "tier": "试错", "shares": 3300, "cost": 17.80, "entry_date": "2026-05-12"},
        {"name": "百济神州", "code": "sh688235", "tier": "试错", "shares": 200, "cost": 268.03, "entry_date": "2026-05-12"},
        {"name": "天赐材料", "code": "sz002709", "tier": "试错", "shares": 300, "cost": 52.02, "entry_date": "2026-05-19"}
    ]
}


def fetch_kline(code, start="2026-01-01"):
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={code},day,{start},{TODAY},1000,qfq")
    try:
        node = json.loads(urllib.request.urlopen(url, timeout=12).read())["data"][code]
        kl = node.get("qfqday") or node.get("day") or []
        # [date, open, close, high, low, volume]
        return [(r[0], float(r[3]), float(r[2])) for r in kl]  # (date, high, close)
    except Exception:
        return []


def fetch_realtime_sina(codes):
    if not codes:
        return {}
    url = f"http://hq.sinajs.cn/list={','.join(codes)}"
    req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
    out = {}
    try:
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        for line in raw.split(";\n"):
            if '="' not in line:
                continue
            var = line.split("=")[0].split("_")[-1]
            parts = line.split('"')[1].split(",")
            if len(parts) < 4:
                continue
            try:
                out[var] = float(parts[3])
            except ValueError:
                continue
    except Exception:
        pass
    return out


def peak_since(kl, entry_date, today_price):
    highs = [h for (d, h, c) in kl if d >= entry_date]
    if today_price:
        highs.append(today_price)
    return max(highs) if highs else None


def cmd_init():
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    with open(HOLDINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
    print(f"✅ 已生成模板 {HOLDINGS_PATH.relative_to(PROJECT_ROOT)} — 请按实际持仓修正后再跑看板。")


def cmd_board():
    if not HOLDINGS_PATH.exists():
        print("未找到 monitor/holdings.json, 先跑 --init 生成模板并修正。")
        return
    with open(HOLDINGS_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    holds = cfg["holdings"]
    codes = [h["code"] for h in holds]
    rt = fetch_realtime_sina(codes)

    print("=" * 122)
    print(f"让赢家跑 — 移动止盈/止损看板  {TODAY}  (R6 让赢家跑 / R6b 保利)")
    print("=" * 122)
    print(f"{'标的':<10}{'档':<5}{'成本':>9}{'现价':>9}{'浮盈%':>8}{'建仓高':>9}{'回撤%':>8}"
          f"{'移动止盈':>10}{'距止盈%':>9}  {'动作'}")
    print("-" * 122)

    actions = []
    for h in holds:
        code = h["code"]
        kl = fetch_kline(code, start=h.get("entry_date", "2026-01-01"))
        cur = rt.get(code) or (kl[-1][2] if kl else None)
        if cur is None:
            print(f"{h['name']:<10}{h.get('tier',''):<5}  数据拉取失败")
            continue
        cost = h["cost"]
        tier = h.get("tier", "普通")
        trail = h.get("trail", DEFAULT_DRAWDOWN.get(tier, 0.18))
        peak = peak_since(kl, h.get("entry_date", "2026-01-01"), cur)
        pnl_pct = (cur / cost - 1) * 100
        dd_from_peak = (cur / peak - 1) * 100 if peak else 0.0
        trail_stop = peak * (1 - trail) if peak else None
        # 保利硬线: 移动止盈位不低于成本 (一旦浮盈, 锁保本)
        is_winner = cur > cost
        protect = max(trail_stop, cost) if (is_winner and trail_stop) else trail_stop
        dist_to_stop = (cur / protect - 1) * 100 if protect else None

        # 动作判定
        if not is_winner:
            act = "— (未浮盈, 走固定止损, 不适用移动止盈)"
        elif dd_from_peak <= -trail * 100:
            act = f"🔴 已回撤 ≥{trail*100:.0f}% → 减半 (趋势反转)"
        elif protect and protect >= cost and cur <= protect * 1.02:
            act = "🟡 逼近移动止盈位 → 盯紧, 破位减半"
        else:
            act = "🟢 让它跑 (默认持有, 不固定止盈)"
            actions.append(h["name"])

        stop_str = f"¥{protect:.2f}" if protect else "—"
        dist_str = f"{dist_to_stop:+.1f}%" if dist_to_stop is not None else "—"
        print(f"{h['name']:<10}{tier:<5}{cost:>9.2f}{cur:>9.2f}{pnl_pct:>+7.1f}%"
              f"{peak:>9.2f}{dd_from_peak:>+7.1f}%{stop_str:>10}{dist_str:>9}  {act}")

    print("-" * 122)
    print("规则 (R6 让赢家跑):")
    print("  • 赢家默认持有, 卖出门槛 > 买入门槛。只有 基本面证伪/估值>2.0/双极端超买需现金/超仓位上限 才减。")
    print("  • '涨了X%落袋' / '怕回吐' 不是减仓理由 (处置效应=亏钱根源)。")
    print("  • 移动止盈 = 从建仓最高点回撤阈值; 最高点上移→止盈位跟涨, 让利润奔跑。")
    print("  • 移动止盈位升到成本之上后 = 保本/保利硬线 (R6b)。")
    if actions:
        print(f"  • 当前'让它跑'的赢家: {', '.join(actions)} — 不要手痒兑现。")


def main():
    p = argparse.ArgumentParser(description="让赢家跑 — 移动止盈看板")
    p.add_argument("--init", action="store_true", help="生成 holdings.json 模板")
    args = p.parse_args()
    if args.init:
        cmd_init()
    else:
        cmd_board()


if __name__ == "__main__":
    main()

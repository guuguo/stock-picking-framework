#!/usr/bin/env python3
"""业绩记账 + 基准对比 (诚实台账)

目的: 回答唯一重要的问题 —— "这套框架到底有没有跑赢躺平?"
  不记反事实 ("避免了多少损失"), 只记真实净值 vs 基准.

数据源: 腾讯日K (历史) + 新浪实时 (当日), 纯 urllib, 无第三方依赖.

基准 (纸面对照组, 全自动):
  1. 沪深300  (sh000300)  — 宽基 beta
  2. 创业板指 (sz399006)  — 成长 beta
  3. 科创50   (sh000688)  — 你的 AI/半导体重仓敞口最接近的指数
  4. 冻结篮子 (可选)      — 起点持仓"买入并持有不动", 检验"折腾"是否创造价值

收益口径: 时间加权收益率 (TWR), 自动剔除入金/出金扰动.

用法:
  # 1. 同步一次持仓时记一笔 (盯盘/复盘/持仓同步都可)
  python3 scripts/core/track_performance.py add --date 2026-05-28 --assets 1084332 --cash 40145 --note "FII减500"

  # 2. 出报告 (打印 + 写入 monitor/performance_ledger.md)
  python3 scripts/core/track_performance.py report

  # 3. 当日实时记一笔 (date 缺省=今天, assets 必填)
  python3 scripts/core/track_performance.py add --assets 1090000
"""
import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MONITOR_DIR = PROJECT_ROOT / "monitor"
NAV_PATH = MONITOR_DIR / "nav_history.json"
LEDGER_PATH = MONITOR_DIR / "performance_ledger.md"

TODAY = date.today().isoformat()

DEFAULT_BENCHMARKS = {
    "sh000300": "沪深300",
    "sz399006": "创业板指",
    "sh000688": "科创50",
}


# ═══════════════════════════════════════════════════════════════
# 数据源
# ═══════════════════════════════════════════════════════════════
def fetch_kline_close_map(code, start="2026-04-01"):
    """腾讯日K -> {date: close}. 失败返回 {}。"""
    url = (
        f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
        f"param={code},day,{start},{TODAY},640,qfq"
    )
    try:
        raw = urllib.request.urlopen(url, timeout=12).read()
        node = json.loads(raw)["data"][code]
        kl = node.get("qfqday") or node.get("day") or []
        return {r[0]: float(r[2]) for r in kl}
    except Exception as e:
        print(f"  ⚠️ K线拉取失败 {code}: {type(e).__name__}: {str(e)[:60]}")
        return {}


def fetch_realtime_sina(codes):
    """新浪实时 -> {code: cur_price}. 失败返回 {}。"""
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
    except Exception as e:
        print(f"  ⚠️ 实时行情拉取失败: {type(e).__name__}")
    return out


def close_on_or_before(close_map, target_date):
    """取 target_date 当日收盘; 若是周末/节假日, 取之前最近交易日。"""
    if not close_map:
        return None
    if target_date in close_map:
        return close_map[target_date]
    candidates = [d for d in close_map if d <= target_date]
    if not candidates:
        return None
    return close_map[max(candidates)]


# ═══════════════════════════════════════════════════════════════
# 台账读写
# ═══════════════════════════════════════════════════════════════
def load_nav():
    if not NAV_PATH.exists():
        return {
            "inception": None,
            "benchmarks": DEFAULT_BENCHMARKS,
            "frozen_basket": None,
            "records": [],
        }
    with open(NAV_PATH, encoding="utf-8") as f:
        d = json.load(f)
    d.setdefault("benchmarks", DEFAULT_BENCHMARKS)
    d.setdefault("frozen_basket", None)
    d.setdefault("records", [])
    return d


def save_nav(d):
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    with open(NAV_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# add
# ═══════════════════════════════════════════════════════════════
def cmd_add(args):
    d = load_nav()
    rec = {
        "date": args.date or TODAY,
        "assets": round(float(args.assets), 2),
        "cash": round(float(args.cash), 2) if args.cash is not None else None,
        "net_flow": round(float(args.flow), 2),  # 入金为正, 出金为负
        "note": args.note or "",
    }
    # 同日覆盖
    d["records"] = [r for r in d["records"] if r["date"] != rec["date"]]
    d["records"].append(rec)
    d["records"].sort(key=lambda r: r["date"])
    if d.get("inception") is None:
        first = d["records"][0]
        d["inception"] = {"date": first["date"], "assets": first["assets"], "note": "首笔=起点"}
    save_nav(d)
    cash_str = f"¥{rec['cash']:,.0f}" if rec["cash"] is not None else "—"
    print(f"✅ 已记账: {rec['date']}  总资产 ¥{rec['assets']:,.0f}"
          f"  现金 {cash_str}"
          f"  净流入 ¥{rec['net_flow']:,.0f}")
    print(f"   累计 {len(d['records'])} 笔. 运行 report 看对比.")


# ═══════════════════════════════════════════════════════════════
# report
# ═══════════════════════════════════════════════════════════════
def compute_twr(records):
    """时间加权累计收益率序列 (剔除入金/出金)。
    返回与 records 等长的列表, 每个元素是"自起点至该笔"的累计收益率(%)。
    """
    cum = 1.0
    out = []
    prev_assets = None
    for r in records:
        if prev_assets is None:
            out.append(0.0)
        else:
            # 期间收益 = (期末 - 期间净流入) / 期初 - 1
            period = (r["assets"] - r["net_flow"]) / prev_assets - 1 if prev_assets else 0.0
            cum *= (1 + period)
            out.append((cum - 1) * 100)
        prev_assets = r["assets"]
    return out


def value_frozen_basket(basket, close_maps_basket, rt_basket, target_date, is_today):
    """给定日期, 冻结篮子的市值。"""
    total = basket.get("cash", 0) or 0
    for h in basket["holdings"]:
        # 现金占位 (如跨市场 HK 标的) 直接按固定值计入
        if h.get("cash_value") is not None and h.get("shares", 0) == 0:
            total += h["cash_value"]
            continue
        code = h["code"]
        if is_today and code in rt_basket and rt_basket[code] > 0:
            px = rt_basket[code]
        else:
            px = close_on_or_before(close_maps_basket.get(code, {}), target_date)
        if px is None:
            return None
        total += px * h["shares"]
    return total


def cmd_report(args):
    d = load_nav()
    records = d["records"]
    if len(records) < 1:
        print("台账为空. 先 add 一笔.")
        return
    benchmarks = d["benchmarks"]
    incep = records[0]
    incep_date = incep["date"]

    # 拉取基准 K线
    print("拉取基准数据...")
    close_maps = {code: fetch_kline_close_map(code) for code in benchmarks}
    last_date = records[-1]["date"]
    is_today_last = last_date == TODAY
    rt = fetch_realtime_sina(list(benchmarks)) if is_today_last else {}

    # 冻结篮子
    basket = d.get("frozen_basket")
    basket_maps, basket_rt = {}, {}
    if basket:
        codes = [h["code"] for h in basket["holdings"]
                 if h.get("cash_value") is None and h.get("shares", 0) != 0]
        basket_maps = {c: fetch_kline_close_map(c) for c in codes}
        basket_rt = fetch_realtime_sina(codes) if is_today_last else {}

    twr = compute_twr(records)

    def bench_ret(code, target_date, is_today):
        cm = close_maps.get(code, {})
        base = close_on_or_before(cm, incep_date)
        if base is None:
            return None
        if is_today and code in rt and rt[code] > 0:
            cur = rt[code]
        else:
            cur = close_on_or_before(cm, target_date)
        if cur is None:
            return None
        return (cur / base - 1) * 100

    # 冻结篮子起点市值
    basket_base = None
    if basket:
        basket_base = value_frozen_basket(basket, basket_maps, {}, incep_date, False)

    # 组装表
    lines = []
    lines.append("# 业绩台账 — 真实净值 vs 基准 (诚实对照)\n")
    lines.append(f"> 起点: {incep_date}  总资产 ¥{incep['assets']:,.0f}")
    lines.append(f"> 收益口径: 时间加权 (TWR), 已剔除入金/出金扰动")
    lines.append(f"> 基准: " + " / ".join(benchmarks.values()) +
                 (" / 冻结篮子(买入持有不动)" if basket else ""))
    lines.append(f"> 更新: {TODAY}  (运行 track_performance.py report 自动刷新)\n")

    # 主表: 每笔记录 自起点累计
    header = ["日期", "总资产", "我(TWR)"] + list(benchmarks.values())
    if basket:
        header.append("冻结篮子")
    header += ["最强基准", "超额α"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")

    latest_alpha = None
    for i, r in enumerate(records):
        is_today_rec = (r["date"] == TODAY)
        row = [r["date"], f"¥{r['assets']:,.0f}", f"{twr[i]:+.1f}%"]
        bench_vals = {}
        for code, bname in benchmarks.items():
            br = bench_ret(code, r["date"], is_today_rec)
            bench_vals[bname] = br
            row.append(f"{br:+.1f}%" if br is not None else "—")
        if basket:
            bv = value_frozen_basket(basket, basket_maps, basket_rt, r["date"], is_today_rec)
            if bv is not None and basket_base:
                br = (bv / basket_base - 1) * 100
                bench_vals["冻结篮子"] = br
                row.append(f"{br:+.1f}%")
            else:
                row.append("—")
        valid = {k: v for k, v in bench_vals.items() if v is not None}
        if valid:
            best_name = max(valid, key=valid.get)
            best_val = valid[best_name]
            alpha = twr[i] - best_val
            row.append(f"{best_name} {best_val:+.1f}%")
            row.append(f"{alpha:+.1f}pp")
            latest_alpha = (r["date"], alpha, best_name, best_val, twr[i])
        else:
            row.append("—")
            row.append("—")
        lines.append("| " + " | ".join(row) + " |")

    # 结论
    lines.append("\n## 当前结论\n")
    if latest_alpha:
        dt, alpha, bname, bval, mine = latest_alpha
        if alpha > 1:
            verdict = f"✅ 跑赢最强基准 ({bname}) {alpha:+.1f}pp — 框架目前创造了正超额."
        elif alpha < -1:
            verdict = (f"🔴 跑输最强基准 ({bname}) {alpha:+.1f}pp — "
                       f"截至 {dt}, 折腾不如直接买 {bname}. 这是框架要解决的核心问题.")
        else:
            verdict = f"⚪ 与最强基准 ({bname}) 基本持平 (差 {alpha:+.1f}pp) — 框架暂未证明 alpha."
        lines.append(f"- {verdict}")
        lines.append(f"- 我 {mine:+.1f}%  vs  {bname} {bval:+.1f}%  (截至 {dt})")
    lines.append("\n## 诚实记账纪律\n")
    lines.append("- 只记真实净值, 不记 \"避免了多少损失\" 这种反事实.")
    lines.append("- 错过的大涨 (中际/兆易等) 与避开的坑, 归因时两边都要算, 不许只记一边.")
    lines.append("- 连续 3 个月跑不赢最强基准 → 严肃讨论是否降低主动操作、转配置 ETF.")

    report_text = "\n".join(lines) + "\n"
    MONITOR_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("\n" + report_text)
    print(f"📝 已写入 {LEDGER_PATH.relative_to(PROJECT_ROOT)}")


# ═══════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser(description="业绩记账 + 基准对比")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="记一笔净值")
    pa.add_argument("--date", default=None, help="日期 YYYY-MM-DD, 缺省=今天")
    pa.add_argument("--assets", required=True, help="账户总资产 (元)")
    pa.add_argument("--cash", default=None, help="可用现金 (元, 可选)")
    pa.add_argument("--flow", default=0, help="自上一笔以来净入金 (元, 出金为负, 默认 0)")
    pa.add_argument("--note", default=None, help="备注")
    pa.set_defaults(func=cmd_add)

    pr = sub.add_parser("report", help="出报告 + 写 ledger")
    pr.set_defaults(func=cmd_report)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

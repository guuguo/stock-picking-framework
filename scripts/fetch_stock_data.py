#!/usr/bin/env python3
"""V14.3 SOP: 通用股票全维度数据抓取脚本

替代:
  - fetch_pinggao_data.py (600312)
  - fetch_longi_data.py   (601012)
  - (未来所有 fetch_<name>_data.py 的合并)

用法:
  python3 scripts/fetch_stock_data.py 600312
  python3 scripts/fetch_stock_data.py 601012 --start 20260420 --end 20260512
  python3 scripts/fetch_stock_data.py 002230 --peers 300223,688256,603019
  python3 scripts/fetch_stock_data.py 300442 --no-peers  # 跳过同行对比
  python3 scripts/fetch_stock_data.py 600312 --periods 12  # 拉 12 期利润表

新增标的: 编辑 scripts/stocks_config.json 添加 peers 列表, 无需改脚本.
"""
import argparse
import json
import time
from pathlib import Path

import akshare as ak
import pandas as pd

# ===== 路径常量 =====
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_PATH = SCRIPT_DIR / "stocks_config.json"
DATA_DIR = PROJECT_ROOT / "data"


# ===== 工具函数 =====
def market_prefix(ticker: str) -> str:
    """根据股票代码自动识别市场前缀 (SH/SZ/BJ)"""
    if ticker.startswith(("6", "9")):
        return "SH"
    if ticker.startswith(("0", "2", "3")):
        return "SZ"
    if ticker.startswith(("4", "8")):
        return "BJ"
    return "SH"


def retry(fn, max_n: int = 3, sleep: float = 3.0, tag: str = ""):
    """通用重试 (网络波动 / akshare RemoteDisconnect)"""
    for i in range(max_n):
        try:
            return fn()
        except Exception as e:
            print(f"  [{tag}] 重试 {i + 1}/{max_n}: {type(e).__name__}: {str(e)[:80]}")
            if i < max_n - 1:
                time.sleep(sleep)
    return None


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fmt_section(title: str):
    print(f"\n{'=' * 80}\n{title}\n{'=' * 80}")


# ===== 6 个抓取维度 =====
def fetch_basic_info(ticker: str):
    fmt_section(f"【1】基础行情信息 {ticker}")
    info = retry(lambda: ak.stock_individual_info_em(symbol=ticker), tag="basic_info")
    if info is not None:
        print(info.to_string(index=False))


def fetch_recent_quotes(ticker: str, start: str, end: str):
    fmt_section(f"【2】最近交易日行情 {start} ~ {end}")
    df = retry(
        lambda: ak.stock_zh_a_hist(symbol=ticker, period="daily", start_date=start, end_date=end, adjust=""),
        tag="hist",
    )
    if df is not None and len(df) > 0:
        print(df.tail(10).to_string(index=False))


def restore_single_quarter(profit, periods: int = 8):
    """累计 YTD → 单季还原 (维度 1.1 强制步骤, 防累计/单季口径错误).
    规则: 单季 Qn = 累计(Qn) - 同年累计(Qn-1); Q1 本身即单季.
    输出: 单季营收/归母/扣非 + 单季 yoy(同季比) + 单季 qoq(环比).
    """
    fmt_section("【3.1】单季还原 (维度 1.1 强制) — 增速结论必须基于单季, 不用累计")
    cols = {
        "REPORT_DATE": "日期",
        "TOTAL_OPERATE_INCOME": "营收",
        "PARENT_NETPROFIT": "归母",
        "DEDUCT_PARENT_NETPROFIT": "扣非",
    }
    avail = [c for c in cols if c in profit.columns]
    df = profit[avail].head(periods + 5).copy()
    for c in avail:
        if c != "REPORT_DATE":
            df[c] = df[c].astype(float) / 1e8
    df["_y"] = df["REPORT_DATE"].str[:4]
    df["_m"] = df["REPORT_DATE"].str[5:7]
    df = df.sort_values("REPORT_DATE").reset_index(drop=True)

    rows = []
    for _, r in df.iterrows():
        rec = {"日期": r["REPORT_DATE"][:10]}
        for src, name in cols.items():
            if src == "REPORT_DATE" or src not in df.columns:
                continue
            cum = r[src]
            if r["_m"] == "03":
                sq = cum
            else:
                prev = df[(df["_y"] == r["_y"]) & (df["REPORT_DATE"] < r["REPORT_DATE"])]
                sq = cum - prev.iloc[-1][src] if len(prev) > 0 else None
            rec[name] = round(sq, 2) if sq is not None else None
        rows.append(rec)

    sq_df = pd.DataFrame(rows).tail(periods).reset_index(drop=True)
    for base in ["营收", "归母", "扣非"]:
        if base not in sq_df.columns:
            continue
        vals = sq_df[base].tolist()
        yoy, qoq = [], []
        for i in range(len(vals)):
            v = vals[i]
            vy = vals[i - 4] if i >= 4 else None
            vq = vals[i - 1] if i >= 1 else None
            yoy.append(f"{(v/vy-1)*100:+.0f}%" if (v is not None and vy not in (None, 0) and vy > 0) else "—")
            qoq.append(f"{(v/vq-1)*100:+.0f}%" if (v is not None and vq not in (None, 0) and vq > 0) else "—")
        sq_df[base + "yoy"] = yoy
        sq_df[base + "qoq"] = qoq
    print(sq_df.to_string(index=False))
    print("\n⚠️ 维度1.1: 任何'失速/腰斩/加速'结论必须基于上表单季数列, 不许凭印象。TTM = 最近4单季之和。")
    return sq_df


def fetch_profit_sheet(ticker: str, periods: int = 10, single_quarter: bool = True):
    fmt_section(f"【3】利润表最近 {periods} 期 (亿元, 累计YTD口径)")
    mkt = market_prefix(ticker)
    profit = retry(lambda: ak.stock_profit_sheet_by_report_em(symbol=f"{mkt}{ticker}"), tag="profit")
    if profit is None or len(profit) == 0:
        return None
    cols = [
        "REPORT_DATE",
        "TOTAL_OPERATE_INCOME",
        "OPERATE_PROFIT",
        "TOTAL_PROFIT",
        "PARENT_NETPROFIT",
        "DEDUCT_PARENT_NETPROFIT",
    ]
    avail = [c for c in cols if c in profit.columns]
    sub = profit[avail].head(periods).copy()
    for c in avail[1:]:
        sub[c] = (sub[c].astype(float) / 1e8).round(2)
    print(sub.to_string(index=False))
    if single_quarter:
        try:
            restore_single_quarter(profit, periods=min(periods, 8))
        except Exception as e:
            print(f"  [单季还原] 失败: {type(e).__name__}: {str(e)[:60]} (手动还原)")
    return profit


def fetch_balance_sheet(ticker: str, periods: int = 8):
    fmt_section(f"【4】资产负债表最近 {periods} 期 (亿元) - 含合同负债 / 应收 / 存货")
    mkt = market_prefix(ticker)
    bs = retry(lambda: ak.stock_balance_sheet_by_report_em(symbol=f"{mkt}{ticker}"), tag="balance")
    if bs is None or len(bs) == 0:
        return None
    cols = [
        "REPORT_DATE",
        "TOTAL_ASSETS",
        "TOTAL_LIABILITIES",
        "CONTRACT_LIAB",
        "ACCOUNTS_RECE",
        "INVENTORY",
        "FIXED_ASSET",
        "CIP",
    ]
    avail = [c for c in cols if c in bs.columns]
    sub = bs[avail].head(periods).copy()
    for c in avail[1:]:
        sub[c] = (sub[c].astype(float) / 1e8).round(2)
    print(sub.to_string(index=False))
    return bs


def fetch_research_reports(ticker: str, name: str, top_n: int = 15):
    fmt_section(f"【5】券商研报列表 (近 12 个月) - 维度 0 R14 bottom-up")
    rep = retry(lambda: ak.stock_research_report_em(symbol=ticker), tag="reports")
    if rep is None or len(rep) == 0:
        print("  无券商研报数据")
        return None
    print(f"覆盖券商: {len(rep)} 份")
    cols = [
        "报告日期",
        "机构名称",
        "报告名称",
        "2026-盈利预测-收益",
        "2027-盈利预测-收益",
        "2028-盈利预测-收益",
        "报告PDF链接",
    ]
    avail = [c for c in cols if c in rep.columns]
    print(rep[avail].head(top_n).to_string(index=False))
    # 保存到 data/<ticker>_reports.csv
    out = DATA_DIR / f"{ticker}_reports.csv"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rep.to_csv(out, index=False)
    print(f"\n已保存全量研报列表 → {out.relative_to(PROJECT_ROOT)}")
    return rep


def fetch_peer_alpha(peers: list, num_periods: int = 5):
    """同行 Q1 alpha 横向对比 (R15)
    peers: [[code, name], ...]
    """
    fmt_section(f"【6】同行 Q1 横向 alpha 对比 (R15) - {len(peers)} 个标的, 最近 {num_periods} 期")
    rows = []
    for code, name in peers:
        mkt = market_prefix(code)
        p = retry(
            lambda c=code, m=mkt: ak.stock_profit_sheet_by_report_em(symbol=f"{m}{c}"),
            max_n=2,
            sleep=2,
            tag=f"peer_{code}",
        )
        if p is None or len(p) == 0:
            rows.append({"代码": code, "名称": name, "状态": "拉取失败"})
            continue
        row = {"代码": code, "名称": name}
        for i in range(min(num_periods, len(p))):
            date_ = p.iloc[i].get("REPORT_DATE", "")[:10] if "REPORT_DATE" in p.columns else "NA"
            inc = float(p.iloc[i].get("TOTAL_OPERATE_INCOME", 0) or 0) / 1e8
            np_ = float(p.iloc[i].get("PARENT_NETPROFIT", 0) or 0) / 1e8
            row[f"期{i}"] = f"{date_} 营{inc:.1f}/利{np_:.2f}"
        rows.append(row)

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    return df


# ===== 主入口 =====
def parse_args():
    p = argparse.ArgumentParser(
        description="V14.3 通用股票全维度数据抓取",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("ticker", help="股票代码 (e.g. 600312, 601012, 300442)")
    p.add_argument("--name", default=None, help="标的中文名 (默认从 stocks_config.json 读)")
    p.add_argument("--start", default="20260420", help="行情起始日 YYYYMMDD")
    p.add_argument("--end", default="20260512", help="行情结束日 YYYYMMDD")
    p.add_argument("--periods", type=int, default=10, help="利润表/资产负债表期数")
    p.add_argument("--reports-top", type=int, default=15, help="研报列表显示前 N 条")
    p.add_argument(
        "--peers",
        default=None,
        help="同行代码逗号分隔 (e.g. 600438,002129,002459), 默认从配置读取",
    )
    p.add_argument("--no-peers", action="store_true", help="跳过同行 alpha 对比")
    p.add_argument(
        "--skip",
        default="",
        help="跳过模块, 逗号分隔: basic,quotes,profit,balance,reports,peers",
    )
    return p.parse_args()


def resolve_peers(ticker: str, name: str, args, config: dict):
    """优先级: --peers 命令行 > stocks_config.json > 仅自身"""
    if args.peers:
        return [[c.strip(), c.strip()] for c in args.peers.split(",") if c.strip()]
    if ticker in config and "peers" in config[ticker]:
        return config[ticker]["peers"]
    return [[ticker, name]]


def main():
    args = parse_args()
    config = load_config()
    ticker = args.ticker.strip()
    name = args.name or (config.get(ticker, {}).get("name") or ticker)
    sector = config.get(ticker, {}).get("sector", "未分类")
    skip = set(s.strip() for s in args.skip.split(",") if s.strip())

    print(f"\n{'#' * 80}")
    print(f"# V14.3 全维度抓取: {name} ({ticker})  |  主线: {sector}")
    print(f"# 行情区间: {args.start} ~ {args.end}  |  期数: {args.periods}")
    print(f"{'#' * 80}")

    if "basic" not in skip:
        fetch_basic_info(ticker)
    if "quotes" not in skip:
        fetch_recent_quotes(ticker, args.start, args.end)
    if "profit" not in skip:
        fetch_profit_sheet(ticker, args.periods)
    if "balance" not in skip:
        fetch_balance_sheet(ticker, min(args.periods, 8))
    if "reports" not in skip:
        fetch_research_reports(ticker, name, args.reports_top)

    if not args.no_peers and "peers" not in skip:
        peers = resolve_peers(ticker, name, args, config)
        if len(peers) > 1:
            fetch_peer_alpha(peers)
        else:
            print(f"\n  跳过同行对比 (peers 列表仅自身, 请在 stocks_config.json 配置或用 --peers)")

    print(f"\n{'#' * 80}\n# 抓取完成: {name} ({ticker})\n{'#' * 80}\n")


if __name__ == "__main__":
    main()

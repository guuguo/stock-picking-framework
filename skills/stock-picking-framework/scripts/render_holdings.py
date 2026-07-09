#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""持仓单一真相源渲染器 — data/holdings.json 是唯一真相, 此脚本派生其余所有持仓表。

设计 (2026-06-25, 根治多份手维护漂移):
  唯一真相源 = STOCK_ROOT/data/holdings.json (agent 成交/评分/止损/缠论 只改这一个文件)
  跑本脚本 → 自动产出 daily_playbook.md 的 4 个标记块 + winners_guard json:
    HOLDINGS  持仓明细 (带腾讯实时价快照)
    STOPLOSS  入价证伪止损 P0
    TRAILING  移动止盈 P1 (带实时浮盈)
    CHANLUN   缠论结构关键位
    monitor/holdings.json  winners_guard 精简 subset
  → agent 只改一处, 不再人肉同步多份, 杜绝漂移(尤其止损价绝不留第二份会过期的)。

现价/涨跌/浮盈/仓位% 不存 json, 渲染时拉腾讯算 + 标"截至 HH:MM"快照。

用法 (STOCK_ROOT 下, 或 --root):
  python3 render_holdings.py            # 拉实时价 → 写 4 块 + winners_guard json
  python3 render_holdings.py --no-price # 离线(不拉价)
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.request

M = {
    "HOLDINGS": ("<!-- HOLDINGS:START 自动生成,勿手改;改 data/holdings.json 后跑 scripts/render_holdings.py -->",
                 "<!-- HOLDINGS:END -->", r"(##\s*一、持仓明细[^\n]*\n)"),
    "STOPLOSS": ("<!-- STOPLOSS:START 自动生成,勿手改;源 data/holdings.json -->",
                 "<!-- STOPLOSS:END -->", r"(###\s*入价证伪止损[^\n]*\n)"),
    "TRAILING": ("<!-- TRAILING:START 自动生成,勿手改;源 data/holdings.json -->",
                 "<!-- TRAILING:END -->", r"(###\s*移动止盈[^\n]*\n)"),
    "CHANLUN":  ("<!-- CHANLUN:START 自动生成,勿手改;源 data/holdings.json -->",
                 "<!-- CHANLUN:END -->", r"(##\s*二·五、缠论结构关键位[^\n]*\n)"),
}


def find_root(arg):
    if arg:
        return arg
    cfg = os.path.expanduser("~/.config/stock-picking/config.json")
    if os.path.isfile(cfg):
        try:
            r = json.load(open(cfg, encoding="utf-8")).get("stock_root")
            if r and os.path.isdir(r):
                return r
        except Exception:
            pass
    return os.getcwd()


def prefix(code):
    return ("sh" if code[0] in "69" else ("bj" if code[0] == "8" else "sz")) + code


def tencent(codes):
    try:
        u = "https://qt.gtimg.cn/q=" + ",".join(prefix(c) for c in codes)
        rq = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(rq, timeout=10).read().decode("gbk")
    except Exception as e:
        print(f"[warn] 拉腾讯价失败, 退化为无价: {e}", file=sys.stderr)
        return {}
    out = {}
    for line in data.split(";"):
        if '"' not in line:
            continue
        v = line.split('"')[1].split("~")
        if len(v) > 32:
            out[v[2]] = {"price": float(v[3]) if v[3] else 0}
    return out


def render_holdings(hj, px, now):
    h, ta, cash = hj["holdings"], hj.get("total_assets") or 0, hj.get("cash") or 0
    cash_pct = (cash / ta * 100) if ta else 0
    head = (f"**持仓 {len(h)} 只** | 现金 ~¥{cash/1e4:.1f}万(~{cash_pct:.1f}%) | "
            f"总资产 ~¥{ta/1e4:.1f}万 | 截至 {now:%Y-%m-%d %H:%M} (现价/浮盈为腾讯快照, 实时以盯盘为准)")
    rows = ["| 标的 | 持仓 | 成本 | 现价 | 浮盈% | 仓位% | 目标 | 评分 | 止损 | 主线 | 进度 |",
            "|------|---:|---:|---:|---:|---:|---:|:--:|---:|------|------|"]
    for x in h:
        p = px.get(x["code"], {}).get("price", 0)
        cur = f"{p:.2f}" if p else "—"
        pnl = f"{(p/x['cost']-1)*100:+.1f}%" if p else "—"
        pos = f"{x['shares']*p/ta*100:.1f}%" if (p and ta) else "—"
        sl = (x.get("stoploss") or {}).get("price", "")
        rows.append(f"| **{x['name']} {x['code']}** | {x['shares']:,} | {x['cost']} | {cur} | {pnl} | {pos} | "
                    f"{x.get('target_pct','')}% | {x.get('score','')} | {sl} | {x.get('mainline','')} | {x.get('进度','')} |")
    return "\n".join([head, ""] + rows)


def render_stoploss(hj):
    rows = ["> P0 永不撤销, 跌破机械砍。源 data/holdings.json。",
            "", "| 标的 | 持仓 | 证伪价 | 证伪卖量 | 逻辑 |", "|------|---:|---:|---:|------|"]
    for x in hj["holdings"]:
        s = x.get("stoploss")
        if not s:
            continue
        rows.append(f"| **{x['name']} {x['code']}** | {x['shares']:,} | **¥{s.get('price')}** | {s.get('qty','')} | {s.get('logic','')} |")
    return "\n".join(rows)


def render_trailing(hj, px):
    rows = ["> P1 保护利润, 触发后手动减(非条件单)。浮盈为腾讯快照。源 data/holdings.json。",
            "", "| 标的 | 浮盈 | 触发价 | 减仓 | 剩余 | 逻辑 |", "|------|------|---:|---:|---:|------|"]
    for x in hj["holdings"]:
        t = x.get("trailing")
        if not t:
            continue
        p = px.get(x["code"], {}).get("price", 0)
        pnl = f"{(p/x['cost']-1)*100:+.1f}%" if p else "—"
        rows.append(f"| **{x['name']}** | {pnl} | **¥{t.get('trigger')}** | -{t.get('qty','')} | {t.get('left','')} | {t.get('logic','')} |")
    return "\n".join(rows)


def render_chanlun(hj):
    rows = ["> 缠论买卖点+中枢, 跨天有效, 结构变化才改 json。源 data/holdings.json。",
            "", "| 标的 | 一买 | 二买 | 中枢 | 当前位置 | 上方压力 | 止损/失效 |",
            "|------|---:|---:|------|------|------|---:|"]
    for x in hj["holdings"]:
        c = x.get("chanlun") or {}
        rows.append(f"| {x['name']} | {c.get('一买','—')} | {c.get('二买','—')} | {c.get('中枢','—')} | "
                    f"{c.get('位置','')} | {c.get('压力','')} | {c.get('失效','')} |")
    return "\n".join(rows)


def write_block(txt, key, body):
    start, end, after = M[key]
    block = f"{start}\n\n{body}\n\n{end}"
    if start in txt and end in txt:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: block, txt, flags=re.S)
    m = re.search(after, txt)
    if not m:
        raise SystemExit(f"{key}: 无标记也无标题锚点({after}), 无法插入。")
    return txt[:m.end()] + "\n" + block + "\n" + txt[m.end():]


def write_winners_guard(js_path, hj, now):
    out = {"note": f"由 data/holdings.json 经 render_holdings.py 自动生成 ({now:%Y-%m-%d %H:%M}), 勿手改。",
           "last_sync": now.strftime("%Y-%m-%d"),
           "holdings": [{"name": x["name"], "code": prefix(x["code"]), "tier": x.get("tier", "普通"),
                         "shares": x["shares"], "cost": x["cost"], "entry_date": x.get("entry_date", "")}
                        for x in hj["holdings"]]}
    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    json.dump(out, open(js_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description="持仓真相源渲染器")
    ap.add_argument("--root")
    ap.add_argument("--no-price", action="store_true")
    a = ap.parse_args(argv)
    root = find_root(a.root)
    src = os.path.join(root, "data", "holdings.json")
    pb = os.path.join(root, "daily_playbook.md")
    if not os.path.isfile(src):
        print(f"找不到真相源 {src}", file=sys.stderr)
        return 2
    hj = json.load(open(src, encoding="utf-8"))
    now = _dt.datetime.now()
    px = {} if a.no_price else tencent([x["code"] for x in hj["holdings"]])
    txt = open(pb, encoding="utf-8").read()
    txt = write_block(txt, "HOLDINGS", render_holdings(hj, px, now))
    txt = write_block(txt, "STOPLOSS", render_stoploss(hj))
    txt = write_block(txt, "TRAILING", render_trailing(hj, px))
    txt = write_block(txt, "CHANLUN", render_chanlun(hj))
    open(pb, "w", encoding="utf-8").write(txt)
    write_winners_guard(os.path.join(root, "monitor", "holdings.json"), hj, now)
    print(f"✅ 已从 data/holdings.json 渲染 4 块 (现价快照 {'拉到' if px else '无'}) + winners_guard json: {len(hj['holdings'])} 只")
    return 0


if __name__ == "__main__":
    sys.exit(main())

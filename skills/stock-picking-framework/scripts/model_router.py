#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型路由模块 — 把框架子任务派给最合适的模型 (claude / dsclaude / codex)。

设计 (贴合框架"按需加载 + 优雅退化"气质):
  · 按需启用: 只有"宿主是 claude 且 dsclaude/codex 至少一个可用"才启用多模型路由。
  · 优雅退化: 缺模型 → 自动退回纯 claude, 框架行为完全不变, 绝不报错挡路。
  · 探测缓存: 结果存 ~/.config/stock-picking/model_routing.json, 默认 TTL 7 天, 过期自动重探。
  · 路由表 v2 (2026-06-25 去偏): 真实历史题证明推理/计算/判断三家平价, 旧"按能力排除 dsclaude"作废;
    唯一真差距是信息采集(claude 有工具最强)。采→claude(深研+dsclaude WebSearch); 想/算/判→默认claude, 深研判断块双跑; codex 可选第三票。
  · router 只做"路由+派发+收集"; 自包含 prompt 由主 agent 构造 (dsclaude 隔离无技能, 必须把规则喂进去)。

零外部依赖, 纯标准库。

子命令:
  probe [--deep] [--force]   探测环境并缓存 (默认只查存在性; --deep 真实 ping 每个模型一次)
  status                     打印当前可用性 + 是否启用路由 (缓存过期会自动浅探)
  list                       列出所有已知任务及其路由
  route <task>               查某任务派给谁 (solo/ensemble), 不执行
  run <task> --in FILE       派活: 对自包含 prompt 跑指定模型, 输出落盘; ensemble 返回多份供综合
                             (FILE 用 - 表示从 stdin 读)

示例:
  python3 scripts/model_router.py status
  python3 scripts/model_router.py route next_quarter_nowcast
  python3 scripts/model_router.py run single_quarter_restate --in /tmp/payload.txt
"""

import argparse
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
CFG_DIR = os.path.join(HOME, ".config", "stock-picking")
CACHE = os.path.join(CFG_DIR, "model_routing.json")
TTL_DAYS = 7
CALL_TIMEOUT = 300  # 单个模型调用超时(秒)

# ---------------------------------------------------------------------------
# 路由表 (任务 -> 类别/模式/理想模型)。category 决定退化时的回退优先级。
# mode: solo = 派一个最强; ensemble = 多模型跑后主 agent 综合 (分歧=不确定性)。
# 依据 pilot 7 块实测: claude9.7 / codex8.9 / dsclaude7.9, 详见 SCORECARD.md。
# ---------------------------------------------------------------------------
TASKS = {
    # ① 数据采集 (唯一真有差距的层 = 工具/水管)
    "data_fetch":       ("gather", "solo",     ["claude"],             "正常查数: 股价/财报/估值 (claude 有工具采得全, 总/流通市值都分得清)"),
    "data_fetch_deep":  ("gather", "ensemble", ["claude", "dsclaude"], "深研采数: claude 主采 + dsclaude WebSearch 补公告原文链接/小道消息/交叉验证"),
    # ② 计算/结构 (真实题证明三家平价 -> 默认 claude, 需要时再交叉)
    "single_quarter_restate": ("compute", "solo", ["claude"], "累计→单季还原 / TTM / yoy / qoq"),
    "pe_recompute":           ("compute", "solo", ["claude"], "估值重算 PE/PB/PEG"),
    "earnings_stripping":     ("compute", "solo", ["claude"], "扣非 / 剔除非经常 / 真实业绩剥离 (会计幻觉过滤器)"),
    "fractal_pivot":          ("compute", "solo", ["claude"], "缠论 包含/分型/笔/中枢 (惯例敏感, 争议项人工定标准)"),
    # ③ 高价值判断 (深研双跑, 分歧=不确定性)
    "mainline_attribution":  ("judge", "ensemble", ["claude", "dsclaude"], "主线归属 (表面vs实质)"),
    "next_quarter_nowcast":  ("judge", "ensemble", ["claude", "dsclaude"], "预研 / 下一季前瞻 / 预期差"),
    "catalyst_cluster":      ("judge", "ensemble", ["claude", "dsclaude"], "催化集群 / 政策题材"),
    "peer_alpha":            ("judge", "ensemble", ["claude", "dsclaude"], "同行 alpha/beta 判定"),
    "info_discernment":      ("judge", "ensemble", ["claude", "dsclaude"], "信息甄别 (小道消息/合同/财报细节 可参考性)"),
    "chan_bsp_div_level":    ("judge", "ensemble", ["claude", "dsclaude"], "缠论 背驰/买卖点/级别联立"),
    "growth_sustainability": ("judge", "ensemble", ["claude", "dsclaude"], "增速可持续性 7 步"),
    # ④ 综合/打分/裁判 -> claude 收口
    "synthesis_decision":    ("synth", "solo", ["claude"], "8维打分 / 三档概率 / 仓位决策 / 综合归纳"),
}

# 退化/扩充回退 (理想不可用按序找替补; claude 永远兜底; codex 仅作可选第三票, 不进默认采集/判断)
FALLBACK = {
    "gather":  ["claude", "dsclaude"],            # codex 沙箱采集不可靠(连不上腾讯/通达信), 不入采集
    "compute": ["claude", "dsclaude", "codex"],
    "judge":   ["claude", "dsclaude", "codex"],
    "synth":   ["claude"],
}


def _now():
    return _dt.datetime.now()


def _load_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_cache(data):
    os.makedirs(CFG_DIR, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _stale(cache):
    if not cache or "probed_at" not in cache:
        return True
    try:
        t = _dt.datetime.fromisoformat(cache["probed_at"])
        return (_now() - t).days >= cache.get("ttl_days", TTL_DAYS)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# 探测
# ---------------------------------------------------------------------------
def _dsclaude_bin():
    p = shutil.which("dsclaude")
    if p:
        return p
    cand = os.path.join(HOME, ".local", "bin", "dsclaude")
    return cand if os.path.isfile(cand) else None


def _discover_codex_home():
    h = os.environ.get("CODEX_HOME")
    if h and os.path.isdir(os.path.expanduser(h)):
        return os.path.expanduser(h)
    try:
        txt = open(os.path.join(HOME, ".zshrc"), encoding="utf-8").read()
        m = re.search(r'alias\s+codex-work=.*?CODEX_HOME="([^"]+)"', txt)
        if m:
            p = os.path.expanduser(m.group(1))
            if os.path.isdir(p):
                return p
    except Exception:
        pass
    d = os.path.join(HOME, ".codex")
    return d if os.path.isdir(d) else None


def _ping(model, inv):
    try:
        r = subprocess.run(inv["cmd"], env=inv.get("env"), stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "") + (r.stderr or "")
        return "PONG" in out.upper() or "ok" in out.lower(), out[-200:]
    except Exception as e:
        return False, str(e)


def probe(deep=False):
    host_is_claude = bool(os.environ.get("CLAUDECODE") or shutil.which("claude"))
    models = {}

    # claude (宿主)
    models["claude"] = {"available": bool(shutil.which("claude")), "how": "host"}

    # dsclaude
    db = _dsclaude_bin()
    creds = os.path.isfile(os.path.join(HOME, ".config", "dsclaude", "env"))
    ds_ok = bool(db) and creds
    models["dsclaude"] = {"available": ds_ok, "bin": db, "creds": creds, "model": "deepseek-v4-pro"}

    # codex
    cb = shutil.which("codex")
    ch = _discover_codex_home()
    cx_ok = bool(cb) and bool(ch) and os.path.isfile(os.path.join(ch, "auth.json")) if ch else False
    models["codex"] = {"available": cx_ok, "bin": cb, "codex_home": ch, "model": "gpt-5.5"}

    if deep:
        for m in ("dsclaude", "codex"):
            if models[m]["available"]:
                inv = _build_inv(m, "只回复一个词: PONG", models)
                ok, tail = _ping(m, inv)
                models[m]["ping_ok"] = ok
                models[m]["available"] = ok
                models[m]["ping_tail"] = tail

    extras = [m for m in ("dsclaude", "codex") if models[m]["available"]]
    cache = {
        "probed_at": _now().isoformat(timespec="seconds"),
        "ttl_days": TTL_DAYS,
        "host_is_claude": host_is_claude,
        "models": models,
        "routing_enabled": bool(host_is_claude and extras),
        "extras_available": extras,
    }
    _save_cache(cache)
    return cache


def _ensure(deep=False, force=False):
    cache = _load_cache()
    if force or _stale(cache):
        cache = probe(deep=deep)
    return cache


# ---------------------------------------------------------------------------
# 派发
# ---------------------------------------------------------------------------
def _build_inv(model, prompt, models):
    if model == "claude":
        return {"cmd": ["claude", "-p", prompt], "env": None}
    if model == "dsclaude":
        b = models["dsclaude"].get("bin") or _dsclaude_bin()
        return {"cmd": [b, "-p", prompt], "env": None}
    if model == "codex":
        ch = models["codex"].get("codex_home") or _discover_codex_home()
        env = dict(os.environ)
        if ch:
            env["CODEX_HOME"] = ch
        return {"cmd": ["codex", "exec", "--skip-git-repo-check", prompt], "env": env}
    raise ValueError(model)


def _extract_codex(text):
    # codex exec 会打印 session header + "codex\n<答案>\ntokens used\n<n>\n<答案重复>"
    # 取最后一段 codex 输出, 去掉 tokens 行
    parts = re.split(r'\n\s*codex\s*\n', text)
    ans = parts[-1] if len(parts) > 1 else text
    ans = re.split(r'\n\s*tokens used\s*\n', ans)[0]
    return ans.strip()


def resolve(task, cache):
    if task not in TASKS:
        raise SystemExit("未知任务: %s\n可用: %s" % (task, ", ".join(TASKS)))
    cat, mode, ideal, _ = TASKS[task]
    avail = {m: cache["models"][m]["available"] for m in cache["models"]}
    if not cache.get("routing_enabled"):
        return ("solo", ["claude"], cat)  # 退化: 全交 claude
    if mode == "solo":
        for m in ideal + FALLBACK[cat]:
            if avail.get(m):
                return ("solo", [m], cat)
        return ("solo", ["claude"], cat)
    # ensemble
    members = [m for m in ideal if avail.get(m)]
    if "claude" not in members and avail.get("claude"):
        members.append("claude")
    if not members:
        members = ["claude"]
    return (("ensemble" if len(members) > 1 else "solo"), members, cat)


def run_task(task, prompt, cache):
    mode, models, cat = resolve(task, cache)
    out_dir = _out_dir()
    os.makedirs(out_dir, exist_ok=True)
    results = {}
    for m in models:
        inv = _build_inv(m, prompt, cache["models"])
        try:
            r = subprocess.run(inv["cmd"], env=inv.get("env"), stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=CALL_TIMEOUT)
            raw = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.returncode else "")
            ans = _extract_codex(raw) if m == "codex" else raw.strip()
        except subprocess.TimeoutExpired:
            ans = "[TIMEOUT %ds]" % CALL_TIMEOUT
        except Exception as e:
            ans = "[ERROR] %s" % e
        path = os.path.join(out_dir, "%s.%s.txt" % (task, m))
        with open(path, "w", encoding="utf-8") as f:
            f.write(ans)
        results[m] = {"path": path, "chars": len(ans)}
    return mode, models, cat, results, out_dir


def _out_dir():
    cfg = os.path.join(CFG_DIR, "config.json")
    try:
        root = json.load(open(cfg, encoding="utf-8")).get("stock_root")
        if root and os.path.isdir(root):
            return os.path.join(root, ".model_router")
    except Exception:
        pass
    return os.path.join(CFG_DIR, "router_out")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_status(cache):
    en = cache.get("routing_enabled")
    print("路由启用: %s   (宿主claude=%s, 探测于 %s)" % (
        "✅ 是" if en else "❌ 否(退化为纯claude)", cache.get("host_is_claude"), cache.get("probed_at")))
    for m, d in cache["models"].items():
        flag = "✅" if d.get("available") else "—"
        extra = d.get("model", d.get("how", ""))
        print("  %s %-9s %s" % (flag, m, extra))
    if not en:
        print("\n→ 缺 dsclaude/codex, 所有任务自动交 claude 单跑 (框架行为不变)。")


def main(argv=None):
    ap = argparse.ArgumentParser(description="模型路由模块")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("probe"); p.add_argument("--deep", action="store_true"); p.add_argument("--force", action="store_true")
    sub.add_parser("status")
    sub.add_parser("list")
    pr = sub.add_parser("route"); pr.add_argument("task")
    rn = sub.add_parser("run"); rn.add_argument("task"); rn.add_argument("--in", dest="infile", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "probe":
        _print_status(probe(deep=a.deep)); return
    if a.cmd == "status":
        _print_status(_ensure()); return
    if a.cmd == "list":
        print("任务路由表 v2 (去偏: 三家推理平价; 采数据看工具→claude; codex 仅可选第三票):\n")
        for t, (cat, mode, ideal, desc) in TASKS.items():
            print("  %-24s %-13s %-9s %-22s %s" % (t, cat, mode, "/".join(ideal), desc))
        return
    if a.cmd == "route":
        cache = _ensure()
        mode, models, cat = resolve(a.task, cache)
        print("任务 %s [%s] → %s: %s" % (a.task, cat, mode, " + ".join(models)))
        if mode == "ensemble":
            print("→ 多模型跑完, 主 agent(claude) 综合归纳; 方向打架 = 预期差不可靠 → 降档/拉宽区间。")
        return
    if a.cmd == "run":
        cache = _ensure()
        prompt = sys.stdin.read() if a.infile == "-" else open(a.infile, encoding="utf-8").read()
        mode, models, cat, results, out_dir = run_task(a.task, prompt, cache)
        print("任务 %s [%s] → %s: %s" % (a.task, cat, mode, " + ".join(models)))
        for m, r in results.items():
            print("  ✓ %-9s %d 字 → %s" % (m, r["chars"], r["path"]))
        if mode == "ensemble":
            print("\n【综合归纳】主 agent 请对比上述 %d 份:" % len(results))
            print("  · 方向一致 → 高置信, 正常定档。")
            print("  · 方向打架 → 标'预期差不可靠' → 降一档仓位 + 拉宽 bear/base/bull + 列双方证据。")
        return


if __name__ == "__main__":
    main()

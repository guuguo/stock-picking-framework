# 模型路由模块 (Model Routing) — 按需启用

> 何时加载: 想给深度研究分块加速 / 交叉验证, 且环境里除 claude 外还有 dsclaude / codex 时。
> 工具: `scripts/model_router.py` (零依赖)。可用性缓存 `~/.config/stock-picking/model_routing.json`。
> **版本 v2 (2026-06-25, 去偏重写)**: 旧 v1 按"能力"分(codex算/dsclaude判/claude综合)是基于 claude 出题的有偏 pilot, 已被真实历史题推翻。本版按证据重写。

## 核心纪律: 按需 + 优雅退化

```
启用条件 = 宿主是 claude  AND  (dsclaude 或 codex 至少一个可用)
不满足   → 所有任务自动交 claude 单跑 → 框架行为与现在完全一致, 不报错、不挡路。
```
这是 infra/工具层(决定"谁来跑"), 与"规则冻结/减法治理"正交, 不计入 R 编号。默认不启用, 显式想用多模型时才 `status` 一下。

## 本会话真实题的关键结论 (路由依据)

用真实财报搭题(题面=真实数据、金标=真实数字)、三家盲跑后:

| 维度 | 三家关系 | 说明 |
|---|---|---|
| **推理/计算/判断** (单季还原·扣非剥离·预研·缠论·主线·选股·信息甄别) | **平价** | 真实题 3/3 共识(连百济 +399% 单季陷阱、江波龙"38亿是真实涨价非会计幻觉"都一致) |
| **信息采集 — 采(连数据源/拉数字)** | **claude ≫ codex(沙箱受限) > dsclaude(WebSearch)** | 唯一真差距, 看**工具**不看脑子; claude 还能拿独家有用细节(总/流通市值区分、盘中异动) |
| **信息采集 — 甄别(判信号噪声/挖财报细节/辨合同传言)** | **平价** | 9 条混杂信息 8 条共识, 三家都挖出"合同负债+150%"这种被忽略的财报硬信号 |

→ 旧版"按能力排除 dsclaude 出 A/B"**作废**(真实题证明它计算/剥离都满分)。差距只在"采数据的水管", 该交给有工具的 claude。

## 路由策略 (v2)

```
① 数据采集 (data_fetch)
   · 正常查数(股价/财报/估值)  → claude 单跑      (有工具, 采得全, 独家有用细节)
   · 深度研究(data_fetch_deep) → claude 主采 + dsclaude WebSearch 跟跑(补公告原文链接/小道消息/交叉验证)
   · codex 不用于采集 (沙箱连不上腾讯/通达信)

② 推理 / 计算 / 判断 (单季还原·扣非剥离·预研·缠论·主线·alpha·信息甄别·打分)
   · 默认 claude 单跑 (主 agent, 最稳)
   · 深度研究的高价值判断块(主线归属/预期差nowcast/催化/缠论买卖点/信息甄别) → claude + dsclaude 双跑, 分歧=不确定性
   · 缠论中枢/笔/线段: 流派惯例敏感, 争议项人工定标准, 别盲信任何单家(含 claude)

③ codex = 可选第三方校验, 不进默认流程
   · 机械计算/严格规则执行可作 tie-breaker; 但采集受限 + 成本最高 + 开放中文判断略弱
   · 仅在 claude/dsclaude 分歧大、想要第三票时显式调用
```

## 子命令

```bash
python3 scripts/model_router.py status                 # 看可用性+是否启用(自动探测缓存)
python3 scripts/model_router.py list                    # 列全部任务路由
python3 scripts/model_router.py route <task>            # 查某任务派给谁, 不执行
python3 scripts/model_router.py run <task> --in FILE     # 派活: 跑模型, 输出落 STOCK_ROOT/.model_router/
python3 scripts/model_router.py run <task> --in -        # 从 stdin 读 prompt
```

## 主 agent 工作流

```
1. (按需) status 确认 routing_enabled。否 → 照常自己(claude)做, 结束。
2. 数据采集: 正常 → 自己(claude)拉; 深度研究 → 自己主采, 再 run data_fetch_deep 让 dsclaude WebSearch 补充, 交叉核对。
   ⚠️ dsclaude/codex 看不到框架文件, 派给它们的 prompt 必须自包含(规则+数据喂进去)。
   ⚠️ 精确取数(总/流通市值、集合竞价/收盘、累计/单季、公告原文)以 claude 直连接口为准。
3. 推理/判断:
   · solo(默认) → 自己(claude)算/判, 回填。
   · ensemble(深研判断块) → run <task> 让 dsclaude 也跑一份, 主 agent 综合:
       方向一致 → 高置信; 方向打架 → 标"预期差不可靠" → 降一档仓位 + 拉宽 bear/base/bull + 列双方证据(喂闸门2)。
4. 综合归纳 / 最终评分 / 决策永远由 claude 收口。router 只派活, 不替你决策。
```

**「分歧即不确定性」**: 高价值判断块让 dsclaude+claude 双跑, 它俩打架本身就是免费的不确定性信号, 直接接进 P2 概率 / P5 约束(降档+拉宽)。

## 信息采集两层论 (谁能碰什么)

```
采(连数据源/拉真实数字)  → claude 最强(a-stock-data 全, 总/流通市值都分得清);
                          codex 沙箱常连不上腾讯/通达信(能用新浪拿财报, 拿不到实时);
                          dsclaude 有内置 WebSearch, 能聚合级采集 + 补公告链接, 略旧不够精确。
                          三家都守纪律(实测无一编造, 拿不到就明说, 符合 R21)。
甄别(判可参考性/挖财报细节) → 认知活, 三家平价, 谁判都行。
```

## 运维注意 (实测踩过的坑)
- codex 调用必须 `< /dev/null` (脚本已内置): 否则卡等 stdin + 留僵尸进程。
- 并发跑 codex ≤3-4: 高 effort 内存重, 多了 OOM(exit 137)。
- codex 端点偶发 503 整体宕机; 网络抖断要重试。
- codex 采集烧 token 极凶(实测一次拉数烧 12 万 tokens 还拿不全), 更不该用它采。

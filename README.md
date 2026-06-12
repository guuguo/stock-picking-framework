# Stock Picking Framework

A 股价值投资选股框架 — 基于 `新质生产力主线 + 基本面底座 + 预期差 + 最新资料 + 催化时间` 五维决策体系。

## Agent 安装指令

> 将以下内容发给你的 AI Agent（Qoder / Claude Code / Codex），即可自动完成安装：

```
帮我安装 stock-picking-framework 炒股技能。按以下步骤执行：

1. 克隆仓库并链接为全局技能：
   git clone https://github.com/guuguo/stock-picking-framework.git /tmp/stock-picking-framework
   mkdir -p ~/.agents/skills
   ln -sfn /tmp/stock-picking-framework ~/.agents/skills/stock-picking-framework

2. 安装 Python 依赖：
   pip install pandas numpy mootdx requests stockstats

3. 安装依赖的 a-stock-data 数据技能：
   mkdir -p ~/.agents/skills/a-stock-data
   curl -fsSL -o ~/.agents/skills/a-stock-data/SKILL.md https://raw.githubusercontent.com/simonlin1212/a-stock-data/main/SKILL.md

4. 初始化 STOCK_ROOT（使用当前目录作为炒股项目目录）：
   mkdir -p ~/.config/stock-picking
   echo "{\"stock_root\": \"$(pwd)\"}" > ~/.config/stock-picking/config.json
   mkdir -p monitor cases data research snapshots
   [ ! -f monitor/holdings.json ] && echo '{"positions": []}' > monitor/holdings.json
   [ ! -f monitor/nav_history.json ] && echo '{"entries": []}' > monitor/nav_history.json
   [ ! -f daily_playbook.md ] && printf '# Daily Playbook\n\n## 今日计划\n\n- [ ] 检查持仓标的公告\n- [ ] 检查宏观事件日历\n' > daily_playbook.md

5. 验证安装：
   ls ~/.agents/skills/stock-picking-framework/SKILL.md && echo "✅ 技能已安装"
   cat ~/.config/stock-picking/config.json && echo "✅ STOCK_ROOT 已配置"

安装完成后重启对话即可使用。
```

## 手动安装

如果不想通过 Agent，也可以手动执行：

```bash
# 1. 克隆 + 链接
git clone https://github.com/guuguo/stock-picking-framework.git
mkdir -p ~/.agents/skills
ln -sfn "$(pwd)/stock-picking-framework" ~/.agents/skills/stock-picking-framework

# 2. Python 依赖
pip install pandas numpy mootdx requests stockstats

# 3. a-stock-data 数据技能
mkdir -p ~/.agents/skills/a-stock-data
curl -fsSL -o ~/.agents/skills/a-stock-data/SKILL.md \
  https://raw.githubusercontent.com/simonlin1212/a-stock-data/main/SKILL.md

# 4. 初始化（交互式）
cd stock-picking-framework && bash init.sh
```

## 使用方式

安装后在炒股项目目录启动 AI 对话，技能自动工作：

| 你说的话 | 技能自动做的事 |
|---------|--------------|
| "分析一下 601138" | 拉数据 → 8 维研究 → 评分 → 写入 `research/601138_fii/` |
| "我总资产 52 万，现金 3 万" | 自动记账 → 对比沪深300/创业板/科创50 基准 |
| "工业富联该加仓吗" | 加载决策规则 → FCEM 估值 → 仓位建议 |
| "今天有什么宏观事件" | 加载宏观事件日历 → L1-L4 分级提醒 |
| "复盘一下最近的错误" | 加载 `cases/*.md` 历史案例 |

## STOCK_ROOT 发现逻辑

技能通过以下优先级定位你的炒股项目目录：

1. 当前目录含 `monitor/holdings.json` 或 `daily_playbook.md` → 当前目录
2. `~/.config/stock-picking/config.json` 中的 `stock_root` 字段
3. 均不存在 → 询问你选当前目录还是 `~/.stock/`

## 目录结构

```
技能仓库 (stock-picking-framework/)    STOCK_ROOT (你的炒股项目/)
├── SKILL.md                           ├── monitor/
├── references/ (8 份决策文档)          │   ├── holdings.json
├── scripts/ (数据/记账/看板)           │   ├── nav_history.json
├── init.sh                            │   └── performance_ledger.md
├── requirements.txt                   ├── cases/ (复盘案例，自动维护)
└── LICENSE                            ├── data/
                                       ├── research/ (深度研究输出)
                                       ├── snapshots/
                                       └── daily_playbook.md
```

## 核心功能

- **5 原则决策** — 证据 / 概率 / 对称 / 期望收益 / 约束
- **8 维深度研究** — 主线 / 基本面 / 预期差 / 资料 / 催化 / 估值 / 弹性 / 风险
- **FCEM 四源估值** — 量价利 / TAM / 历史 / 同行交叉验证
- **集中仓位管理** — 5±1 只持仓、核心 25%/普通 12%/试错 4%
- **移动止盈体系** — 让赢家跑、保本止盈、趋势破位
- **自动记账** — 净值跟踪 vs 沪深300/创业板/科创50 基准

## 自定义

编辑技能目录下的 `scripts/stocks_config.json` 配置关注股票：

```json
{
  "stocks": {
    "601138": {
      "name": "工业富联",
      "peers": ["002475", "300308"]
    }
  }
}
```

## License

MIT

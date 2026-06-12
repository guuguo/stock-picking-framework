# Stock Picking Framework

A 股价值投资选股框架 — 基于 `新质生产力主线 + 基本面底座 + 预期差 + 最新资料 + 催化时间` 五维决策体系。

## 安装

```bash
npx skills add https://github.com/guuguo/stock-picking-framework --skill stock-picking-framework
```

### 一键安装（Agent 友好）

> 复制下面这段发给 Agent，自动帮你装好并初始化：

```
帮我安装 stock-picking-framework 炒股技能，执行以下两步：
1. npx skills add https://github.com/guuguo/stock-picking-framework --skill stock-picking-framework
2. bash ~/.agents/skills/stock-picking-framework/init.sh
安装完告诉我结果。
```

> 也可以手动分步执行。脚本仅使用 Python 标准库，无需额外 pip 依赖。
> 数据抓取由 [a-stock-data](https://github.com/simonlin1212/a-stock-data) 技能提供，建议一并安装。

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
├── scripts/ (记账/看板)               │   ├── nav_history.json
├── init.sh                            │   └── performance_ledger.md
└── LICENSE                            ├── cases/ (复盘案例，自动维护)
                                       ├── data/
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

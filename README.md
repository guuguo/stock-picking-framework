# stock-skills

A 股投研 AI 技能集。两个技能协同工作：**选股框架**负责纪律执行，**缠论分析**负责结构判断。

## 技能列表

### stock-picking-framework（选股框架 V17）

选股 + 盯盘 + 仓位管理的执行纪律。

**触发方式**：对话中说 `盯盘`、`加仓`、`减仓`、`条件单`、`选股框架`，或引用 `$stock-picking-framework`。

**核心能力**：
- 持仓矩阵与盈亏实时计算
- 加仓决策强制检查表（信号→天花板→空间→结论四步）
- 条件单参数输出（止损/止盈/限价挂单）
- 写死纪律检查（破位首日执行、市价单、分批清仓、背驰当天行动）
- 观察池管理与入场资格评估

**部署要求**：需要 `STOCK_ROOT` 目录（包含 `daily_playbook.md`、`data/holdings.json`、`daily_ops/` 等）。首次使用运行 `init.sh`。

---

### chanlun-analysis（缠论分析）

K 线结构分析框架：笔、中枢、背驰、买卖点。

**触发方式**：对话中说 `缠论`、`背驰`、`一买/二买/三买`、`中枢`，或引用 `$chanlun-analysis`。

**核心能力**：
- 级别联立（周线定方向 + 日线找买卖点）
- 背驰四要素检查（DIF、MACD 面积、价格、成交量）
- 买卖点识别与决策矩阵
- 盯盘顶背驰快检（写死#6）

---

## 两技能分工

| 维度 | chanlun-analysis | stock-picking-framework |
|------|-----------------|------------------------|
| 定位 | 结构分析（笔、中枢、背驰） | 决策执行（仓位、条件单、盯盘） |
| 买点 | 教你怎么找一买/二买/三买 | 找到后怎么分批买 |
| 仓位 | 决策矩阵（+4-6%等） | 具体锚点（3-10%）+ 天花板 25% |
| 条件单 | 原则（背驰当天行动） | 具体挂单参数 |
| 冲突 | 分析方法 | **纪律优先** |

---

## 安装

### 最简单方式（推荐）

```bash
# 1. 克隆到技能源目录
git clone https://github.com/guuguo/stock-skills.git \
  ~/.agents/sources/skills/stock-skills

# 2. 一行创建 symlink（Claude Code / ZCode / Codex 通用）
for skill in stock-picking-framework chanlun-analysis; do
  ln -sf "$HOME/.agents/sources/skills/stock-skills/skills/$skill" \
         "$HOME/.agents/skills/$skill"
done
```

> `~/.claude/skills/` 和 `~/.zcode/skills/` 已有 symlink → `~/.agents/skills/`，无需额外操作。

### 依赖

```bash
pip install requests pandas stockstats
```

### 初始化（仅 stock-picking-framework 首次使用）

```bash
cd ~/.agents/sources/skills/stock-skills/skills/stock-picking-framework
bash init.sh
```

按提示设置 `STOCK_ROOT`（炒股数据目录路径），脚本会自动创建目录结构。

---

## 使用示例

```
# 盯盘
用户: 盯盘
→ 拉取全持仓行情 → 缠论结构速判 → 条件单检查 → 输出盯盘矩阵

# 加仓决策
用户: 长电科技现在能加仓吗
→ 走 SPF V17 加仓强制检查表（信号→天花板→空间→结论）

# 缠论分析
用户: 帮我看看恒立液压的缠论结构
→ 拉周线+日线 → 级别联立 → 背驰四要素 → 买卖点判断

# 观察池评估
用户: 观察仓里有能买的吗
→ 全量拉取 → 逐只过底分型/MA5/背驰 → 输出入场矩阵
```

---

## 文件结构

```
stock-skills/
├── README.md
└── skills/
    ├── stock-picking-framework/
    │   ├── SKILL.md           # 技能主文件（AI 读取入口）
    │   ├── references/        # 决策规则、深度研究框架、预测模型
    │   ├── scripts/           # 信号检测、业绩跟踪、风控脚本
    │   └── cases/             # 复盘案例
    └── chanlun-analysis/
        ├── SKILL.md           # 技能主文件
        ├── references/        # 缠论核心方法论
        └── agents/            # Agent 配置
```

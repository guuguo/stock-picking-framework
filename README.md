# stock-skills

A 股投研 AI 技能集。两个技能协同工作：**选股框架**负责纪律执行，**缠论分析**负责结构判断。

## 一行安装

```bash
# macOS / Linux (bash)
curl -fsSL https://raw.githubusercontent.com/guuguo/stock-picking-framework/main/install.sh | bash
```

```powershell
# Windows (PowerShell, 需管理员权限)
irm https://raw.githubusercontent.com/guuguo/stock-picking-framework/main/install.ps1 | iex
```

脚本自动完成：**clone 仓库 → 检测本地 AI 编辑器 → 交互选择 → 创建 symlink**。

**重复运行 = 自动更新**：再次执行会自动 `git pull` 拉取最新版本，然后刷新 symlink。

---

## 激活方式

在任意支持的 AI 编辑器中，说出以下关键词即可触发：

| 你说 | 触发 |
|------|------|
| `盯盘` | 全持仓实时行情 + 缠论结构 + 条件单检查 |
| `加仓` / `减仓` | SPF V17 加仓强制检查表 |
| `缠论` / `背驰` / `中枢` / `一买` | 缠论结构分析 |
| **`深度研究 <股票名>`** | 基本面准入 → 估值 → 缠论 → 投资论文 |
| `观察仓` / `候选池` | 全观察池入场资格扫描 |
| `条件单` | 输出具体挂单参数 |

---

## 技能列表

### stock-picking-framework（选股框架 V17）

选股 + 盯盘 + 仓位管理的执行纪律。

**核心能力**：持仓矩阵 / 加仓四步检查表 / 条件单参数 / 写死纪律（破位当天执行、市价单、分批清仓）/ 观察池管理

### chanlun-analysis（缠论分析）

K 线结构分析框架：笔、中枢、背驰、买卖点。

**核心能力**：级别联立（周线+日线）/ 背驰四要素 / 买卖点决策矩阵 / 顶背驰快检

---

## 两技能分工

| 维度 | chanlun-analysis | stock-picking-framework |
|------|-----------------|------------------------|
| 定位 | 结构分析 | 决策执行 |
| 买点 | 找一买/二买/三买 | 分批怎么买 |
| 仓位 | 决策矩阵 | 具体锚点 + 天花板 25% |
| 冲突 | 分析方法 | **纪律优先** |

---

## 依赖

```bash
pip install requests pandas stockstats
```

---

## 文件结构

```
stock-skills/
├── README.md
├── install.sh           # macOS / Linux 安装脚本
├── install.ps1          # Windows PowerShell 安装脚本
└── skills/
    ├── stock-picking-framework/
    │   ├── SKILL.md
    │   ├── references/  # 决策规则、深度研究框架
    │   ├── scripts/     # 信号检测、风控脚本
    │   └── cases/       # 复盘案例
    └── chanlun-analysis/
        ├── SKILL.md
        ├── references/  # 缠论核心方法论
        └── agents/
```

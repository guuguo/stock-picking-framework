# Stock Picking Framework

A 股价值投资选股框架 — 基于 `新质生产力主线 + 基本面底座 + 预期差 + 最新资料 + 催化时间` 五维决策体系。

## 安装

### 1. 安装为 AI Agent 技能

```bash
# 克隆仓库
git clone https://github.com/guuguo/stock-picking-framework.git

# 链接到全局技能目录
mkdir -p ~/.agents/skills
ln -s "$(pwd)/stock-picking-framework" ~/.agents/skills/stock-picking-framework
```

> Qoder / Claude Code 用户：安装后重启对话即可自动识别。

### 2. 运行初始化

```bash
cd stock-picking-framework
bash init.sh
```

初始化脚本会：
- 询问 STOCK_ROOT 位置（当前目录 或 `~/.stock/`）
- 写入全局配置 `~/.config/stock-picking/config.json`
- 在 STOCK_ROOT 下创建目录结构（monitor/ cases/ data/ research/ snapshots/）
- 创建空模板文件

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 安装外部数据技能（必需）

本技能依赖 `a-stock-data` 提供 A 股行情、研报、资金等数据：

```bash
# 安装 a-stock-data 技能
mkdir -p ~/.agents/skills/a-stock-data
curl -o ~/.agents/skills/a-stock-data/SKILL.md \
  https://raw.githubusercontent.com/simonlin1212/a-stock-data/main/SKILL.md
```

来源：[github.com/simonlin1212/a-stock-data](https://github.com/simonlin1212/a-stock-data)

## 使用

安装后在任意炒股项目目录启动 AI 对话，技能会自动：

1. **发现 STOCK_ROOT** — 通过项目特征文件或全局配置定位
2. **按需加载参考文档** — 根据场景自动加载决策规则、研究框架等
3. **执行研究/决策** — 深度研究输出写入 `research/<ticker>/`，cases 自动维护
4. **记账跟踪** — 报告总资产时自动记录净值、对比基准

## 目录结构

```
stock-picking-framework/          # 技能仓库
├── SKILL.md                      # 技能主文件
├── references/                   # 8 份按需加载参考文档
├── scripts/                      # Python 脚本（数据抓取/记账/看板）
├── init.sh                       # 初始化脚本
└── ...

STOCK_ROOT/                       # 运行时数据目录（init.sh 创建）
├── monitor/                      # 持仓/净值/业绩台账
├── cases/                        # 复盘案例（自动维护）
├── data/                         # 数据产物
├── research/                     # 深度研究输出
├── snapshots/                    # 持仓快照
└── daily_playbook.md             # 每日计划
```

## 核心功能

- **5 原则决策框架** — 证据 / 概率 / 对称 / 期望收益 / 约束
- **8 维深度研究** — 主线 / 基本面 / 预期差 / 资料 / 催化 / 估值 / 弹性 / 风险
- **FCEM 四源估值** — 量价利 / TAM / 历史 / 同行交叉验证
- **集中仓位管理** — 5±1 只持仓、核心 25%/普通 12%/试错 4%
- **移动止盈体系** — 让赢家跑、保本止盈、趋势破位
- **自动记账** — 净值跟踪 vs 沪深300/创业板/科创50 基准

## 配置

编辑 `scripts/stocks_config.json` 配置你的关注股票和同行对标：

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

#!/usr/bin/env bash
set -euo pipefail

# stock-picking-framework 初始化脚本
# 职责: 创建 STOCK_ROOT 目录结构 + 写入全局配置

CONFIG_DIR="$HOME/.config/stock-picking"
CONFIG_FILE="$CONFIG_DIR/config.json"

echo "=== Stock Picking Framework 初始化 ==="
echo ""

# 1. 确定 STOCK_ROOT
if [ -f "$CONFIG_FILE" ]; then
    EXISTING_ROOT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['stock_root'])" 2>/dev/null || echo "")
    if [ -n "$EXISTING_ROOT" ]; then
        echo "已存在全局配置: STOCK_ROOT = $EXISTING_ROOT"
        read -rp "是否重新设置? [y/N] " RECONFIRM
        if [[ "$RECONFIRM" != "y" && "$RECONFIRM" != "Y" ]]; then
            STOCK_ROOT="$EXISTING_ROOT"
        fi
    fi
fi

if [ -z "${STOCK_ROOT:-}" ]; then
    echo "选择 STOCK_ROOT（所有炒股数据存放位置）:"
    echo "  1) 使用当前目录: $(pwd)"
    echo "  2) 创建 ~/.stock/ 作为全局目录"
    read -rp "请选择 [1/2]: " CHOICE

    case "$CHOICE" in
        1) STOCK_ROOT="$(pwd)" ;;
        2) STOCK_ROOT="$HOME/.stock" ;;
        *) STOCK_ROOT="$(pwd)" ;;
    esac
fi

echo ""
echo "STOCK_ROOT = $STOCK_ROOT"

# 2. 创建全局配置文件
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" << EOF
{
  "stock_root": "$STOCK_ROOT"
}
EOF
echo "✓ 全局配置已写入: $CONFIG_FILE"

# 3. 创建 STOCK_ROOT 目录结构
mkdir -p "$STOCK_ROOT"/{monitor,cases,data,research,snapshots}
echo "✓ 目录结构已创建: monitor/ cases/ data/ research/ snapshots/"

# 4. 创建空模板文件（如不存在）
if [ ! -f "$STOCK_ROOT/monitor/holdings.json" ]; then
    echo '{"positions": []}' > "$STOCK_ROOT/monitor/holdings.json"
    echo "✓ 已创建 monitor/holdings.json"
fi

if [ ! -f "$STOCK_ROOT/monitor/nav_history.json" ]; then
    echo '{"entries": []}' > "$STOCK_ROOT/monitor/nav_history.json"
    echo "✓ 已创建 monitor/nav_history.json"
fi

if [ ! -f "$STOCK_ROOT/daily_playbook.md" ]; then
    cat > "$STOCK_ROOT/daily_playbook.md" << 'PLAYBOOK'
# Daily Playbook

> 每日操作计划，盘前更新。

## 今日计划

- [ ] 检查持仓标的公告
- [ ] 检查宏观事件日历

## 待跟踪

_（按需添加）_
PLAYBOOK
    echo "✓ 已创建 daily_playbook.md"
fi

echo ""
echo "=== 初始化完成 ==="
echo "STOCK_ROOT: $STOCK_ROOT"
echo "配置文件:   $CONFIG_FILE"
echo ""
echo "下一步:"
echo "  1. pip install -r requirements.txt"
echo "  2. 安装 a-stock-data 技能（见 README.md）"
echo "  3. 按需编辑 scripts/stocks_config.json 配置你的关注股票"

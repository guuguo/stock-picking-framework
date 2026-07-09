#!/usr/bin/env bash
set -euo pipefail

# stock-skills 安装脚本
# 自动检测本地 AI 编辑器 → 选择目标 → 创建 symlink
# 兼容 bash 3.x+ (macOS / Linux)

SKILLS="stock-picking-framework chanlun-analysis"
CANONICAL="$HOME/.agents/sources/skills/stock-skills/skills"

# ── 编辑器检测 ──────────────────────────────────
# 格式: "id|skills_path|marker_path"
CONSUMERS=(
  "claude|$HOME/.claude/skills|$HOME/.claude"
  "zcode|$HOME/.zcode/skills|$HOME/.zcode"
  "codex|$HOME/.codex/skills|$HOME/.codex"
  "opencode|$HOME/.config/opencode/skills|$HOME/.config/opencode"
  "antigravity|$HOME/.gemini/antigravity/skills|$HOME/.gemini/antigravity"
  "qoderwork|$HOME/.qoderworkcn/skills|$HOME/.qoderworkcn"
  "hermes|$HOME/.hermes/skills|$HOME/.hermes"
)

echo "🔍 扫描本地 AI 编辑器..."
echo ""

DETECTED=()
for entry in "${CONSUMERS[@]}"; do
  id="${entry%%|*}"; rest="${entry#*|}"; path="${rest%%|*}"; marker="${rest##*|}"
  if [ -e "$marker" ]; then
    DETECTED+=("$id|$path")
    printf "   ✅ %-12s → %s\n" "$id" "$path"
  else
    printf "   ⬜ %-12s (未安装)\n" "$id"
  fi
done

if [ ${#DETECTED[@]} -eq 0 ]; then
  echo ""
  echo "❌ 未检测到任何 AI 编辑器。至少需要安装 Claude Code / ZCode / Codex 之一。"
  exit 1
fi

# ── 用户选择 ──────────────────────────────────
echo ""
echo "📦 将安装以下技能:"
for s in $SKILLS; do echo "   - $s"; done
echo ""
echo "检测到 ${#DETECTED[@]} 个编辑器:"
for entry in "${DETECTED[@]}"; do
  echo "   - ${entry%%|*}"
done
echo ""
read -rp "安装到全部检测到的编辑器? [Y/n] " CHOICE

SELECTED=()
if [[ "$CHOICE" =~ ^[Nn] ]]; then
  echo ""
  echo "请选择要安装到的编辑器 (空格分隔多个):"
  for i in "${!DETECTED[@]}"; do
    echo "  $((i+1))) ${DETECTED[$i]%%|*}"
  done
  read -rp "> " NUMS
  for n in $NUMS; do
    idx=$((n-1))
    [ -n "${DETECTED[$idx]:-}" ] && SELECTED+=("${DETECTED[$idx]}")
  done
else
  SELECTED=("${DETECTED[@]}")
fi

# ── 创建 symlink ──────────────────────────────────
echo ""
echo "🔗 创建 symlink..."
echo ""

for entry in "${SELECTED[@]}"; do
  id="${entry%%|*}"; path="${entry##*|}"
  for skill in $SKILLS; do
    src="$CANONICAL/$skill"; dest="$path/$skill"
    mkdir -p "$path"
    if [ -L "$dest" ]; then
      current=$(readlink "$dest")
      if [ "$current" = "$src" ]; then
        echo "   ✅ $id/$skill (已正确链接)"
        continue
      fi
    fi
    rm -rf "$dest"
    ln -sf "$src" "$dest"
    echo "   🔗 $id/$skill"
  done
done

# ── .agents 桥接 ──────────────────────────────────
echo ""
echo "🌉 设置 .agents 桥接..."
mkdir -p "$HOME/.agents/skills"
for skill in $SKILLS; do
  src="$CANONICAL/$skill"; dest="$HOME/.agents/skills/$skill"
  rm -rf "$dest"; ln -sf "$src" "$dest"
  echo "   🔗 .agents/$skill"
done

# ── 验证矩阵 ──────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  安装完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "%-14s" "编辑器"
for skill in $SKILLS; do printf "%-22s" "$skill"; done
echo ""
for entry in "${CONSUMERS[@]}"; do
  id="${entry%%|*}"; rest="${entry#*|}"; path="${rest%%|*}"; marker="${rest##*|}"
  printf "%-14s" "$id"
  if [ -e "$marker" ]; then
    for skill in $SKILLS; do
      link="$path/$skill"
      if [ -L "$link" ]; then
        t=$(readlink "$link")
        case "$t" in
          *stock-skills*) printf "%-22s" "✅ linked" ;;
          *)             printf "%-22s" "⚠️  drift" ;;
        esac
      else
        printf "%-22s" "❌ missing"
      fi
    done
  else
    for skill in $SKILLS; do printf "%-22s" "—"; done
  fi
  echo ""
done
echo ""
echo "💡 对话中说「盯盘」或「缠论」即可激活技能"

# stock-skills Windows 安装脚本 (PowerShell)
# 自动检测本地 AI 编辑器 → 选择目标 → 创建 symlink

param([switch]$Yes)

$skills = @("stock-picking-framework", "chanlun-analysis")
$canonical = "$env:USERPROFILE\.agents\sources\skills\stock-skills\skills"

# ── 编辑器检测 ──────────────────────────────────
$consumers = @(
  @{id="claude";      path="$env:USERPROFILE\.claude\skills";               marker="$env:USERPROFILE\.claude"},
  @{id="codex";       path="$env:USERPROFILE\.codex\skills";                marker="$env:USERPROFILE\.codex"},
  @{id="opencode";    path="$env:USERPROFILE\.config\opencode\skills";      marker="$env:USERPROFILE\.config\opencode"},
  @{id="antigravity"; path="$env:USERPROFILE\.gemini\antigravity\skills";   marker="$env:USERPROFILE\.gemini\antigravity"},
  @{id="qoderwork";   path="$env:USERPROFILE\.qoderworkcn\skills";          marker="$env:USERPROFILE\.qoderworkcn"},
  @{id="hermes";      path="$env:USERPROFILE\.hermes\skills";               marker="$env:USERPROFILE\.hermes"}
)

Write-Host "🔍 扫描本地 AI 编辑器..." -ForegroundColor Cyan
Write-Host ""

$detected = @()
foreach ($c in $consumers) {
  if (Test-Path $c.marker) {
    $detected += $c
    Write-Host "   ✅ $($c.id.PadRight(12)) → $($c.path)"
  } else {
    Write-Host "   ⬜ $($c.id.PadRight(12)) (未安装)"
  }
}

if ($detected.Count -eq 0) {
  Write-Host ""
  Write-Host "❌ 未检测到任何 AI 编辑器。" -ForegroundColor Red
  exit 1
}

# ── 用户选择 ──────────────────────────────────
Write-Host ""
Write-Host "📦 将安装以下技能:" -ForegroundColor Yellow
foreach ($s in $skills) { Write-Host "   - $s" }
Write-Host ""
Write-Host "检测到 $($detected.Count) 个编辑器:"
foreach ($d in $detected) { Write-Host "   - $($d.id)" }

if (-not $Yes) {
  Write-Host ""
  $choice = Read-Host "安装到全部检测到的编辑器? [Y/n]"
  if ($choice -match '^[Nn]') {
    Write-Host ""
    Write-Host "请选择 (空格分隔多个):"
    for ($i=0; $i -lt $detected.Count; $i++) {
      Write-Host "  $($i+1)) $($detected[$i].id)"
    }
    $nums = Read-Host ">"
    $selected = @()
    foreach ($n in $nums -split '\s+') {
      $idx = [int]$n - 1
      if ($idx -ge 0 -and $idx -lt $detected.Count) {
        $selected += $detected[$idx]
      }
    }
    $detected = $selected
  }
}

# ── 创建 symlink ──────────────────────────────────
Write-Host ""
Write-Host "🔗 创建 symlink..." -ForegroundColor Green
Write-Host ""

# 需要管理员权限才能创建 symlink (Windows)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Host "⚠️  Windows 创建 symlink 需要管理员权限。正在尝试..." -ForegroundColor Yellow
}

foreach ($c in $detected) {
  New-Item -ItemType Directory -Force -Path $c.path | Out-Null
  foreach ($skill in $skills) {
    $src = Join-Path $canonical $skill
    $dest = Join-Path $c.path $skill
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue }
    try {
      New-Item -ItemType SymbolicLink -Path $dest -Target $src -Force | Out-Null
      Write-Host "   🔗 $($c.id)/$skill"
    } catch {
      # Fallback: use junction or copy
      Write-Host "   ⚠️  $($c.id)/$skill (symlink 失败, 尝试 junction...)"
      try {
        New-Item -ItemType Junction -Path $dest -Target $src -Force | Out-Null
        Write-Host "      → junction 创建成功"
      } catch {
        Write-Host "   ❌ $($c.id)/$skill 失败: 请以管理员身份运行" -ForegroundColor Red
      }
    }
  }
}

# ── .agents 桥接 ──────────────────────────────────
Write-Host ""
Write-Host "🌉 设置 .agents 桥接..." -ForegroundColor Green
$agentsSkills = "$env:USERPROFILE\.agents\skills"
New-Item -ItemType Directory -Force -Path $agentsSkills | Out-Null
foreach ($skill in $skills) {
  $src = Join-Path $canonical $skill
  $dest = Join-Path $agentsSkills $skill
  Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
  try {
    New-Item -ItemType SymbolicLink -Path $dest -Target $src -Force | Out-Null
    Write-Host "   🔗 .agents/$skill"
  } catch {
    New-Item -ItemType Junction -Path $dest -Target $src -Force | Out-Null
    Write-Host "   🔗 .agents/$skill (junction)"
  }
}

# ── 验证矩阵 ──────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  安装完成" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

$header = "{0,-14}" -f "编辑器"
foreach ($skill in $skills) { $header += "{0,-22}" -f $skill }
Write-Host $header

foreach ($c in $consumers) {
  $line = "{0,-14}" -f $c.id
  if (Test-Path $c.marker) {
    foreach ($skill in $skills) {
      $link = Join-Path $c.path $skill
      if (Test-Path $link) {
        $line += "{0,-22}" -f "✅ linked"
      } else {
        $line += "{0,-22}" -f "❌ missing"
      }
    }
  } else {
    foreach ($skill in $skills) { $line += "{0,-22}" -f "—" }
  }
  Write-Host $line
}

Write-Host ""
Write-Host "💡 对话中说「盯盘」「缠论」「深度研究」即可激活" -ForegroundColor Yellow

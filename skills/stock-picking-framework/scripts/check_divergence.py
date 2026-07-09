#!/usr/bin/env python3
"""
背驰自动检测脚本 — 严格缠论方法论
工作流: 包含处理 → 分型 → 笔 → 中枢 → 背驰判断 → 买卖点映射
"""

import json
import urllib.request
import sys
import os
from datetime import datetime

STOCK_ROOT = os.environ.get('STOCK_ROOT', '/Volumes/Seamless SSD/dev/guuguo/life/炒股')
DATA_DIR = os.path.join(STOCK_ROOT, 'data')

# ============================================================
# K线数据
# ============================================================

def get_kline(code, days=90):
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        klines = data['data'][code].get('qfqday', data['data'][code].get('day', []))
        return [{
            'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
            'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5])
        } for k in klines]
    except:
        return None

# ============================================================
# Step 1: 包含处理
# ============================================================

def han_baohan(klines):
    """K线包含处理：按趋势方向合并有包含关系的相邻K线"""
    if len(klines) < 3:
        return klines
    processed = [dict(k) for k in klines]
    i = 1
    while i < len(processed):
        prev, cur = processed[i-1], processed[i]
        # 判断包含关系
        contained = ((prev['high'] >= cur['high'] and prev['low'] <= cur['low']) or
                     (cur['high'] >= prev['high'] and cur['low'] <= prev['low']))
        if contained:
            # 判断趋势方向
            if i >= 2:
                upward = prev['close'] > processed[i-2]['close']
            else:
                upward = prev['close'] > prev['open']
            if upward:
                # 向上：取高高+高低
                processed[i] = {
                    'date': cur['date'], 'open': prev['open'], 'close': cur['close'],
                    'high': max(prev['high'], cur['high']),
                    'low': max(prev['low'], cur['low']),
                    'volume': prev['volume'] + cur['volume']
                }
            else:
                # 向下：取低高+低低
                processed[i] = {
                    'date': cur['date'], 'open': prev['open'], 'close': cur['close'],
                    'high': min(prev['high'], cur['high']),
                    'low': min(prev['low'], cur['low']),
                    'volume': prev['volume'] + cur['volume']
                }
            processed.pop(i-1)
        else:
            i += 1
    return processed

# ============================================================
# Step 2: 分型识别
# ============================================================

def find_fractals(klines):
    """在包含处理后的K线上找顶底分型"""
    tops, bottoms = [], []
    for i in range(1, len(klines) - 1):
        ph, ch, nh = klines[i-1]['high'], klines[i]['high'], klines[i+1]['high']
        pl, cl, nl = klines[i-1]['low'],  klines[i]['low'],  klines[i+1]['low']
        if ch > ph and ch > nh:
            tops.append({'date': klines[i]['date'], 'price': ch, 'volume': klines[i]['volume'], 'type': '顶'})
        if cl < pl and cl < nl:
            bottoms.append({'date': klines[i]['date'], 'price': cl, 'volume': klines[i]['volume'], 'type': '底'})
    return tops, bottoms

# ============================================================
# Step 3: 笔
# ============================================================

def build_bi(tops, bottoms):
    """用有效交替分型连接成笔"""
    all_fx = sorted(tops + bottoms, key=lambda x: x['date'])
    if len(all_fx) < 2:
        return []

    bi = []
    last = all_fx[0]
    for fx in all_fx[1:]:
        if fx['type'] != last['type']:
            bi.append({'from': last, 'to': fx,
                       'direction': '↑' if fx['price'] > last['price'] else '↓',
                       'pct': (fx['price']-last['price'])/last['price']*100})
            last = fx
        else:
            # 同向：取极值（顶取更高，底取更低）
            if fx['type'] == '顶' and fx['price'] > last['price']:
                last = fx
            elif fx['type'] == '底' and fx['price'] < last['price']:
                last = fx
    return bi

# ============================================================
# Step 4: 中枢
# ============================================================

def find_zhongshu(bi):
    """从笔中识别中枢（至少3段重叠）"""
    zhongshu_list = []
    for i in range(len(bi) - 2):
        segs = bi[i:i+3]
        highs = [max(s['from']['price'], s['to']['price']) for s in segs]
        lows = [min(s['from']['price'], s['to']['price']) for s in segs]
        zg, zd = min(highs), max(lows)
        if zg > zd:
            zhongshu_list.append({
                'zg': round(zg, 1), 'zd': round(zd, 1),
                'start': segs[0]['from']['date'], 'end': segs[-1]['to']['date']
            })
    return zhongshu_list

# ============================================================
# Step 5: 背驰判断
# ============================================================

def check_top_divergence(bi, tops, zhongshu_list):
    """顶背驰: 比较同向笔或中枢前后的力度"""
    if len(tops) < 2:
        return None

    t1, t2 = tops[-2], tops[-1]
    price_up = t2['price'] > t1['price']
    vol_ratio = t2['volume'] / t1['volume'] if t1['volume'] > 0 else 1

    # 情况1: 顶背驰 — 价格新高但量没跟上
    if price_up and vol_ratio < 0.8:
        return {
            'type': '顶背驰', 'level': '🔴 SELL',
            'desc': f"价格新高量能萎缩 {vol_ratio:.0%}",
            'action': '一卖: 减仓1/3',
            'date': t2['date'],
            'detail': f"{t1['date']} 顶@{t1['price']:.1f} 量{t1['volume']/10000:.0f}万 → "
                      f"{t2['date']} 顶@{t2['price']:.1f} 量{t2['volume']/10000:.0f}万"
        }

    # 情况2: 一卖已过，顶分型下移 → 找二卖
    if not price_up:
        ratio = (t2['price'] - t1['price']) / t1['price'] * 100
        return {
            'type': '顶分型下移', 'level': '🟡 WARN',
            'desc': f"一卖 {t1['date']} @{t1['price']:.1f}，二卖 {t2['date']} @{t2['price']:.1f} (高点降{ratio:+.1f}%)",
            'action': '二卖: 反弹至中枢附近减仓',
            'date': t2['date'],
            'detail': f"{t1['date']} @{t1['price']:.1f} → {t2['date']} @{t2['price']:.1f}"
        }

    # 情况3: 放量新高（无背驰）
    return {
        'type': '放量突破', 'level': '🟢 OK',
        'desc': f"价量同步新高",
        'action': None, 'date': t2['date'],
        'detail': f"{t1['date']}→{t2['date']} 量比{vol_ratio:.0%}"
    }

def check_bottom_divergence(bi, bottoms, zhongshu_list):
    """底背驰"""
    if len(bottoms) < 2:
        return None

    b1, b2 = bottoms[-2], bottoms[-1]
    price_down = b2['price'] < b1['price']
    vol_ratio = b2['volume'] / b1['volume'] if b1['volume'] > 0 else 1

    # 底背驰: 价格新低但缩量
    if price_down and vol_ratio < 0.8:
        return {
            'type': '底背驰', 'level': '🟢 BUY',
            'desc': f"价格新低缩量 {vol_ratio:.0%}，卖压衰竭",
            'action': '关注一买: 需底分型+站上MA5确认',
            'date': b2['date'],
            'detail': f"{b1['date']} 底@{b1['price']:.1f} 量{b1['volume']/10000:.0f}万 → "
                      f"{b2['date']} 底@{b2['price']:.1f} 量{b2['volume']/10000:.0f}万"
        }

    # 下跌放量 = 危险
    if price_down and vol_ratio >= 1.0:
        return {
            'type': '下跌放量', 'level': '🔴 DANGER',
            'desc': f"价跌量增 {vol_ratio:.0%}",
            'action': '远离，不接刀',
            'date': b2['date'],
            'detail': f"{b1['date']}→{b2['date']} 量比{vol_ratio:.0%}"
        }

    return None

# ============================================================
# Step 6: 综合判断
# ============================================================

def analyze(code, name):
    klines = get_kline(code)
    if not klines or len(klines) < 30:
        return {'name': name, 'code': code, 'error': '数据不足'}

    # 缠论严格流程
    clean = han_baohan(klines)
    tops, bottoms = find_fractals(clean)
    bi = build_bi(tops, bottoms)
    zhongshu_list = find_zhongshu(bi)

    price = clean[-1]['close']
    ma5 = sum(k['close'] for k in clean[-5:]) / 5
    ma20 = sum(k['close'] for k in clean[-20:]) / 20

    top_signal = check_top_divergence(bi, tops, zhongshu_list)
    bottom_signal = check_bottom_divergence(bi, bottoms, zhongshu_list)

    # 位置判断
    position = '—'
    if zhongshu_list:
        zs = zhongshu_list[-1]
        if price > zs['zg']:
            position = f"中枢上方(三买候选)"
        elif price < zs['zd']:
            position = f"中枢下方(三卖候选)"
        else:
            position = f"中枢震荡[{zs['zd']},{zs['zg']}]"

    # 当前笔
    current_bi = None
    if bi:
        last_bi = bi[-1]
        current_bi = f"{last_bi['direction']} {last_bi['from']['price']:.1f}→{last_bi['to']['price']:.1f}"

    return {
        'name': name, 'code': code,
        'price': price, 'ma5': ma5, 'ma20': ma20,
        'position': position,
        'current_bi': current_bi,
        'bi_count': len(bi),
        'zhongshu': zhongshu_list[-1] if zhongshu_list else None,
        'top_signal': top_signal,
        'bottom_signal': bottom_signal,
        'last_top': tops[-1] if tops else None,
        'last_bottom': bottoms[-1] if bottoms else None,
    }

# ============================================================
# 主程序
# ============================================================

def load_symbols():
    symbols = []
    hp = os.path.join(DATA_DIR, 'holdings.json')
    if os.path.exists(hp):
        with open(hp) as f:
            holdings = json.load(f)
        for h in holdings.get('holdings', []):
            symbols.append((h['code'], h['name'], '持仓', h.get('stoploss')))
    wp = os.path.join(DATA_DIR, 'watchlist.json')
    if os.path.exists(wp):
        with open(wp) as f:
            watchlist = json.load(f)
        for w in watchlist.get('watchlist', []):
            if w['code'] not in {s[0] for s in symbols}:
                symbols.append((w['code'], w['name'], '观察', None))
    return symbols

def main():
    symbols = load_symbols()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    print(f"╔══════════════════════════════════════════════════════════════╗")
    print(f"║  缠论背驰检测  {now}  (严格方法)              ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")

    alerts = []
    results = []
    sell_signals = []
    buy_signals = []

    for code, name, source, stoploss in symbols:
        r = analyze(code, name)
        results.append(r)

        ts = r.get('top_signal')
        if ts and ts['level'] in ('🔴 SELL', '🟡 WARN'):
            alerts.append((name, code, source, ts, stoploss))
            if ts['level'] == '🔴 SELL':
                sell_signals.append((name, code, source, r, stoploss))

        bs = r.get('bottom_signal')
        if bs and bs['level'] in ('🟢 BUY',):
            alerts.append((name, code, source, bs, stoploss))
            buy_signals.append((name, code, source, r, stoploss))

    # 状态表
    print(f"║ {'标的':<8} {'源':<4} {'现价':>8} {'位置':<22} {'笔':<16} {'顶':<10} {'底':<10}║")
    print(f"║ {'─'*80}║")
    for r in results:
        name = r.get('name', '?')
        source = r.get('source', '?')
        price = r.get('price', 0)
        pos = r.get('position', '—')[:22]
        bi_str = r.get('current_bi') or '—'
        ts = r.get('top_signal')
        bs = r.get('bottom_signal')
        top_str = ts['level'] if ts else '—'
        bot_str = bs['level'] if bs else '—'
        print(f"║ {name:<8} {source:<4} {price:>8.2f} {pos:<22} {bi_str:<16} {top_str:<10} {bot_str:<10}║")

    # 详细信号
    if alerts:
        print(f"╠══════════════════════════════════════════════════════════════╣")
        for name, code, source, signal, sl in alerts:
            print(f"║                                                              ║")
            print(f"║  {signal['level']} {name} ({source})    {signal['type']}                              ║")
            print(f"║  {signal['detail']}                                          ║")
            if signal.get('action'):
                print(f"║  → {signal['action']}                                        ║")
            if sl:
                print(f"║  止损: {sl}                                                 ║")

    print(f"╚══════════════════════════════════════════════════════════════╝")

    # 买卖信号汇总
    if sell_signals:
        print(f"\n🔴 卖出信号 ({len(sell_signals)}):")
        for name, code, source, r, sl in sell_signals:
            ts = r['top_signal']
            print(f"  {name}: {ts['action']} — {ts['desc']}")
    if buy_signals:
        print(f"\n🟢 买入信号 ({len(buy_signals)}):")
        for name, code, source, r, sl in buy_signals:
            bs = r['bottom_signal']
            print(f"  {name}: {bs['action']} — {bs['desc']}")
    if not sell_signals and not buy_signals:
        print(f"\n✅ 无操作信号")

    return alerts

if __name__ == '__main__':
    main()

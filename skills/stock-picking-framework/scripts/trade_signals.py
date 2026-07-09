#!/usr/bin/env python3
"""
统一买卖信号引擎
每次盯盘跑一次，输出今天该挂的所有买卖单（直接抄进涨乐）
"""

import json
import urllib.request
import sys
import os
from datetime import datetime

ROOT = os.environ.get('STOCK_ROOT', '/Volumes/Seamless SSD/dev/guuguo/life/炒股')
DATA = os.path.join(ROOT, 'data')

def fetch_prices(codes):
    """逐条拉现价（腾讯单股API，可靠）"""
    import time
    result = {}
    for code in codes:
        try:
            url = f"http://web.ifzq.gtimg.cn/appstock/app/minute/query?_var=min_data&code={code}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8').replace('min_data=',''))
            qt = data['data'][code]['qt'][code]
            result[code] = {
                'price': float(qt[3]), 'chg': float(qt[32]),
                'high': float(qt[33]), 'low': float(qt[34]),
            }
        except:
            pass
        time.sleep(0.03)
    return result

def get_kline(code, days=60):
    url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        klines = data['data'][code].get('qfqday', data['data'][code].get('day', []))
        return [{'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                 'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5])} for k in klines]
    except:
        return None

def find_fractals(klines):
    tops, bottoms = [], []
    for i in range(1, len(klines)-1):
        ph, ch, nh = klines[i-1]['high'], klines[i]['high'], klines[i+1]['high']
        pl, cl, nl = klines[i-1]['low'],  klines[i]['low'],  klines[i+1]['low']
        if ch > ph and ch > nh:
            tops.append({'date': klines[i]['date'], 'price': ch, 'vol': klines[i]['volume']})
        if cl < pl and cl < nl:
            bottoms.append({'date': klines[i]['date'], 'price': cl, 'vol': klines[i]['volume']})
    return tops, bottoms

# ============================================================
# 卖出信号
# ============================================================

def check_sell(holding, prices):
    """检查单只持仓是否需要卖出"""
    code = holding['code']
    name = holding['name']
    price = prices.get(code, {}).get('price')
    if not price:
        return []

    orders = []
    shares = holding['shares']
    stoploss = holding.get('stoploss', 0)
    cost = holding.get('cost', 0)
    target_pct = holding.get('target_pct', 0)
    current_pct = holding.get('pos_pct', 0)

    # 1. 止损距离检查
    if stoploss:
        dist = (price - stoploss) / stoploss * 100
        if dist <= 3.0:
            orders.append({
                'name': name, 'code': code, 'action': '⚠️止损逼近',
                'type': '价跌卖出',
                'trigger': stoploss, 'qty': shares,
                'reason': f'距止损仅 {dist:+.1f}%，已挂单不用动' if dist > 0 else '已破止损！'
            })

    # 2. 背驰检查
    klines = get_kline(code)
    if klines and len(klines) >= 30:
        tops, _ = find_fractals(klines)
        if len(tops) >= 2:
            t1, t2 = tops[-2], tops[-1]
            # 顶背驰: 价格新高 + 量能萎缩
            if t2['price'] > t1['price'] and t2['vol'] < t1['vol'] * 0.8:
                dist_from_top = (price - t2['price']) / t2['price'] * 100
                sell_qty = max(100, (shares // 3 // 100) * 100)

                if dist_from_top > -5:
                    # 还在高点附近 → 回落卖出
                    orders.append({
                        'name': name, 'code': code, 'action': '🔴顶背驰·削在顶',
                        'type': '回落卖出',
                        'monitor': t2['price'],
                        'fall': '3%',
                        'trigger': round(t2['price'] * 0.97, 2),
                        'qty': sell_qty,
                        'reason': f'{t1["date"]}顶{t1["price"]:.1f}→{t2["date"]}顶{t2["price"]:.1f} 量缩{t2["vol"]/t1["vol"]:.0%}'
                    })
                else:
                    # 已经跌了一段 → 反弹卖出（二卖）
                    ma5 = sum(k['close'] for k in klines[-5:]) / 5
                    target = round(ma5, 2)
                    orders.append({
                        'name': name, 'code': code, 'action': '🔴顶背驰·等反弹二卖',
                        'type': '限价卖出',
                        'trigger': target,
                        'qty': sell_qty,
                        'reason': f'{t1["date"]}顶{t1["price"]:.1f}→{t2["date"]}顶{t2["price"]:.1f} 量缩{t2["vol"]/t1["vol"]:.0%}，已跌{dist_from_top:+.0f}%，等二卖@{target}'
                    })

    # 3. 仓位超标检查
    if target_pct > 0 and current_pct > target_pct * 1.1:
        excess = current_pct - target_pct
        # 只提醒，不做自动卖出
        orders.append({
            'name': name, 'code': code, 'action': '🟡仓位超标',
            'type': '提醒',
            'trigger': None, 'qty': 0,
            'reason': f'仓位{current_pct:.1f}% > 目标{target_pct:.1f}% (超{excess:.1f}%)，反弹减仓'
        })

    return orders

# ============================================================
# 买入信号
# ============================================================

def check_buy(watch_item, prices):
    """检查观察池标的是否触发买点"""
    code = watch_item['code']
    name = watch_item['name']
    score = watch_item.get('score', 0)
    price = prices.get(code, {}).get('price')
    if not price or score < 7.0:
        return None

    klines = get_kline(code, days=60)
    if not klines or len(klines) < 30:
        return None

    tops, bottoms = find_fractals(klines)
    closes = [k['close'] for k in klines[-20:]]
    lows = [k['low'] for k in klines[-3:]]
    ma5 = sum(k['close'] for k in klines[-5:]) / 5
    ma20 = sum(k['close'] for k in klines[-20:]) / 20

    signals = []
    buy_ready = False

    # 条件1: 底背驰
    if len(bottoms) >= 2:
        b1, b2 = bottoms[-2], bottoms[-1]
        if b2['price'] < b1['price'] and b2['vol'] < b1['vol'] * 0.8:
            signals.append(f'底背驰: {b1["date"]}底{b1["price"]:.1f}→{b2["date"]}底{b2["price"]:.1f} 缩量{b2["vol"]/b1["vol"]:.0%}')

    # 条件2: 最近有底分型
    if bottoms and bottoms[-1]['date'] >= klines[-3]['date']:
        b = bottoms[-1]
        signals.append(f'近日底分型: {b["date"]} 低@{b["price"]:.2f}')

    # 条件3: 不破前低
    if len(bottoms) >= 2:
        last_low = bottoms[-1]['price']
        today_low = klines[-1]['low']
        if today_low >= last_low * 0.98:
            signals.append(f'未破前低{last_low:.2f} (今日低{today_low:.2f})')
        else:
            signals.append(f'⚠️ 今日低{today_low:.2f} 已破前低{last_low:.2f}')

    # 条件4: 站上MA5
    if price > ma5:
        signals.append(f'站上MA5({ma5:.2f})')
    else:
        signals.append(f'仍在MA5({ma5:.2f})下方 {price/ma5*100-100:+.1f}%')

    # 判断满足几条
    conditions_met = sum(1 for s in signals if not s.startswith('⚠️') and '下方' not in s and '仍在' not in s)

    if conditions_met >= 3:
        buy_ready = True

    # 计算买入量
    total_assets = 1016415  # 从 holdings.json 读取
    hp = os.path.join(DATA, 'holdings.json')
    if os.path.exists(hp):
        with open(hp) as f:
            hh = json.load(f)
        total_assets = hh.get('total_assets', total_assets)

    trial_pct = 0.02 if score >= 8.0 else 0.015
    budget = total_assets * trial_pct
    buy_qty = max(100, (int(budget / price) // 100) * 100)

    # 止损位
    if bottoms:
        stoploss_price = round(bottoms[-1]['price'] * 0.98, 2)
    else:
        stoploss_price = round(price * 0.95, 2)

    return {
        'name': name, 'code': code, 'score': score,
        'price': price, 'buy_qty': buy_qty,
        'stoploss': stoploss_price,
        'signals': signals,
        'conditions_met': conditions_met,
        'ready': buy_ready,
        'ma5': ma5, 'ma20': ma20,
    }

# ============================================================
# 主程序
# ============================================================

def main():
    # 加载数据
    hp = os.path.join(DATA, 'holdings.json')
    wp = os.path.join(DATA, 'watchlist.json')

    with open(hp) as f:
        holdings = json.load(f)
    with open(wp) as f:
        watchlist = json.load(f)

    # 收集所有代码
    all_codes = [h['code'] for h in holdings['holdings']]
    all_codes += [w['code'] for w in watchlist.get('watchlist', [])]
    all_codes = list(set(all_codes))

    prices = fetch_prices(all_codes)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    sell_orders = []
    buy_candidates = []

    # 检查所有持仓的卖出信号
    for h in holdings['holdings']:
        orders = check_sell(h, prices)
        sell_orders.extend(orders)

    # 检查所有观察池的买入信号
    existing_codes = {h['code'] for h in holdings['holdings']}
    for w in watchlist.get('watchlist', []):
        if w['code'] not in existing_codes:
            result = check_buy(w, prices)
            if result:
                buy_candidates.append(result)

    # ============================================================
    # 输出
    # ============================================================

    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║  买卖信号引擎  {now}                          ║")
    print(f"╠══════════════════════════════════════════════════════════╣")

    # 卖出
    urgent_sells = [o for o in sell_orders if '🔴' in o['action']]
    warn_sells = [o for o in sell_orders if '🟡' in o['action']]
    near_sl = [o for o in sell_orders if '⚠️止损' in o['action']]

    if urgent_sells or near_sl:
        print(f"║                                                              ║")
        print(f"║  📱 需要挂单的卖出                                          ║")
        print(f"╠══════════════════════════════════════════════════════════════╣")

        for o in urgent_sells + near_sl:
            print(f"║                                                              ║")
            print(f"║  {o['action']} {o['name']}                                     ║")
            print(f"║  {o['reason']}                                               ║")
            if o.get('type') != '提醒':
                print(f"║  ┌─────────────────────────────────────┐                    ║")
                print(f"║  │ 涨乐条件单                          │                    ║")
                print(f"║  │ 类型: {o.get('type','?'):<30s} │                    ║")
                if o.get('monitor'):
                    print(f"║  │ 监控价: ¥{o['monitor']:<28.2f} │                    ║")
                    print(f"║  │ 回落:   {o.get('fall','?'):<30s} │                    ║")
                if o.get('trigger'):
                    print(f"║  │ 触发价: ¥{o['trigger']:<28.2f} │                    ║")
                print(f"║  │ 数量:   {o.get('qty',0):<5d} 股 (市价委托)              │                    ║")
                print(f"║  └─────────────────────────────────────┘                    ║")

    if warn_sells:
        print(f"║                                                              ║")
        print(f"║  🟡 需要关注的持仓                                          ║")
        for o in warn_sells:
            print(f"║  {o['name']}: {o['reason']}")

    # 买入
    ready_buys = [b for b in buy_candidates if b['ready']]
    watching_buys = [b for b in buy_candidates if not b['ready']]

    print(f"╠══════════════════════════════════════════════════════════════╣")
    print(f"║                                                              ║")
    print(f"║  🎯 买入候选                                                ║")
    print(f"╠══════════════════════════════════════════════════════════════╣")

    if ready_buys:
        print(f"║  ✅ 触发买点的标的:                                         ║")
        for b in ready_buys:
            print(f"║                                                              ║")
            print(f"║  🟢 {b['name']} ({b['code']}) 评分{b['score']}                          ║")
            print(f"║  现价 ¥{b['price']:.2f}  MA5 {b['ma5']:.2f}  MA20 {b['ma20']:.2f}                        ║")
            for s in b['signals']:
                print(f"║  {'✅' if not s.startswith('⚠️') and '下方' not in s and '仍在' not in s else '❌'} {s}")
            print(f"║  ┌─────────────────────────────────────┐                    ║")
            print(f"║  │ 涨乐买入单                          │                    ║")
            print(f"║  │ 数量: {b['buy_qty']} 股                      │                    ║")
            print(f"║  │ 止损: ¥{b['stoploss']:.2f} (市价单)                  │                    ║")
            print(f"║  │ 仓位: {b['buy_qty']*b['price']/1016415*100:.1f}%                           │                    ║")
            print(f"║  └─────────────────────────────────────┘                    ║")
    else:
        print(f"║  ❌ 无触发买点的标的                                        ║")

    print(f"║                                                              ║")
    print(f"║  ⏳ 接近但未触发:                                           ║")
    for b in watching_buys:
        print(f"║  {b['name']:<6} {b['score']}分 现价{b['price']:.2f}  满足{b['conditions_met']}/4条  {'🟡差一点' if b['conditions_met']>=2 else '❌还远'}")

    # 持仓上限提醒
    count = len(holdings['holdings'])
    if count > 6:
        print(f"║                                                              ║")
        print(f"║  ⚠️ 持仓{count}只，超上限6只 → 新买前需先清一只              ║")

    print(f"╚══════════════════════════════════════════════════════════════╝")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手机一键取数（多多买菜 / 美团特价团）：你在手机上搜好、停在列表页第一屏，Mac 上跑一次，
它读当前页的无障碍树，按前台 App 自动选解析器，取前 N 条追加到 jsonl 并打印。不滑不点。

  python3 pipeline/cost/phone_grab.py            # 前 10 条 → cost/data/raw/<city>/<今天>/<app>.jsonl
  python3 pipeline/cost/phone_grab.py --n 5 --kw 拌面

多多买菜（拼多多 App 内，自研内核）：只有读屏（TalkBack）开着才读得到，脚本会检查。
美团特价团（原生 MRN 页面）：不用读屏。价格拆成 ¥ / 整数 / .小数 三个节点，脚本拼回去。
"""
import argparse, json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap = argparse.ArgumentParser()
ap.add_argument('--adb', default=os.path.expanduser('~/tools/scrcpy-macos-aarch64-v4.1/adb'))
ap.add_argument('--serial', default='T4ORZ5Q8FY4XTGKF')
ap.add_argument('--city', default='urumqi')
ap.add_argument('--n', type=int, default=10)
ap.add_argument('--kw', default=None, help='关键词/筛选说明，读不到时手动写')
ap.add_argument('--out', default=None)
ap.add_argument('--scroll', type=int, default=0, help='原生列表（贝壳）屏幕外的条目不在树里，给 N 就自动下滑 N 屏合并')
a = ap.parse_args()

def adb(*args):
    return subprocess.run([a.adb, '-s', a.serial, *args], capture_output=True, timeout=30)

focus = adb('shell', 'dumpsys', 'window').stdout.decode('utf-8', 'ignore')
pkg = (re.search(r'mCurrentFocus=Window\{[^ ]+ u0 ([\w.]+)/', focus) or [None, ''])[1]
PKGS = {'com.xunmeng.pinduoduo': 'ddmc', 'com.sankuai.meituan': 'meituan', 'com.lianjia.beike': 'beike', 'com.anjuke.android.app': 'anjuke'}
APP = PKGS.get(pkg)
def dump():
    xml = ''
    for _ in range(5):
        xml = adb('exec-out', 'uiautomator', 'dump', '/dev/tty').stdout.decode('utf-8', 'ignore')
        if len(xml) > 5000: return xml
        time.sleep(1)
    sys.exit('读不到界面（uiautomator dump 失败）。停到列表页再跑。')

xml = dump()
if not APP:
    m = re.search(r'package="((?:com\.xunmeng\.pinduoduo|com\.sankuai\.meituan|com\.lianjia\.beike|com\.anjuke\.android\.app))"', xml)
    APP = PKGS.get(m.group(1)) if m else None
if not APP:
    sys.exit(f'前台是 {pkg or "未知"}，不是拼多多/美团/贝壳/安居客。')
if APP == 'ddmc':
    tb = adb('shell', 'settings', 'get', 'secure', 'enabled_accessibility_services').stdout.decode().lower()
    if 'talkback' not in tb:
        sys.exit('多多买菜搜索结果页只有读屏开着才读得到。先开 TalkBack 再跑。')

def to_nodes(xml):
    return [(t.replace('&amp;', '&').replace('\u2006', ' ').replace('\u2009', ' '), int(x1), int(y1)) for t, x1, y1, x2, y2 in
         re.findall(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml) if t.strip()]
nodes = to_nodes(xml)
texts = [t for t, *_ in nodes]

def parse_ddmc():
    kw = a.kw or next((t for t in texts[:6] if t not in ('搜索', '返回') and len(t) <= 12), None)
    items, seen = [], set()
    for t in texts:
        m = re.match(r'^(.+?)，(\d+(?:\.\d{1,2})?)元$', t)
        if m and '购物车' not in t and m.group(1) not in seen:
            seen.add(m.group(1)); items.append({'name': m.group(1), 'price': float(m.group(2))})
    return kw, '综合', {'platform': '多多买菜', 'pickup': '鑫顺意超市'}, items

def parse_meituan():
    loc = next((t for t in texts if '地铁站' in t or t.endswith('站)')), None)
    kw = a.kw or next((t for t in texts if t.startswith('搜索') and len(t) > 2), None)
    rows = sorted(nodes, key=lambda r: (r[2], r[1]))
    # 每条团购从「店名 | 套餐名」开始，到下一条标题为止；价格三段（¥ / 整数 / .小数）y 不完全对齐，按区间找
    titles = [i for i, (t, x, y) in enumerate(rows) if re.search(r'\s\|\s', t) and x < 500 and y > 600]
    deals = []
    for k, i in enumerate(titles):
        block = rows[i + 1: titles[k + 1] if k + 1 < len(titles) else len(rows)]
        d = {'name': rows[i][0], 'store': None, 'distance': None, 'price': None, 'orig': None, 'sales': None}
        whole = frac = None
        for t, x, y in block:
            if re.match(r'^\d+(\.\d+)?(km|m)$', t): d['distance'] = t
            elif '（' in t and '店）' in t: d['store'] = t
            elif t.startswith('爆卖'): d['sales'] = t
            elif whole is None and re.match(r'^\d{1,4}$', t) and 480 <= x <= 600: whole = t
            elif frac is None and re.match(r'^\.\d{1,2}$', t) and x <= 700: frac = t
            elif d['orig'] is None and re.match(r'^¥\d+(\.\d+)?$', t): d['orig'] = float(t[1:])
        if whole is not None: d['price'] = float(whole + (frac or ''))
        deals.append(d)
    return kw, '默认', {'platform': '美团特价团', 'location': loc}, [d for d in deals if d['price'] is not None]

def parse_beike_page(nodes):
    # 原生 RecyclerView：标题「整租1居·小区」→ 规格「20㎡｜南｜高楼层｜电梯」→「距离1号线-南门站306m」→ 价格「860」+「元/月」
    rows = sorted(nodes, key=lambda r: (r[2], r[1]))
    out, cur = [], None
    for i, (t, x, y) in enumerate(rows):
        if re.match(r'^(整租|合租)\d居·', t):
            cur = {'name': t, 'spec': None, 'distance': None, 'price': None}; out.append(cur)
        elif cur:
            if '㎡' in t and cur['spec'] is None: cur['spec'] = t
            elif t.startswith('距离'): cur['distance'] = t
            elif re.match(r'^\d{3,6}$', t) and i + 1 < len(rows) and rows[i + 1][0].startswith('元/月') and cur['price'] is None:
                cur['price'] = float(t)
    return [o for o in out if o['price'] is not None]

def parse_anjuke_page(nodes):
    # 安居客：「整租 | 标题」→「1室·35㎡·小区·路」→ 标签 → 价格「2300」+「元/月」→「距1号线-南门502m」
    rows = sorted(nodes, key=lambda r: (r[2], r[1]))
    out, cur = [], None
    for i, (t, x, y) in enumerate(rows):
        if re.match(r'^(整租|合租)\s*\|', t):
            cur = {'name': t, 'spec': None, 'distance': None, 'price': None}; out.append(cur)
        elif cur:
            if '㎡' in t and cur['spec'] is None: cur['spec'] = t
            elif t.startswith('距'): cur['distance'] = t
            elif re.match(r'^\d{3,6}$', t) and i + 1 < len(rows) and rows[i + 1][0].startswith('元/月') and cur['price'] is None:
                cur['price'] = float(t)
    return [o for o in out if o['price'] is not None]

def parse_beike():
    page = parse_anjuke_page if APP == 'anjuke' else parse_beike_page
    bar = (300, 340) if APP == 'anjuke' else (340, 365)
    station = next((t for t, x, y in nodes if bar[0] <= y <= bar[1] and x < 200), None)
    filt = ' '.join(t for t, x, y in nodes if bar[0] <= y <= bar[1])
    items, seen = [], set()
    def take(ns):
        for o in page(ns):
            k = (o['name'], o['spec'], o['distance'], o['price'])
            if k not in seen: seen.add(k); items.append(o)
    take(nodes)
    stale = 0
    for _ in range(a.scroll):
        adb('shell', 'input', 'swipe', '640', '2300', '640', '800', '500'); time.sleep(2.5)
        before = len(items); take(to_nodes(dump()))
        stale = stale + 1 if len(items) == before else 0
        if stale >= 2: break
    return a.kw or station, '默认', {'platform': '安居客' if APP == 'anjuke' else '贝壳', 'filter': filt}, items

kw, sort, meta, items = {'ddmc': parse_ddmc, 'meituan': parse_meituan, 'beike': parse_beike, 'anjuke': parse_beike}[APP]()
if not items:
    sys.exit(f'这一页没解析出条目。页面头部：{texts[:8]}\n含|的节点：{[(t,x,y) for t,x,y in nodes if "|" in t][:5]}')
items = items[:a.n]
today = time.strftime('%Y-%m-%d')
out = a.out or os.path.join(ROOT, 'cost', 'data', 'raw', a.city, today.replace('-', ''), f'{APP}.jsonl')
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, 'a', encoding='utf-8') as f:
    for i, it in enumerate(items):
        f.write(json.dumps({'city': a.city, **meta, 'keyword': kw, 'sort': sort, 'rank': i + 1, **it,
                            'unit': 'CNY', 'fetched_at': today}, ensure_ascii=False) + '\n')
print(f'{meta["platform"]} {meta.get("location") or meta.get("pickup") or meta.get("filter")}  关键词「{kw}」 {len(items)} 条 → {os.path.relpath(out, ROOT)}')
for i, it in enumerate(items):
    extra = '  '.join(str(it[k]) for k in ('spec', 'store', 'distance', 'sales') if it.get(k))
    orig = f'（原价 {it["orig"]}）' if it.get('orig') else ''
    print(f'{i+1:>2}. {it["name"]}  {it["price"]}{orig}  {extra}')

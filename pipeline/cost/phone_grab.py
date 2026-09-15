#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
手机一键取数（多多买菜 / 美团特价团）：你在手机上搜好、停在列表页第一屏，Mac 上跑一次，
它读当前页的无障碍树，按前台 App 自动选解析器，取前 N 条追加到 jsonl 并打印。不滑不点。

  python3 pipeline/cost/phone_grab.py            # 前 10 条 → cost/data/raw/<city>/<今天>/<app>.jsonl
  python3 pipeline/cost/phone_grab.py --n 5 --kw 拌面
  python3 pipeline/cost/phone_grab.py --scroll 4 --n 40        # 贝壳/安居客：站名、排序、整租/合租 都从当前页面头部读，不用写；读不到才要 --kw / --sort
  python3 pipeline/cost/phone_grab.py --scroll 8 --max-price 3000   # 按价格升序时超过 3000 就停
  贝壳租房（整租/合租都行）：手机停在列表第一屏，Mac 跑
  python3 pipeline/cost/phone_grab.py --city urumqi --kw 南门 --sort 价格从低到高 --scroll 4 --n 40
  → cost/data/raw/urumqi/<今天>/beike.jsonl（每条带 type 整租/合租、keyword、sort），然后 python3 pipeline/cost/rent_from_beike.py urumqi 算档位房租

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
ap.add_argument('--max-price', type=float, default=None, help='按价格升序取数时，滑到条目价格超过这个数就停（贝壳/安居客）')
ap.add_argument('--sort', default=None, help='列表当时的排序（贝壳：价格从低到高 / 默认排序 …）。头部筛选条上能读到就自动取，读不到必须写')
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
        m = re.match(r'^(整租|合租)(?:\d居)?[·\s]', t)      # 整租1居·小区 / 合租3居·小区 / 合租·小区（合租页标题不一定带「N居」，2026-09-15 放宽）
        if m:
            cur = {'name': t, 'type': m.group(1), 'spec': None, 'distance': None, 'price': None}; out.append(cur)
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
        m = re.match(r'^(整租|合租)\s*\|', t)
        if m:
            cur = {'name': t, 'type': m.group(1), 'spec': None, 'distance': None, 'price': None}; out.append(cur)
        elif cur:
            if '㎡' in t and cur['spec'] is None: cur['spec'] = t
            elif t.startswith('距'): cur['distance'] = t
            elif re.match(r'^\d{3,6}$', t) and i + 1 < len(rows) and rows[i + 1][0].startswith('元/月') and cur['price'] is None:
                cur['price'] = float(t)
    return [o for o in out if o['price'] is not None]

def screen_size():
    m = re.search(r'(\d+)x(\d+)', adb('shell', 'wm', 'size').stdout.decode('utf-8', 'ignore'))
    return (int(m.group(1)), int(m.group(2))) if m else (1280, 2772)

STATION = re.compile(r'(号线|地铁|站)')
SORTS = ('价格从低到高', '价格从高到低', '默认排序', '最新发布', '距离最近', '面积从小到大', '面积从大到小', '综合排序')
POPUP = ('我知道了', '以后再说', '立即升级', '暂不', '允许', '去开启', '领取', '关闭')

def known_stations(city):
    """城市 JSON 里四档的代表车站名（去掉括号说明），头部里出现的就是选中的站。"""
    try:
        d = json.load(open(os.path.join(ROOT, 'cost', 'data', 'cities', f'{city}.json'), encoding='utf-8'))
        names = set()
        for t in d.get('tiers', []):
            for st in t.get('stations', []): names.add(re.sub(r'[（(].*$', '', st).strip())
        return {n for n in names if 1 < len(n) <= 8}
    except Exception:
        return set()

def beike_header(ns):
    """筛选条不按写死的 y 找（那是一台手机的值）：先找第一张房源卡的 y，卡上方所有节点就是头部。
       站名三条路：① 头部里出现两次的短词（贝壳：选中的站在筛选条上一次、站名 tab 里一次）；② 头部里出现城市 JSON 的代表车站名；③ 含「站/号线」的短节点。
       排序 = 头部里能认出的排序词（贝壳/安居客的排序钮是图标，树里多半没有字 → 读不到就按「默认」，按价排过必须 --sort 写明）。"""
    rows = sorted(ns, key=lambda r: (r[2], r[1]))
    first = next((y for t, x, y in rows if re.match(r'^(整租|合租)(\d居)?[·\s|]', t)), None)   # 第一张房源卡的标题
    head = [t for t, x, y in rows if first is None or y < first]
    short = [t for t in head if 1 < len(t) <= 6 and re.fullmatch(r'[\u4e00-\u9fff]+', t)]
    dup = [t for t in short if short.count(t) >= 2 and t not in ('整租', '合租', '租金', '户型', '更多', '筛选', '排序')]   # 选中的站：筛选条一次 + 站名 tab 一次
    ks = known_stations(a.city)
    station = dup[0] if dup else next((t for t in head if t in ks), None) or next((t for t in head if re.search(r'站|号线', t) and len(t) <= 12), None)
    sort = next((w for t in head for w in SORTS if w in t), None)
    return station, sort, ' '.join(t for t in head if len(t) <= 14)

def parse_beike():
    page = parse_anjuke_page if APP == 'anjuke' else parse_beike_page
    W, H = screen_size()
    pops = [t for t in texts if t in POPUP]
    if pops: print(f'提示：界面上有弹窗/按钮 {pops}，可能挡住列表；脚本不点，挡住了就手动关掉再跑。', file=sys.stderr)
    station, sort_seen, filt = beike_header(nodes)
    items, seen = [], set()
    def take(ns):
        for o in page(ns):
            k = (o['name'], o['spec'], o['distance'], o['price'])
            if k not in seen: seen.add(k); items.append(o)
    take(nodes)
    stale = 0
    for _ in range(a.scroll):
        if a.max_price is not None and items and items[-1]['price'] > a.max_price: break   # 按价格升序时超上限就不再滑
        adb('shell', 'input', 'swipe', str(W // 2), str(int(H * 0.83)), str(W // 2), str(int(H * 0.29)), '500'); time.sleep(2.5)
        before = len(items); take(to_nodes(dump()))
        stale = stale + 1 if len(items) == before else 0
        if stale >= 2: break
    if a.max_price is not None: items[:] = [o for o in items if o['price'] <= a.max_price]
    sort = a.sort or sort_seen
    if not sort:
        sort = '默认'; print(f'提示：排序方式树里读不到（排序钮是图标），按「默认」记；如果你按价格排过序，重跑加 --sort 价格从低到高。', file=sys.stderr)
    kw = a.kw or station
    if not kw:
        sys.exit(f'站名读不到（头部：{filt[:80]}），用 --kw 写站名。')
    types = sorted({o['type'] for o in items})
    return kw, sort, {'platform': '安居客' if APP == 'anjuke' else '贝壳', 'filter': filt, 'type': '/'.join(types)}, items

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

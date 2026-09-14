#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多多买菜（拼多多 App 内）关键词搜索抓取：读无障碍树，不 OCR、不抓包、不改系统设置。

实测结论（2026-09-14，REDMI K80 Ultra，拼多多 App）：
- 搜索结果页是拼多多自研内核 meco.webkit.WebView，平时无障碍树是空的；
  **系统开着读屏（TalkBack）时**它才把商品挂进树里，每个商品一条：
  "30枚/板【五谷源】新鲜红壳鸡蛋/净重1.65kg±50g，20.99元"。
- 读屏开着时 adb 的 input tap / swipe 照常生效（注入事件不经过读屏的触摸浏览层）。
- 中文关键词：点搜索框 → input text 拼音 → 空格选输入法第一候选 → 校验搜索框文本 → 点「搜索」。
- 结果页有 综合/销量/秒杀/价格 排序，本脚本按「销量」抓，rank 即销量排序名次。

用法（先在手机上开读屏，再跑）：
  python3 ddmc_search.py --serial T4ORZ5Q8FY4XTGKF --city urumqi --out cost/data/raw/urumqi/20260914/ddmc_search.jsonl
  python3 ddmc_search.py --serial ... --kw 鸡蛋:jidan --kw 大米:dami
"""
import argparse, json, os, re, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument('--adb', default=os.path.expanduser('~/tools/scrcpy-macos-aarch64-v4.1/adb'))
ap.add_argument('--serial', required=True)
ap.add_argument('--city', default='urumqi')
ap.add_argument('--pickup', default='鑫顺意超市', help='自提点名，从首页「当前自提点是…」读到的')
ap.add_argument('--kw', action='append', help='中文:拼音[,备选拼音]，可多次；不给就用篮子默认六项')
ap.add_argument('--out', required=True)
ap.add_argument('--max-pages', type=int, default=30)
ap.add_argument('--sort', default='销量', choices=['综合', '销量', '价格'])
a = ap.parse_args()

DEFAULT_KW = ['鸡蛋:jidan', '纯牛奶:chunniunai', '大米:dami', '吐司:tusi,tusimianbao', '可乐:kele', '啤酒:pijiu']
HOME = 'pinduoduo://com.xunmeng.pinduoduo/ywgnpxpt.html?_p_page=vgt_search'   # 冷启动后落在多多买菜搜索页
SEARCH_BOX = (500, 226)
SEARCH_BTN = (1142, 227)
SORT_TAB = {'综合': (190, 370), '销量': (505, 370), '价格': (1050, 370)}
PRODUCT = re.compile(r'^(?P<name>.+?)，(?P<price>\d+(?:\.\d{1,2})?)元$')

def adb(*args, timeout=25):
    return subprocess.run([a.adb, '-s', a.serial, *args], capture_output=True, timeout=timeout)

def tap(x, y, wait=3.0):
    adb('shell', 'input', 'tap', str(x), str(y)); time.sleep(wait)

def dump(tries=5):
    for _ in range(tries):
        xml = adb('exec-out', 'uiautomator', 'dump', '/dev/tty').stdout.decode('utf-8', 'ignore')
        if len(xml) > 5000:
            return xml
        time.sleep(1)
    return ''

def nodes_of(xml):
    return [(t, int(x1), int(y1), int(x2), int(y2)) for t, x1, y1, x2, y2 in
            re.findall(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml) if t.strip()]

def edit_text(xml):
    m = re.search(r'<node[^>]*text="([^"]*)"[^>]*class="android.widget.EditText"', xml)
    return m.group(1) if m else None

def talkback_on():
    r = adb('shell', 'settings', 'get', 'secure', 'enabled_accessibility_services').stdout.decode()
    return 'talkback' in r.lower()

def products(xml):
    out = []
    for t, *_ in nodes_of(xml):
        if '点击加入购物车' in t: continue
        m = PRODUCT.match(t)
        if m: out.append((m.group('name'), float(m.group('price'))))
    return out

def search(zh, pinyins):
    adb('shell', 'am', 'force-stop', 'com.xunmeng.pinduoduo'); time.sleep(1.5)
    adb('shell', 'am', 'start', '-a', 'android.intent.action.VIEW', '-d', HOME); time.sleep(8)
    dump(tries=2)
    for py in pinyins:
        tap(*SEARCH_BOX, wait=2.5)
        adb('shell', 'input', 'text', py); time.sleep(2)
        adb('shell', 'input', 'keyevent', 'KEYCODE_SPACE'); time.sleep(1.5)   # 输入法第一候选
        got = edit_text(dump())
        if got == zh: break
        print(f'  拼音 {py} 上屏成了 {got!r}，清掉重试', file=sys.stderr)
        adb('shell', 'input', 'keyevent', 'KEYCODE_MOVE_END')
        for _ in range(len(got or '') + 2): adb('shell', 'input', 'keyevent', 'KEYCODE_DEL')
    else:
        return None
    tap(*SEARCH_BTN, wait=5)
    if a.sort != '综合': tap(*SORT_TAB[a.sort], wait=4)
    seen, order, stale = {}, [], 0
    for page in range(a.max_pages):
        got = products(dump())
        new = [(n, p) for n, p in got if n not in seen]
        for n, p in new: seen[n] = p; order.append(n)
        stale = stale + 1 if not new else 0
        if stale >= 3: break
        adb('shell', 'input', 'swipe', '640', '2300', '640', '900', '400'); time.sleep(2.5)
    return [(n, seen[n]) for n in order]

if not talkback_on():
    sys.exit('手机上没开读屏（TalkBack）。搜索结果页只有读屏开着才读得到，先开再跑。')
os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
today = time.strftime('%Y-%m-%d')
with open(a.out, 'a', encoding='utf-8') as f:
    for spec in (a.kw or DEFAULT_KW):
        zh, pys = spec.split(':', 1)
        print(f'搜 {zh}', file=sys.stderr)
        res = search(zh, pys.split(','))
        if res is None:
            print(f'  {zh}: 拼音上屏失败，跳过', file=sys.stderr); continue
        print(f'  {zh}: {len(res)} 条（按{a.sort}）', file=sys.stderr)
        for i, (n, p) in enumerate(res):
            f.write(json.dumps({'city': a.city, 'platform': '多多买菜', 'pickup': a.pickup, 'keyword': zh, 'sort': a.sort,
                                'rank': i + 1, 'name': n, 'price': p, 'unit': 'CNY', 'fetched_at': today}, ensure_ascii=False) + '\n')
        f.flush()

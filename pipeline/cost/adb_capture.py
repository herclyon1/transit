#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
被动采集：用户在手机上自己搜、自己滑，本脚本每 N 秒 uiautomator dump 一次，
把屏幕上出现过的「商品名 + 价格」去重记进 jsonl。不发任何点击，不需要小米的
「USB 调试（安全设置）」。

用法：
  python3 adb_capture.py --serial 192.168.2.2:42357 --city urumqi --out cost/data/raw/urumqi/20260914/capture.jsonl
停止：Ctrl-C，或另开终端 touch <out>.stop
"""
import argparse, json, os, re, subprocess, sys, time, hashlib

ap = argparse.ArgumentParser()
ap.add_argument('--adb', default=os.path.expanduser('~/tools/scrcpy-macos-aarch64-v4.1/adb'))
ap.add_argument('--serial', required=True)
ap.add_argument('--city', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--interval', type=float, default=2.0)
a = ap.parse_args()

def adb(*args, timeout=15):
    return subprocess.run([a.adb, '-s', a.serial, *args], capture_output=True, timeout=timeout)

PRICE = re.compile(r'^[¥￥]?\s*(\d{1,6}(?:\.\d{1,2})?)\s*(?:元|円|/份|/袋|/盒|起)?$')
SKIP = re.compile(r'已拼|已售|人买过|人下单|包赔|包邮|好评率|抢购|加入购物车|立即|搜索|返回|限购|限时|直降|券后|折|满\d|减\d|^\d{1,2}:\d{2}')

seen = set()
if os.path.exists(a.out):
    for line in open(a.out, encoding='utf-8'):
        try: seen.add(json.loads(line)['key'])
        except Exception: pass
os.makedirs(os.path.dirname(a.out), exist_ok=True)
outf = open(a.out, 'a', encoding='utf-8')
stop_flag = a.out + '.stop'
print(f'capturing every {a.interval}s → {a.out}  (touch {stop_flag} to stop)', flush=True)

last_hash = None
while not os.path.exists(stop_flag):
    t0 = time.time()
    try:
        r = adb('exec-out', 'uiautomator', 'dump', '/dev/tty')
        xml = r.stdout.decode('utf-8', 'ignore')
    except Exception as e:
        print('dump failed:', e, flush=True); time.sleep(a.interval); continue
    h = hashlib.md5(xml.encode()).hexdigest()
    if h != last_hash:
        last_hash = h
        pkg = (re.search(r'package="([^"]+)"', xml) or [None, '?'])[1]
        nodes = re.findall(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
        rows = [(t.strip(), int(y1), int(x1), int(y2)) for t, x1, y1, x2, y2 in nodes if t.strip()]
        rows.sort(key=lambda r: (r[1], r[2]))
        # 价格节点：向上找最近的一条像商品名的文本（长度≥6，不含促销词）
        new = 0
        for i, (t, y1, x1, y2) in enumerate(rows):
            m = PRICE.match(t)
            if not m: continue
            price = float(m.group(1))
            name = None
            for j in range(i - 1, max(-1, i - 12), -1):
                tj = rows[j][0]
                if len(tj) >= 6 and not SKIP.search(tj) and not PRICE.match(tj) and y1 - rows[j][1] < 900:
                    name = tj; break
            if not name: continue
            key = f'{name}|{price}'
            if key in seen: continue
            seen.add(key); new += 1
            outf.write(json.dumps({'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'city': a.city, 'app': pkg,
                                   'name': name, 'price': price, 'key': key}, ensure_ascii=False) + '\n')
        outf.flush()
        if new: print(f'{time.strftime("%H:%M:%S")} {pkg} +{new} (total {len(seen)})', flush=True)
    dt = time.time() - t0
    time.sleep(max(0.2, a.interval - dt))
print('stopped', flush=True)

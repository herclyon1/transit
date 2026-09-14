#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOSS 直聘 App 正文扫描：按关键词搜（城市已在 App 里切好），逐条点开读「职位详情」正文，
抓正文里写死的工资（每小时 N 元 / N 元/时 / 日薪 N / 底薪 N / 保底 N），存 jsonl。
列表标题栏永远是区间，只有正文才可能有单一数字，所以必须点进去。
用法：python3 boss_scan.py --kw 便利店 --kw 收银员 --n 6 --out cost/data/raw/urumqi/20260915/boss.jsonl
前提：手机 USB 连着，BOSS App 已登录、城市已切到目标城市、停在首页。
"""
import argparse, json, os, re, subprocess, sys, time
ap=argparse.ArgumentParser()
ap.add_argument('--adb', default=os.path.expanduser('~/tools/scrcpy-macos-aarch64-v4.1/adb'))
ap.add_argument('--serial', default='T4ORZ5Q8FY4XTGKF')
ap.add_argument('--kw', action='append', required=True, help='关键词:拼音，如 便利店:bianlidian')
ap.add_argument('--n', type=int, default=6)
ap.add_argument('--city', default='urumqi')
ap.add_argument('--out', required=True)
a=ap.parse_args()
def adb(*args): return subprocess.run([a.adb,'-s',a.serial,*args],capture_output=True,timeout=40)
def tap(x,y,w=2.5): adb('shell','input','tap',str(x),str(y)); time.sleep(w)
def dump():
    for _ in range(5):
        x=adb('exec-out','uiautomator','dump','/dev/tty').stdout.decode('utf-8','ignore')
        if len(x)>5000: return x
        time.sleep(1)
    return ''
def nodes(x): return [(t.replace('&amp;','&').replace('&#10;','\n'),int(x1),int(y1),int(x2),int(y2)) for t,x1,y1,x2,y2 in re.findall(r'<node[^>]*text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"',x) if t.strip()]
EXACT=re.compile(r'(每小时\s*\d+(?:\.\d+)?\s*元|\d+(?:\.\d+)?\s*元\s*/?\s*(?:每)?(?:小时|时)(?!\d)|时薪\s*\d+(?:\.\d+)?|日薪\s*\d+|\d+\s*元\s*/\s*天|每天\s*\d+\s*元|一天\s*\d+\s*元|底薪\s*\d{3,5}|保底\s*\d{3,5}|(?<![-–~\d])月薪\s*\d{3,5}(?![-–~\d]))')
def search(kw,py):
    tap(500,168); tap(640,235,1)
    adb('shell','input','keyevent','KEYCODE_MOVE_END')
    for _ in range(8): adb('shell','input','keyevent','KEYCODE_DEL')
    adb('shell','input','text',py); time.sleep(2); adb('shell','input','keyevent','KEYCODE_SPACE'); time.sleep(1.5)
    x=dump(); box=next((t for t,x1,y1,x2,y2 in nodes(x) if y1<300 and x1<400),None)
    if box!=kw: print(f'  搜索框是 {box!r} 不是 {kw}，跳过',file=sys.stderr); return False
    tap(1117,348,5); return True
def read_detail():
    x=dump(); ns=nodes(x)
    title=next((t for t,x1,y1,*_ in ns if y1<300 and x1<100),'')
    pay=next((t for t,x1,y1,*_ in ns if 380<y1<450),'')
    loc=next((t for t,x1,y1,*_ in ns if 480<y1<540 and x1<100),'')
    who=[t for t,x1,y1,*_ in ns if 700<y1<1000 and x1>250]
    body=max((t for t,*_ in ns if len(t)>60), key=len, default='')
    return {'title':title,'pay':pay,'loc':loc,'poster':' | '.join(who[:3]),'exact':EXACT.findall(body),'body':body[:600]}
os.makedirs(os.path.dirname(os.path.abspath(a.out)),exist_ok=True)
outf=open(a.out,'a',encoding='utf-8'); today=time.strftime('%Y-%m-%d')
for spec in a.kw:
    kw,py=spec.split(':')
    print(f'== {kw}',file=sys.stderr)
    if not search(kw,py): continue
    done=0; seen=set(); scrolls=0
    while done<a.n and scrolls<4:
        ns=nodes(dump())
        cards=[(t,x1,y1,x2,y2) for t,x1,y1,x2,y2 in ns if x1==78 and 700<y1<2500 and len(t)<50 and not re.match(r'(经验|学历|\d)',t)]
        cards=[c for c in cards if re.search(r'元',next((t for t,x1,y1,*_ in ns if abs(y1-c[2])<20 and x1>800),''))]
        new=[c for c in cards if c[0] not in seen]
        if not new:
            adb('shell','input','swipe','640','2200','640','900','500'); time.sleep(2.5); scrolls+=1; continue
        for t,x1,y1,x2,y2 in new:
            if done>=a.n: break
            seen.add(t); tap((x1+x2)//2,(y1+y2)//2,4)
            # 可能弹出「标记不合适」气泡，再点一下空白处
            x=dump()
            if 'PopupWindow' in adb('shell','dumpsys','window').stdout.decode('utf-8','ignore').split('mCurrentFocus')[1][:80]: tap(640,1500,1.5)
            d=read_detail(); d.update({'city':a.city,'platform':'BOSS直聘','keyword':kw,'list_title':t,'fetched_at':today})
            outf.write(json.dumps(d,ensure_ascii=False)+'\n'); outf.flush()
            print(f"  {d['pay']:<12} {d['title'][:18]:<18} | {d['poster'][:30]} | {d['exact']}",file=sys.stderr)
            done+=1
            adb('shell','input','keyevent','KEYCODE_BACK'); time.sleep(2.5)
    adb('shell','input','keyevent','KEYCODE_BACK'); time.sleep(2)
print('done',file=sys.stderr)

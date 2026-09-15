#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIG 验收（DESIGN-HIG.md「验收程序」第 2、3 关）。
  前提：模拟器已启动（iPhone 18 Pro Max / iOS 27），本地 `python3 pipeline/rangeserver.py 8788` 在跑。
  python3 pipeline/ui/accept.py
    第 2 关：在模拟器 Safari 里逐页打开 <页>?accept，页面里的 ui/accept.js 量 DOM，POST 回 rangeserver 写 .accept/<页>.json；
            本脚本汇总打印每页超差项。数字全部在真机字号（17pt）下量，不用桌面浏览器。
    第 3 关：截地图 App 首页做基准 + 每页截图，拼成 .accept/compare.png 供目测（内缩、圆角、抓手、玻璃、字体）。
退出码：有超差 = 1。
"""
import subprocess, sys, time, os, re, json, glob
HERE=os.path.dirname(os.path.abspath(__file__)); REPO=os.path.abspath(os.path.join(HERE,'..','..')); OUT=os.path.join(REPO,'.accept'); os.makedirs(OUT,exist_ok=True)
BASE=os.environ.get('ACCEPT_BASE','http://127.0.0.1:8788')
r=subprocess.run(['xcrun','simctl','list','devices','booted'],capture_output=True,text=True).stdout
m=re.search(r'\(([0-9A-F-]{36})\) \(Booted\)',r); UDID=os.environ.get('SIM_UDID') or (m.group(1) if m else None)
if not UDID: sys.exit('没有已启动的模拟器：xcrun simctl boot "iPhone 18 Pro Max"')
try:
    import urllib.request; urllib.request.urlopen(BASE+'/ui/hig.css',timeout=3)
except Exception as e: sys.exit(f'{BASE} 没起来：python3 pipeline/rangeserver.py 8788（{e}）')
def shot(name):
    p=os.path.join(OUT,name+'.png'); subprocess.run(['xcrun','simctl','io',UDID,'screenshot',p],capture_output=True); return p
pages={'index':'/index.html','cost':'/cost/index.html','osaka':'/osaka/index.html','japan':'/japan/index.html','quiz':'/quiz/index.html'}
for k in pages:
    f=os.path.join(OUT,k+'.json')
    if os.path.exists(f): os.remove(f)
# 第 3 关基准：地图 App
subprocess.run(['xcrun','simctl','launch',UDID,'com.apple.Maps'],capture_output=True); time.sleep(5); shot('ref_maps')
bad=0; rows=[]
for k,u in pages.items():
    subprocess.run(['xcrun','simctl','openurl',UDID,BASE+u+'?accept=1&quiet=1'],capture_output=True)
    f=os.path.join(OUT,k+'.json'); t0=time.time()
    while not os.path.exists(f) and time.time()-t0<25: time.sleep(0.5)
    time.sleep(1.5); shot('page_'+k)
    if not os.path.exists(f): print(f'✗ {k}: 25 秒内没收到验收结果（页面没加载完或 accept.js 没跑）'); bad+=1; continue
    d=json.load(open(f)); res=d['results']; fails=[x for x in res if not x['pass']]
    print(f"{'✓' if not fails else '✗'} {k}  {d['w']}×{d['h']} 根字号 {d['root']}  通过 {len(res)-len(fails)}/{len(res)}")
    for x in fails: print(f"     ✗ {x['name']}: 实测 {x['got']} 期望 {x['want']}" + (f"  [{x['note']}]" if x.get('note') else ''))
    bad+=len(fails)
# 拼对照图：地图 App + 各页，各取上半和 Sheet 顶部
try:
    from PIL import Image
    ims=[Image.open(os.path.join(OUT,n+'.png')) for n in ['ref_maps']+['page_'+k for k in pages]]
    w=ims[0].width//3; h=ims[0].height//3
    small=[im.resize((w,h)) for im in ims]
    sheet=Image.new('RGB',(w*len(small),h),'white')
    for i,im in enumerate(small): sheet.paste(im,(i*w,0))
    sheet.save(os.path.join(OUT,'compare.png')); print('对照图 .accept/compare.png（左起：地图 App、首页、薪资、大阪、学習、クイズ）')
except Exception as e: print('拼图跳过：',e)
print('OK' if not bad else f'共 {bad} 项超差'); sys.exit(1 if bad else 0)

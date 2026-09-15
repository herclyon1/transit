#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HIG 验收（DESIGN-HIG.md「验收程序」第 2、3 关）。
  前提：模拟器已启动（iPhone 18 Pro Max / iOS 27），本地 `python3 pipeline/rangeserver.py 8788` 在跑。
  python3 pipeline/ui/accept.py
    第 2 关：在模拟器 Safari 里逐页打开 <页>?accept，页面里的 ui/accept.js 量 DOM，POST 回 rangeserver 写 .accept/<页>.json；
            本脚本汇总打印每页超差项。数字全部在真机字号（17pt）下量，不用桌面浏览器。
    第 3 关：截地图 App 首页做基准 + 每页截图，拼成 .accept/compare.png 供目测（内缩、圆角、抓手、玻璃、字体）。
  python3 pipeline/ui/accept.py --webapp
    主屏幕网页 App 模式（整屏 956、状态栏半透明，和地图 App 同一口径）：先 python3 pipeline/ui/webclips.py 往模拟器
    主屏幕第二页装五个网页 App 图标（URL 带 ?accept=1&quiet=1），然后逐个点开（simctl 打不开网页 App，只能点；
    网页 App 里跨页跳转会让视口变 894，所以必须逐个从图标点）；本脚本等结果、来一页截一页、汇总。
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
WEBAPP='--webapp' in sys.argv
for k in pages:
    f=os.path.join(OUT,k+'.json')
    if os.path.exists(f): os.remove(f)
# 第 3 关基准：地图 App
subprocess.run(['xcrun','simctl','launch',UDID,'com.apple.Maps'],capture_output=True); time.sleep(5); shot('ref_maps')
bad=0; rows=[]
if WEBAPP:
    subprocess.run(['xcrun','simctl','terminate',UDID,'com.apple.webapp'],capture_output=True)
    print('网页 App 模式：请在模拟器主屏幕第二页逐个点开 首页/薪资/大阪/学習/クイズ（顺序随意），每页等它截完图再点下一个；总共等 300 秒…', flush=True)
    got=set(); t0=time.time()
    while len(got)<len(pages) and time.time()-t0<300:
        for k in pages:
            if k in got: continue
            f=os.path.join(OUT,k+'.json')
            if os.path.exists(f): time.sleep(1.5); shot('webapp_'+k); got.add(k); print('  收到',k, flush=True)
        time.sleep(0.5)
for k,u in pages.items():
    if not WEBAPP:
        subprocess.run(['xcrun','simctl','openurl',UDID,BASE+u+'?accept=1&quiet=1'],capture_output=True)
        f=os.path.join(OUT,k+'.json'); t0=time.time()
        while not os.path.exists(f) and time.time()-t0<25: time.sleep(0.5)
        time.sleep(1.5); shot('page_'+k)
    f=os.path.join(OUT,k+'.json')
    if not os.path.exists(f): print(f'✗ {k}: 没收到验收结果（页面没加载完或 accept.js 没跑）'); bad+=1; continue
    d=json.load(open(f)); res=d['results']; fails=[x for x in res if not x['pass']]
    print(f"{'✓' if not fails else '✗'} {k}  {d['w']}×{d['h']}{'（网页 App）' if d.get('standalone') else ''} 根字号 {d['root']}  通过 {len(res)-len(fails)}/{len(res)}")
    for x in fails: print(f"     ✗ {x['name']}: 实测 {x['got']} 期望 {x['want']}" + (f"  [{x['note']}]" if x.get('note') else ''))
    bad+=len(fails)
# 拼对照图：地图 App + 各页，各取上半和 Sheet 顶部
try:
    from PIL import Image
    ims=[Image.open(os.path.join(OUT,n+'.png')) for n in ['ref_maps']+[('webapp_' if WEBAPP else 'page_')+k for k in pages]]
    w=ims[0].width//3; h=ims[0].height//3
    small=[im.resize((w,h)) for im in ims]
    sheet=Image.new('RGB',(w*len(small),h),'white')
    for i,im in enumerate(small): sheet.paste(im,(i*w,0))
    sheet.save(os.path.join(OUT,'compare_webapp.png' if WEBAPP else 'compare.png')); print('对照图 .accept/'+('compare_webapp.png' if WEBAPP else 'compare.png')+'（左起：地图 App、首页、薪资、大阪、学習、クイズ）')
except Exception as e: print('拼图跳过：',e)
print('OK' if not bad else f'共 {bad} 项超差'); sys.exit(1 if bad else 0)

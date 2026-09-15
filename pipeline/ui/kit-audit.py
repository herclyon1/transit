#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组件对账（用户 2026-09-15：「做个工具去验收网页上的组件有哪些是官方的，哪些还是原来老的」）。
页面里的 ui/kitaudit.js 把每个看得见的控件对上一个 Kit 组件（✅ 对上 / ◇ Kit 无、清单登记过 / ⚠ 对上了但尺寸不对 / ✗ 没对上 = 老样式），
本脚本在两端跑完汇总：
  Mac   = 无头 Chrome 1440×900（pointer:fine → hig.css 11b 的 macOS 27 Kit 数字）
  手机  = 已启动的 iPhone 模拟器 Safari（iOS 27 Kit 数字；rangeserver 收 POST 写 .accept/kitaudit_<页>_ios.json）
  python3 pipeline/ui/kit-audit.py                 两端五页
  python3 pipeline/ui/kit-audit.py --mac cost quiz  只跑 Mac 的两页
  python3 pipeline/ui/kit-audit.py --phone
前提：python3 pipeline/rangeserver.py 8788 在跑（ACCEPT_BASE 可改）；手机端还要模拟器已启动。
退出码：有 ⚠/✗ = 1。列表按页打印，每条给「元素 · 实测 · 对应 Kit 组件 · 差在哪」，直接拿去改。
"""
import subprocess, sys, time, os, re, json, socket, base64, struct, urllib.request, tempfile, shutil
HERE=os.path.dirname(os.path.abspath(__file__)); REPO=os.path.abspath(os.path.join(HERE,'..','..')); OUT=os.path.join(REPO,'.accept'); os.makedirs(OUT,exist_ok=True)
BASE=os.environ.get('ACCEPT_BASE','http://127.0.0.1:8788')
CHROME=os.environ.get('CHROME','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PAGES={'index':'/index.html','cost':'/cost/index.html','osaka':'/osaka/index.html','japan':'/japan/index.html','quiz':'/quiz/index.html'}
args=[a for a in sys.argv[1:] if not a.startswith('--')]; flags=[a for a in sys.argv[1:] if a.startswith('--')]
pages={k:v for k,v in PAGES.items() if not args or k in args}
do_mac='--phone' not in flags; do_phone='--mac' not in flags
try: urllib.request.urlopen(BASE+'/ui/hig.css',timeout=3)
except Exception as e: sys.exit(f'{BASE} 没起来：python3 pipeline/rangeserver.py 8788（{e}）')

class WS:   # 最小 WebSocket 客户端（只为 CDP，不装依赖）
    def __init__(s,url):
        host,port=url.split('/')[2].split(':'); path='/'+'/'.join(url.split('/')[3:])
        s.sock=socket.create_connection((host,int(port))); key=base64.b64encode(os.urandom(16)).decode()
        s.sock.send(f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        buf=b''
        while b'\r\n\r\n' not in buf: buf+=s.sock.recv(4096)
        s.id=0
    def send(s,method,params=None):
        s.id+=1; data=json.dumps({'id':s.id,'method':method,'params':params or {}}).encode(); mask=os.urandom(4); L=len(data)
        hdr=bytes([0x81])+(bytes([0x80|L]) if L<126 else bytes([0x80|126])+struct.pack('>H',L) if L<65536 else bytes([0x80|127])+struct.pack('>Q',L))
        s.sock.send(hdr+mask+bytes(b^mask[i%4] for i,b in enumerate(data)))
        while True:
            m=s.recv()
            if m.get('id')==s.id: return m
    def recvn(s,n):
        b=b''
        while len(b)<n:
            c=s.sock.recv(n-len(b))
            if not c: raise EOFError('CDP 断了')
            b+=c
        return b
    def recv(s):
        h=s.recvn(2); L=h[1]&0x7f
        if L==126: L=struct.unpack('>H',s.recvn(2))[0]
        elif L==127: L=struct.unpack('>Q',s.recvn(8))[0]
        return json.loads(s.recvn(L))

PORT=[9334]
def run_mac(url):
    PORT[0]+=1; port=PORT[0]; prof=tempfile.mkdtemp()   # 每页换端口：上一个 Chrome 退出要一两秒，同端口会撞上
    p=subprocess.Popen([CHROME,'--headless=new','--use-angle=swiftshader','--enable-unsafe-swiftshader','--hide-scrollbars',f'--remote-debugging-port={port}',f'--user-data-dir={prof}','--window-size=1440,900','about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        page=None
        for i in range(100):
            try: page=next(t for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json')) if t['type']=='page'); break
            except Exception: time.sleep(0.2)
        if not page: print('  无头 Chrome 没起来'); return None
        ws=WS(page['webSocketDebuggerUrl'])
        ws.send('Emulation.setDeviceMetricsOverride',{'width':1440,'height':900,'deviceScaleFactor':2,'mobile':False})
        ws.send('Page.navigate',{'url':url})
        for i in range(90):
            r=ws.send('Runtime.evaluate',{'expression':'window.__kitDone?JSON.stringify(window.__kit):null','returnByValue':True})
            v=r.get('result',{}).get('result',{}).get('value')
            if v: return json.loads(v)
            time.sleep(0.5)
        return None
    finally:
        p.terminate()
        try: p.wait(timeout=8)
        except Exception: p.kill()
        shutil.rmtree(prof,ignore_errors=True)

def run_phone(k,u):
    r=subprocess.run(['xcrun','simctl','list','devices','booted'],capture_output=True,text=True).stdout
    ms=re.findall(r'^\s*(.*?) \(([0-9A-F-]{36})\) \(Booted\)',r,re.M); pref=[uu for n,uu in ms if 'iPhone' in n] or [uu for n,uu in ms]
    udid=os.environ.get('SIM_UDID') or (pref[0] if pref else None)
    if not udid: print('  没有已启动的模拟器：xcrun simctl boot "iPhone 18 Pro Max"'); return None
    f=os.path.join(OUT,f'kitaudit_{k}_ios.json')
    if os.path.exists(f): os.remove(f)
    subprocess.run(['xcrun','simctl','openurl',udid,BASE+u+'?kitaudit=1&quiet=1&t='+str(int(time.time()))],capture_output=True)
    t0=time.time()
    while not os.path.exists(f) and time.time()-t0<60: time.sleep(0.5)
    return json.load(open(f)) if os.path.exists(f) else None

def report(k,plat,d):
    if not d: print(f'✗ {k} {plat}: 没收到对账结果（页面没加载完或 kitaudit.js 没跑）'); return 1
    s=d['summary']; bad=s['off']+s['unknown']
    print(f"{'✓' if not bad else '✗'} {k} {plat} {d['w']}×{d['h']}  ✅{s['ok']} ⚠{s['off']} ✗{s['unknown']}  内容{s.get('content',0)}（共 {s['total']} 个）")
    # 同一种问题合并（岗位行几十条一样的），给个数和前 3 个例子
    groups={}
    for x in d['items']:
        if x['status'] not in ('off','unknown'): continue
        key=(x['status'],x['kit'],re.sub(r'[\d.]+','N','；'.join(x['probs'])))
        groups.setdefault(key,[]).append(x)
    for (st,kit,_),xs in groups.items():
        ex=xs[0]; more=f'  …共 {len(xs)} 个' if len(xs)>1 else ''
        print(f"     {'⚠' if st=='off' else '✗'} {ex['el']}  [{ex['got']}]  → {kit}：{'；'.join(ex['probs'])}{more}")
        for y in xs[1:3]: print(f"         同：{y['el']}  [{y['got']}]")
    if '--all' in flags:
        for x in d['items']:
            if x['status'] in ('ok','content'): print(f"     {'✅' if x['status']=='ok' else '内容'} {x['el']}  [{x['got']}]  → {x['kit']}")
    return bad

total=0
for k,u in pages.items():
    if do_mac:
        d=run_mac(BASE+u+'?kitaudit=1&quiet=1&t='+str(int(time.time())))
        if d: open(os.path.join(OUT,f'kitaudit_{k}_mac.json'),'w').write(json.dumps(d,ensure_ascii=False,indent=1))
        total+=report(k,'Mac 1440',d)
    if do_phone:
        total+=report(k,'iPhone',run_phone(k,u))
print('KIT-OK' if not total else f'共 {total} 个控件没按 Kit'); sys.exit(1 if total else 0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
往 iOS 模拟器主屏幕装五个「网页 App」图标（= Safari「添加到主屏幕」+「作为网页 App 打开」），
供 pipeline/ui/accept.py --webapp 用：视口 894（状态栏之下），没有 Safari 地址栏。
simctl 没有这个命令，但 .webclip 只是一个目录（Info.plist + icon.png + Storage/ + Cookies/），直接写进
  ~/Library/Developer/CoreSimulator/Devices/<UDID>/data/Library/WebClips/<UUID>.webclip
然后重启 SpringBoard 就出现在主屏幕（第二页）。重复运行会先删掉旧的（按 URL 认）。
  python3 pipeline/ui/webclips.py            # 用已启动的模拟器
"""
import os, re, sys, uuid, shutil, plistlib, subprocess, json
from PIL import Image
HERE=os.path.dirname(os.path.abspath(__file__)); REPO=os.path.abspath(os.path.join(HERE,'..','..'))
BASE=os.environ.get('ACCEPT_BASE','http://127.0.0.1:8788')
r=subprocess.run(['xcrun','simctl','list','devices','booted'],capture_output=True,text=True).stdout
m=re.search(r'\(([0-9A-F-]{36})\) \(Booted\)',r); UDID=os.environ.get('SIM_UDID') or (m.group(1) if m else None)
if not UDID: sys.exit('没有已启动的模拟器')
WC=os.path.expanduser(f'~/Library/Developer/CoreSimulator/Devices/{UDID}/data/Library/WebClips'); os.makedirs(WC,exist_ok=True)
# 五个各自独立：网页 App 里跨页跳转（location.href）后 WebKit 的视口会变成 894 顶对齐、底下留 62 空白（容器 bug），所以不用 chain，逐个点。
pages=[('首页','/index.html','#0088ff','map.fill',''),('薪资','/cost/index.html','#34c759','yensign',''),
       ('大阪','/osaka/index.html','#30b0c7','tram.fill',''),('学習','/japan/index.html','#5856d6','graduationcap.fill',''),('クイズ','/quiz/index.html','#ff9500','questionmark.circle','')]
for d in os.listdir(WC):
    pp=os.path.join(WC,d,'Info.plist')
    if d.endswith('.webclip') and os.path.exists(pp) and BASE in plistlib.load(open(pp,'rb')).get('URL',''): shutil.rmtree(os.path.join(WC,d))
ids={}
for title,path,color,sym,extra in pages:
    uid=uuid.uuid4().hex.upper(); d=os.path.join(WC,uid+'.webclip'); os.makedirs(os.path.join(d,'Storage')); os.makedirs(os.path.join(d,'Cookies'))
    info={'ApplicationBundleVersion':1,'ClassicMode':False,'ConfigurationIsManaged':False,'ContentMode':'UIWebClipContentModeRecommended','Eligibility':0,
          'FullScreen':True,'IconIsPrecomposed':True,'IconIsScreenShotBased':False,'IgnoreManifestScope':False,'IsAppClip':False,'Orientations':0,
          'PlaceholderBundleIdentifier':'com.apple.WebKit.PushBundle.'+uid,'ScenelessBackgroundLaunch':False,'Title':title,
          'TrustedClientBundleIdentifiers':['com.apple.mobilesafari'],'URL':f'{BASE}{path}?accept=1&quiet=1{extra}',
          'WebClipStatusBarStyle':'UIWebClipStatusBarStyleDefault'}   # = <meta apple-mobile-web-app-status-bar-style=default>（black-translucent 在 iOS 27 网页 App 里触摸偏 62，见 hig.css）
    plistlib.dump(info,open(os.path.join(d,'Info.plist'),'wb'),fmt=plistlib.FMT_BINARY)
    im=Image.new('RGBA',(180,180),color); sf=os.path.join(REPO,'ui','sf',sym+'.png')
    if os.path.exists(sf):
        a=Image.open(sf).convert('RGBA').split()[3]; s=100; a=a.resize((s,int(s*a.height/a.width))); w=Image.new('RGBA',a.size,'white'); w.putalpha(a); im.alpha_composite(w,((180-a.width)//2,(180-a.height)//2))
    im.convert('RGB').save(os.path.join(d,'icon.png')); ids[title]=uid; print('装了',title,info['URL'])
os.makedirs(os.path.join(REPO,'.accept'),exist_ok=True); json.dump(ids,open(os.path.join(REPO,'.accept','webclips.json'),'w'),ensure_ascii=False)
subprocess.run(['xcrun','simctl','spawn',UDID,'launchctl','kickstart','-k','system/com.apple.SpringBoard'],capture_output=True)
print('SpringBoard 已重启，图标在主屏幕第二页')

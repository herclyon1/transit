#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SUUMO 家賃相場：按站名取该站相場页的 1K 值（默认条件 = 新築・駅徒歩 1〜5 分，与大阪档同口径；SUUMO 每季更新）。
   python3 pipeline/cost/suumo_soba.py tokyo 新宿 渋谷 池袋 東京 荻窪 赤羽 …   → 打印 站名 ek 码 1K 万円 更新日；--json 输出 JSON
   站名 → ek 码从沿线相場页（/chintai/soba/<pref>/en_<line>/）里找，LINES 列出要扫的线；请求间隔 2 秒。"""
import re, sys, json, time, html, subprocess, os
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
LINES={'osaka':['en_chikatetsumidosujisen','en_chikatetsutanimachisen','en_chikatetsuyotsubashisen','en_chikatetsusennichimaesen','en_chikatetsuchuosen','en_chikatetsusakaisujisen','en_chikatetsuimazatosujisen','en_kitaosakakyuko'],'tokyo':['en_chuosen','en_yamanotesen','en_keihintohokusen','en_saikyosen','en_jobansen','en_tozaisen','en_chiyodasen','en_odakyusen','en_keiosen','en_seibuikebukurosen','en_tobutojosen','en_sobusen','en_keihinkyukosen','en_tokyutoyokosen','en_hanzomonsen','en_oedosen','en_keiseihonsen','en_odakyuodawarasen','en_keiokeiosen','en_tokyudenentoshisen']}
def get(url):
    r=subprocess.run(['curl','-sL','-m','40','-A',UA,url],capture_output=True,text=True); time.sleep(2); return r.stdout
def text(h):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',h,flags=re.S); t=html.unescape(re.sub(r'<[^>]+>','|',t)); return re.sub(r'[\s|]+','|',t)
def codes(pref):
    m={}
    for ln in LINES[pref]:
        h=get(f'https://suumo.jp/chintai/soba/{pref}/{ln}/')
        for a in re.finditer(r'<a href="/chintai/soba/'+pref+r'/(ek_\d+)/\?ts=1">([^<]+)',h):
            m.setdefault(a.group(2).strip(),a.group(1))
    return m
def station(pref,ek):
    t=text(get(f'https://suumo.jp/chintai/soba/{pref}/{ek}/'))
    v=re.search(r'\|1K\|([\d.]+)\|万円',t); r=re.search(r'\|ワンルーム\|([\d.]+)\|万円',t); u=re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)更新',t)
    cond=re.search(r'(新築かつ駅から徒歩[^、。]*以内)',t)
    return {'ek':ek,'1k':float(v.group(1)) if v else None,'1r':float(r.group(1)) if r else None,'updated':u.group(1) if u else None,'cond':cond.group(1) if cond else None,'url':f'https://suumo.jp/chintai/soba/{pref}/{ek}/'}
if __name__=='__main__':
    pref=sys.argv[1]; names=[a for a in sys.argv[2:] if not a.startswith('--')]
    m=codes(pref); out={}
    for n in names:
        ek=m.get(n) or m.get(n.replace('ケ','ヶ'))
        out[n]=station(pref,ek) if ek else {'ek':None}
        print(n,out[n])
    if '--json' in sys.argv: json.dump(out,open(f'/tmp/suumo_{pref}.json','w'),ensure_ascii=False,indent=1)

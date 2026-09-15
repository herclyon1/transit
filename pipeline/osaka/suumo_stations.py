#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reach.json 的 842 站 ↔ SUUMO 関西版 站代码（ek）对表 → osaka/data/suumo_ek.json。只对表，不抓房租。
   python3 pipeline/osaka/suumo_stations.py [--refetch]

SUUMO 的租房检索 URL（cost/data/cities/osaka.json 里已有 4 例）长这样：
   https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ra=027&rn=2020&ek=202025390&…
   ek = rn（4 位路線代码）+ 5 位站代码；同一物理站在每条线上各有一个 ek。
站代码来源：SUUMO 各府县「沿線から探す」页 https://suumo.jp/chintai/<pref>/ensen/ 列出路線 slug，
路線页 https://suumo.jp/chintai/<pref>/en_<slug>/ 底部「○○線から賃貸を探す」块里每站一个链接
   <a href="/chintai/<pref>/ek_<5位>/?rn=<4位>">駅名</a>
六府县（大阪・兵庫・京都・奈良・滋賀・和歌山）都抓，因为 reach.json 里有 358 站在大阪府外。HTML 缓存进 osaka/data/raw/suumo/html/（不进仓库），解析结果 raw/suumo/lines.json 进仓库。
对表：站名 NFKC 归一（去「駅」、空白）后相同 → 候选；再看候选所在路線的运营者和 reach 的 ops 有没有交集，有交集的记 op_match=true。一个都对不上的进 unmatched。"""
import json, os, re, sys, time, unicodedata, urllib.request, datetime
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.join(HERE,'..','..')
D=os.path.join(ROOT,'osaka','data'); RAW=os.path.join(D,'raw','suumo'); HTML=os.path.join(RAW,'html')
PREFS=['osaka','hyogo','kyoto','nara','shiga','wakayama']
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
# 路線名关键字 → reach.json 的 ops 名
OPS=[('ＪＲ','西日本旅客鉄道'),('JR','西日本旅客鉄道'),('東海道新幹線','東海旅客鉄道'),('阪急','阪急電鉄'),('阪神','阪神電気鉄道'),('京阪','京阪電気鉄道'),('近鉄','近畿日本鉄道'),('南海','南海電気鉄道'),('泉北','南海電気鉄道'),
     ('阪堺','阪堺電気軌道'),('大阪モノレール','大阪モノレール'),('彩都線','大阪モノレール'),('北大阪急行','北大阪急行電鉄'),('能勢電鉄','能勢電鉄'),('水間','水間鉄道'),
     ('北大阪急行','大阪市高速電気軌道'),('ＯｓａｋａＭｅｔｒｏ','大阪市高速電気軌道'),('Osaka Metro','大阪市高速電気軌道'),('長堀鶴見緑地線','大阪市高速電気軌道'),('南港ポートタウン線','大阪市高速電気軌道'),('ニュートラム','大阪市高速電気軌道'),
     ('ポートアイランド線','神戸新交通'),('六甲アイランド線','神戸新交通'),('わかやま電鉄','和歌山電鐵'),
     ('神戸電鉄','神戸電鉄'),('山陽','山陽電気鉄道'),('神戸市営','神戸市交通局'),('北神線','神戸市交通局'),('神戸新交通','神戸新交通'),('ポートライナー','神戸新交通'),('六甲ライナー','神戸新交通'),('北神','神戸市交通局'),
     ('京都市営','京都市交通局'),('京福','京福電気鉄道'),('嵐電','京福電気鉄道'),('叡山','叡山電鉄'),('近江','近江鉄道'),('信楽','信楽高原鐵道'),('紀州鉄道','紀州鉄道'),('和歌山電鐵','和歌山電鐵'),('神戸高速','神戸高速鉄道'),('神戸高速','阪急電鉄'),('神戸高速','阪神電気鉄道'),('神戸高速','山陽電気鉄道'),('北条','北条鉄道'),('智頭','智頭急行'),('京都丹後','WILLER TRAINS')]
ALIAS={'柴原':'柴原阪大前',   # 大阪モノレール 2019 改名，reach.json 还是旧名
       '近鉄京都':'京都',       # SUUMO 近鉄京都線上就叫「京都」
       '鴬の森':'鶯の森'}       # 异体字
NOT_STATION=re.compile(r'(号線|番のりば|番線|改札口)$')  # reach.json 里混进来的站台/出口节点，不是站
def norm(s):
    s=unicodedata.normalize('NFKC',s or '').strip()
    s=re.sub(r'[\s　]','',s).replace('ヶ','ケ').replace('ヵ','カ')
    s=re.sub(r'(駅|停留場|停留所)$','',s)
    s=re.sub(r'[（(].*?[)）]$','',s)   # SUUMO 偶有「○○(△△)」
    return s
def get(url,name,refetch=False):
    os.makedirs(HTML,exist_ok=True); p=os.path.join(HTML,name)
    if os.path.exists(p) and not refetch: return open(p,encoding='utf-8',errors='replace').read()
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept-Language':'ja'})
    s=urllib.request.urlopen(req,timeout=60).read().decode('utf-8','replace'); open(p,'w',encoding='utf-8').write(s); time.sleep(0.7); return s
def fetch_lines(refetch):
    lines=[]
    for pref in PREFS:
        idx=get(f'https://suumo.jp/chintai/{pref}/ensen/',f'ensen_{pref}.html',refetch)
        slugs=sorted(set(re.findall(rf'href="/chintai/{pref}/en_([A-Za-z0-9]+)/"',idx)))
        print(pref,len(slugs),'路線')
        for slug in slugs:
            s=get(f'https://suumo.jp/chintai/{pref}/en_{slug}/',f'en_{pref}_{slug}.html',refetch)
            t=re.search(r'<title>【SUUMO】(.*?)の賃貸',s); title=t.group(1) if t else slug
            sts=re.findall(rf'<a href="/chintai/{pref}/ek_(\d+)/\?rn=(\d+)">([^<]*)</a>',s)
            if not sts: print('  ',slug,'没解析出站'); continue
            rn=sts[0][1]; ops=[o for k,o in OPS if k in title]
            if '地下鉄' in title: ops.append({'osaka':'大阪市高速電気軌道','hyogo':'神戸市交通局','kyoto':'京都市交通局'}.get(pref,'?'))  # SUUMO 只写「地下鉄○○線」，按府县定运营者
            lines.append({'pref':pref,'slug':slug,'name':title,'rn':rn,'ops':sorted(set(ops)),'url':f'https://suumo.jp/chintai/{pref}/en_{slug}/','stations':[{'ek':ek,'name':nm} for ek,r,nm in sts]})
    return lines
def main():
    refetch='--refetch' in sys.argv
    lines=fetch_lines(refetch)
    os.makedirs(RAW,exist_ok=True)
    json.dump({'fetched_at':datetime.date.today().isoformat(),'source':'https://suumo.jp/chintai/<pref>/ensen/ → /en_<slug>/ 底部站链接 /chintai/<pref>/ek_<ek>/?rn=<rn>','lines':lines},open(os.path.join(RAW,'lines.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    byname={}
    for L in lines:
        for st in L['stations']:
            byname.setdefault(norm(st['name']),[]).append({'rn':L['rn'],'ek':L['rn']+st['ek'],'ek5':st['ek'],'line':L['name'],'pref':L['pref'],'ops':L['ops'],'suumo_name':st['name']})
    reach=json.load(open(os.path.join(D,'reach.json'),encoding='utf-8'))
    out=[]; un=[]
    for s in reach['stations']:
        cands=byname.get(norm(ALIAS.get(s['name'],s['name'])),[])
        rows=[]
        for c in cands:
            m=bool(set(c['ops'])&set(s['ops']))
            ra={'osaka':'027','hyogo':'028','kyoto':'026','nara':'029','shiga':'025','wakayama':'030'}[c['pref']]  # ra = 都道府県代码（JIS X 0401）
            rows.append({**c,'op_match':m,'url':f"https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ra={ra}&rn={c['rn']}&ek={c['ek']}&md=01&md=02&cn=9999999&po1=12&pc=50"})
        rows.sort(key=lambda r:(not r['op_match'],r['line']))
        rec={'station_id':s['station_id'],'name':s['name'],'grp':s['grp'],'ops':s['ops'],'in_osaka':s['in_osaka'],'suumo':rows}
        if not rows: un.append({'station_id':s['station_id'],'name':s['name'],'grp':s['grp'],'ops':s['ops'],'in_osaka':s['in_osaka'],'why':'不是站（站台/出口节点）' if NOT_STATION.search(s['name']) else 'SUUMO 沿線页没列这站（多半是没房源：机场/山区/新站）'})
        elif not any(r['op_match'] for r in rows): rec['warn']='同名但运营者对不上'
        out.append(rec)
    n_ok=sum(1 for r in out if r['suumo'] and any(x['op_match'] for x in r['suumo'])); n_warn=sum(1 for r in out if r.get('warn'))
    res={'meta':{'generated':datetime.date.today().isoformat(),'source':'SUUMO 関西版 沿線・駅ページ：https://suumo.jp/chintai/{osaka,hyogo,kyoto,nara,shiga,wakayama}/ensen/ 及各 /en_<slug>/（解析结果 osaka/data/raw/suumo/lines.json）',
        'ek_rule':'检索 URL 的 ek = rn(4 位路線代码) + 5 位站代码；同一物理站每条线一个 ek；url 字段是该站 1R/1K（md=01,02）不限价的检索页',
        'n_reach':len(out),'n_matched_op':n_ok,'n_name_only':n_warn,'n_unmatched':len(un),'n_lines':len(lines),'n_suumo_stations':sum(len(L['stations']) for L in lines),
        'how':__doc__},'stations':out,'unmatched':un}
    json.dump(res,open(os.path.join(D,'suumo_ek.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print(f'reach {len(out)} 站：运营者也对上 {n_ok}，只同名 {n_warn}，对不上 {len(un)}；SUUMO {len(lines)} 路線 {res["meta"]["n_suumo_stations"]} 站')
    if un: print('对不上：',', '.join(f"{u['name']}({u['grp'] or '/'.join(o[:2] for o in u['ops'])})" for u in un))
    if n_warn: print('只同名：',', '.join(r['name'] for r in out if r.get('warn')))
if __name__=='__main__': main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按站房租：SUUMO 在挂 ワンルーム/1K 房源的 賃料（不含管理費）中位数 → osaka/data/station_rent.json（增量，按 ek 键）。
   python3 pipeline/osaka/suumo_station_rent.py 天神橋筋六丁目 千林大宮 大日 なかもず     # 站名 / station_id（S0563）/ 9 位 ek 都行
   python3 pipeline/osaka/suumo_station_rent.py --all                                   # 全部 825 站（约 1–2 小时、几千次请求）——先问用户
   python3 pipeline/osaka/suumo_station_rent.py --all --only-osaka                     # 只跑府内 486 站

站 → ek 的对表来自 osaka/data/suumo_ek.json（suumo_stations.py）。同一物理站在每条线上各有一个 ek，检索 URL 里全部带上（ek= 可重复），
SUUMO 按建物去重后给一份列表，这样 梅田/京橋 这种多线站不会重复算。
检索条件 = cost/data/cities/osaka.json tiers 里那 4 条 URL 的参数：md=01,02（ワンルーム/1K）mb=20（専有 20 ㎡以上）et=10（駅徒歩 10 分以内）
cn=9999999（築年不限）po1=12（賃料+管理費が安い順）pc=50（每页 50 栋）。翻完全部页，賃料 取中位数、下四分位（Q1，和 tiers 现值同口径）、最低、n。
礼貌：UA、每次请求间隔 ≥2 s、失败重试 2 次（退避 5/10 s）。解析用 pipeline/cost/suumo_list.py 的 parse_rows。"""
import json, os, re, sys, time, datetime, statistics, subprocess
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.join(HERE,'..','..')
sys.path.insert(0,os.path.join(ROOT,'pipeline','cost'))
from suumo_list import parse_rows, UA   # 行解析和 UA 复用，口径一致
D=os.path.join(ROOT,'osaka','data'); EK=os.path.join(D,'suumo_ek.json'); OUT=os.path.join(D,'station_rent.json')
RA={'osaka':'027','hyogo':'028','kyoto':'026','nara':'029','shiga':'025','wakayama':'030'}
PARAMS='md=01&md=02&mb=20&et=10&cn=9999999&po1=12&pc=50'
COND='ワンルーム/1K・専有 20 ㎡以上・駅徒歩 10 分以内・築年不限・賃料+管理費が安い順・SUUMO 按建物去重后的全部页'
INTERVAL=2.0
_last=[0.0]
def get(url,tries=3):
    for k in range(tries):
        wait=INTERVAL-(time.time()-_last[0])
        if wait>0: time.sleep(wait)
        r=subprocess.run(['curl','-sL','-m','40','-A',UA,'-w','\n%{http_code}',url],capture_output=True,text=True); _last[0]=time.time()
        body,_,code=r.stdout.rpartition('\n')
        if code=='200' and '</html>' in body: return body
        print(f'    重试 {k+1}: HTTP {code} {len(body)} B'); time.sleep(5*(k+1))
    return ''
def search_url(rows):
    ra=RA[rows[0]['pref']]; rn=rows[0]['rn']
    return f"https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ra={ra}&rn={rn}&"+'&'.join(f"ek={r['ek']}" for r in rows)+'&'+PARAMS
def fetch_station(st):
    rows=[r for r in st['suumo'] if r['op_match']] or st['suumo']
    u=search_url(rows); print(f"  {st['name']}（{'/'.join(r['line'].split('（')[0] for r in rows)}）")
    h=get(u)
    if not h: return {'station_id':st['station_id'],'name':st['name'],'eks':[r['ek'] for r in rows],'url':u,'error':'第 1 页取不到','fetched_at':datetime.date.today().isoformat()}
    all_rows,total,last=parse_rows(h); pages=1
    while pages<last:
        pages+=1; r2,_,_=parse_rows(get(u+f'&page={pages}'))
        if not r2: print(f'    第 {pages} 页空，停'); break
        all_rows+=r2
    rents=sorted(r['rent'] for r in all_rows)
    rec={'station_id':st['station_id'],'name':st['name'],'in_osaka':st['in_osaka'],'eks':[r['ek'] for r in rows],'lines':[r['line'] for r in rows],'url':u,
         'fetched_at':datetime.date.today().isoformat(),'cond':COND,'total_listed':total,'pages':pages,'n':len(rents),
         'median':int(statistics.median(rents)) if rents else None,'q1':int(rents[len(rents)//4]) if rents else None,'min':int(rents[0]) if rents else None,'max':int(rents[-1]) if rents else None,
         'note':'賃料 不含管理費；median = 賃料中位，q1 = 下四分位（cost/data/cities/osaka.json tiers 用的口径），n = 去重后的房源行数，total_listed = SUUMO 标的含重复挂牌总数'}
    print(f"    n={len(rents)} 页 {pages} 中位 {rec['median']} Q1 {rec['q1']} 最低 {rec['min']}")
    return rec
def main():
    args=[a for a in sys.argv[1:] if not a.startswith('--')]
    ek=json.load(open(EK,encoding='utf-8')); sts=[s for s in ek['stations'] if s['suumo']]
    if '--all' in sys.argv:
        if '--only-osaka' in sys.argv: sts=[s for s in sts if s['in_osaka']]
        print(f'全部 {len(sts)} 站，约 {len(sts)*4*INTERVAL/60:.0f}+ 分钟。'); todo=sts
    else:
        todo=[]
        for a in args:
            hit=[s for s in sts if s['name']==a or s['station_id']==a or any(r['ek']==a for r in s['suumo'])]
            if not hit: print('找不到站：',a); continue
            todo+=hit
        if not todo: print(__doc__); return
    out=json.load(open(OUT,encoding='utf-8')) if os.path.exists(OUT) else {'meta':{},'stations':{}}
    out['meta']={'source':'SUUMO 関西版 賃貸物件一覧 FR301FC001（按站检索，参数见 cond），站码来自 osaka/data/suumo_ek.json','cond':COND,'params':PARAMS,'updated':datetime.date.today().isoformat(),'how':__doc__}
    for st in todo:
        rec=fetch_station(st); out['stations'][rec['eks'][0]]=rec
        json.dump(out,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=1)   # 每站落盘一次，中断不丢
    print('→',OUT,len(out['stations']),'站')
if __name__=='__main__': main()

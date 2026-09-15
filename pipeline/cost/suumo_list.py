#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SUUMO 在挂房源（普通人真会租到的那档）：按站搜 ワンルーム/1K、専有 ≥20 ㎡、駅徒歩 ≤10 分、築年不限，「賃料+管理費が安い順」翻页到总数的 25%，
   取下四分位（Q1）当主值，同时记 n（总数）、最低、Q1、中位（若翻到）、检索条件；相場页的值只作对照（用户 2026-09-15：相場被新建房源拉高，不能当主值）。
   python3 pipeline/cost/suumo_list.py osaka ek_21550 [ek_…]      # ek 码 = 相場页/物件一覧页共用的站码
   输出 JSON 到 cost/data/raw/<city>/<date>/suumo_list.json（每站前 25% 的行明细也留着）。请求间隔 2 秒。"""
import re, sys, json, time, html, subprocess, os, datetime, statistics
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
PREF={'osaka':('027','2020','osaka'),'tokyo':('013','1000','tokyo')}   # ra, rn(沿線コード占位, 物件一覧页不看它), soba 路径
def get(url):
    r=subprocess.run(['curl','-sL','-m','40','-A',UA,url],capture_output=True,text=True); time.sleep(2); return r.stdout
def text(h):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',h,flags=re.S); t=html.unescape(re.sub(r'<[^>]+>','|',t)); return re.sub(r'[\s|]+','|',t)
def list_url(city,ek):
    """从相場页拿「全物件一覧」链接（带 ar/bs/ra/rn/ek），再加筛选参数"""
    h=get(f'https://suumo.jp/chintai/{PREF[city][2]}/{ek}/')      # 站的物件一覧页里有带 ar/bs/ra/rn/ek 的检索链接
    m=re.search(r'href="(/jj/chintai/ichiran/FR301FC001/\?[^"]*ek=\d+[^"]*)"',h)
    base=html.unescape(m.group(1)).split('&po1')[0] if m else None
    name=(re.search(r'<title>【SUUMO】([^駅]+)駅',h) or [None,ek])[1]
    return name, (f'https://suumo.jp{base}&md=01&md=02&mb=20&et=10&cn=9999999&po1=12&pc=50' if base else None)
def parse_rows(h):
    t=text(h); rows=[]
    for m in re.finditer(r'\|(\d+)階\|([\d.]+)万円\|([^|]*)\|([^|]*)\|([^|]*)\|(ワンルーム|1K|1DK)\|([\d.]+)m\|2\|',t):
        rows.append({'floor':m.group(1),'rent':float(m.group(2))*10000,'kanri':m.group(3),'shikikin':m.group(4),'reikin':m.group(5),'type':m.group(6),'m2':float(m.group(7))})
    tot=re.search(r'\|(\d[\d,]*)\|件\|不動産会社が掲載',t)
    last=max([int(x) for x in re.findall(r'page=(\d+)',h)] or [1])       # 分页器里最大页码 = 去重后的建物页数（50 栋/页）
    return rows, (int(tot.group(1).replace(',','')) if tot else None), last
def station(city,ek):
    """安い順翻页：页数 ≤ 12 全取（精确 Q1/中位）；更多只取到 25% 深度 + 1 页，Q1 按「取到的行数 / 已取页 × 总页」估总行数"""
    name,u=list_url(city,ek)
    if not u: return {'ek':ek,'name':name,'error':'no list url'}
    rows,total,last=parse_rows(get(u)); pages=1
    want=last if last<=12 else max(2,int(last*0.25)+2)
    while pages<want:
        pages+=1; r2,_,_=parse_rows(get(u+f'&page={pages}'))
        if not r2: break
        rows+=r2
    rents=sorted(r['rent'] for r in rows)
    est_rows=len(rents) if pages>=last else round(len(rents)/pages*last)
    q1=rents[min(len(rents)-1,int(est_rows*0.25))] if rents else None
    med=statistics.median(rents) if (rents and pages>=last) else None
    return {'ek':ek,'name':name,'url':u,'total_listed':total,'pages_total':last,'pages_fetched':pages,'rows_fetched':len(rows),'rows_est':est_rows,'min':rents[0] if rents else None,'q1':q1,'median':med,
            'cond':'ワンルーム/1K・専有 20 ㎡以上・駅徒歩 10 分以内・築年不限・賃料+管理費が安い順（SUUMO 去重后的房源列表；total_listed 是含重复的挂牌总数）','rows':rows[:int(est_rows*0.25)+5]}
if __name__=='__main__':
    city=sys.argv[1]; eks=sys.argv[2:]; today=datetime.date.today().strftime('%Y%m%d')
    out={ek:station(city,ek) for ek in eks}
    for ek,o in out.items(): print(o.get('name'),ek,'页',o.get('pages_fetched'),'/',o.get('pages_total'),'行',o.get('rows_fetched'),'估总',o.get('rows_est'),'最低',o.get('min'),'Q1',o.get('q1'),'中位',o.get('median'))
    d=os.path.join(os.path.dirname(__file__),'..','..','cost','data','raw',city,today); os.makedirs(d,exist_ok=True)
    p=os.path.join(d,'suumo_list.json'); old=json.load(open(p)) if os.path.exists(p) else {}; old.update(out); json.dump(old,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1); print('→',p)

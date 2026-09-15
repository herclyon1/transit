#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贝壳/安居客 jsonl → 四档房租（beike.jsonl + anjuke.jsonl 都读）（用户 2026-09-15：房租要「普通人真会租到的价」= 过滤后便宜的四分之一处，不是中位/相場）。
   python3 pipeline/cost/rent_from_beike.py urumqi [--date 20260915]
   读 cost/data/raw/<city>/<date>/beike.jsonl：按 keyword（站名）分组 → 去重（name,spec,distance,price）→ 去掉商用楼/写字间、面积 <15 或 >80 ㎡、价 ≥6000
   → 整租条目写 tiers[].rent_1k（Q1；items = 便宜段明细；compare = 同样本中位），合租条目写 tiers[].rent_share。sort 字段照抄进 how。
   站名 → 档位映射在 STATIONS 里；三工档取距站 ≤2 km。"""
import json, re, sys, os, glob, statistics, datetime
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
STATIONS={'urumqi':{'walk':(['南门'],None,'南门站'),'t15':(['王家梁'],None,'王家梁站'),'t25':(['铁路局'],None,'铁路局站'),'t40':(['三工','三工+宣仁墩+大地窝堡','三工+宣仁墩+大地窝堡·续'],2000,'三工＋宣仁墩＋大地窝堡 三站（2 km 圈）')}}
BAD=re.compile(r'大厦|广场|写字|寰球港|商务|loft|LOFT')
def area(s):
    m=re.search(r'(\d+(?:\.\d+)?)㎡',s or ''); return float(m.group(1)) if m else None
def dist(s):
    m=re.search(r'(\d+(?:\.\d+)?)(km|m)\b',s or ''); return (float(m.group(1))*(1000 if m.group(2)=='km' else 1)) if m else None
def main():
    city=sys.argv[1]; date=(sys.argv[sys.argv.index('--date')+1] if '--date' in sys.argv else sorted(x for x in os.listdir(os.path.join(ROOT,'raw',city)) if x.isdigit())[-1])   # 只认日期目录（README.md 排最后会被当日期）
    rows=[]
    for fn in ('beike.jsonl','anjuke.jsonl'):            # 贝壳没房源时用安居客 App（只有默认排序）；两家都读，platform 字段区分
        fp=os.path.join(ROOT,'raw',city,date,fn)
        if os.path.exists(fp): rows+=[json.loads(l) for l in open(fp,encoding='utf-8')]
    if not rows: sys.exit(f'{city}/{date} 没有 beike.jsonl / anjuke.jsonl')
    for r in rows: r.setdefault('type','合租' if r['name'].startswith('合租') else '整租'); r.setdefault('platform','贝壳')
    cf=os.path.join(ROOT,'cities',f'{city}.json'); d=json.load(open(cf,encoding='utf-8'))
    for t in d['tiers']:
        kws,ring,label=STATIONS[city][t['id']]
        for typ,key,what in (('整租','rent_1k','整租一居'),('合租','rent_share','合租单间')):
            rs=[r for r in rows if r['keyword'] in kws and r.get('price') and r['type']==typ]
            if not rs: continue
            seen=set(); ok=[]
            for r in rs:
                k=(r['name'],r['spec'],r['distance'],r['price'])
                if k in seen: continue
                seen.add(k)
                # 商用楼只看小区名：贝壳标题「整租1居·小区」的小区段、安居客规格「3室·主卧·20㎡·小区·路」的小区段；合租标题里「乌鲁木齐大厦附近」这种地标不算（09-16 安居客实跑 11 条被误删 5 条）
                estate = (r['name'].split('·',1)[1] if r['name'].startswith(('整租','合租')) and '·' in r['name'] and '|' not in r['name'] else '') or ''.join((r.get('spec') or '').split('·')[3:4])
                if BAD.search(estate): continue
                if typ=='整租' and ((area(r['spec']) or 0)<15 or (area(r['spec']) or 99)>80): continue
                if r['price']>=6000 or (ring and (dist(r['distance']) or 9999)>ring): continue
                ok.append(r)
            if len(ok)<4: print(t['id'],typ,'样本太少',len(ok)); continue
            ok.sort(key=lambda r:r['price']); ps=[r['price'] for r in ok]; q1=ps[int(len(ps)*0.25)]; med=statistics.median(ps)
            sorts=sorted(set(r.get('sort','默认') for r in rs)); plats=sorted(set(r.get('platform','贝壳') for r in ok)); src=' / '.join(plats)
            url={'贝壳':'https://m.ke.com/wlmq/zufang/','安居客':'https://wlmq.zu.anjuke.com/'}.get(plats[0],'https://m.ke.com/wlmq/zufang/')
            t[key]={"value":int(q1),"unit":"元/月","source_url":url,"source_name":f"{src} App {what}列表 地铁 1 号线{label}","source_short":f"{src} App","fetched_at":max(r['fetched_at'] for r in rs),"confidence":"listing","n":len(ok),
              "how":f"{src} App {what}、地铁 1 号线{label}，列表按「{'、'.join(sorts)}」抓到 {len(rs)} 条，去重、去掉商用楼/写字间"+("、面积异常" if typ=='整租' else '')+f"后 {len(ok)} 条，取便宜的四分之一处 = {int(q1):,} 元（最低 {int(ps[0]):,}、中位 {int(med):,}、最高 {int(ps[-1]):,}）——刚来打工/上学的人真会租到的那档。",
              "items":[{'name':re.sub(r'^(整租|合租)(\d居)?[·\s]','',r['name']),'price':r['price'],'unit':'元/月','note':' · '.join(x for x in ((r.get('spec') or '').replace('｜',' · '),(r.get('distance') or '').replace('距离','距')) if x)} for r in ok],
              "items_label":f"看 {len(ok)} 套","compare":{"label":"同样本中位数对照","value":int(med),"unit":"元/月","n":len(ok),"source_name":f"{src} App 同一列表"}}
            print(t['id'],typ,'n',len(ok),'Q1',int(q1),'中位',int(med),'排序',sorts)
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
if __name__=='__main__': main()

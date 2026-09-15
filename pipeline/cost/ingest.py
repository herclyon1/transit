#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把各来源适配器通过判据的 jobs_raw.jsonl 写进城市 JSON（PLAN-v2 §一「入库」）。
  python3 pipeline/cost/ingest.py urumqi
- 读 cost/data/raw/<city>/*/jobs_raw.jsonl（所有日期），按 (雇主/地点, 篮子, 工资) 去重，同一岗位留最新发帖；
- 每个篮子取时薪最低的 5 条（「普通人去应聘拿到的价」），写进 cities/<city>.json 的 jobs[]，条目带 ingest_key；
- 手写的条目（没有 ingest_key）原样保留；重跑先删旧的 ingest 条目再写；
- 24 小时岗（hours_flag 含 24h岗）时薪按 24×班数算，note 里注明，并另给 12 小时在岗口径的对照数。
"""
import os, sys, json, glob, datetime, collections
CITY=sys.argv[1] if len(sys.argv)>1 else 'urumqi'
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
BASKET_ZH={'security':'保安','food':'餐饮服务员/后厨','retail':'便利店/超市理货收银','delivery':'外卖/快递/仓储','factory':'工厂普工','cleaning':'保洁/家政','chain':'连锁锚点'}
SRC_ZH={'weixin_sogou':'微信公众号招工帖（搜狗微信搜索）','wlmqkp':'乌鲁木齐快聘网','shiliu':'石榴快聘','hellowork':'ハローワーク','vieclamtot':'Việc Làm Tốt','dvvl_daklak':'Đắk Lắk 就业服务中心'}

rows=[]
for f in sorted(glob.glob(os.path.join(ROOT,'raw',CITY,'*','jobs_raw.jsonl'))):
    for l in open(f,encoding='utf-8'):
        r=json.loads(l)
        if r.get('reasons'): continue
        rows.append(r)
# 去重：雇主(或地点)+篮子+工资 → 最新
best={}
for r in rows:
    key=((r.get('employer') or r.get('location_phrase') or r.get('contact') or '').strip(), r.get('basket'), r.get('wage_value'), r.get('wage_unit'))
    if key not in best or (r.get('posted_at','') > best[key].get('posted_at','')): best[key]=r
uniq=list(best.values())
by=collections.defaultdict(list)
for r in uniq:
    if r.get('hourly'): by[r['basket']].append(r)
picked=[]
for b,lst in by.items():
    lst.sort(key=lambda r:(r['hourly'], r.get('posted_at','')))
    picked+=lst[:5]

def entry(r):
    h=r.get('hours_month'); hpd=r.get('hours_per_day'); dpm=r.get('days_per_month'); flag=r.get('hours_flag','')
    note=f"帖子原文：“{r['raw'][:220].replace(chr(10),' / ')}”"
    if '24h岗' in flag and h: note+=f"。24 小时岗：月工时按 24 h × {dpm} 班 = {h} h 计，含夜间值守；若按 12 小时在岗算则 {round(r['wage_value']/(12*dpm),1)} 元/时。"
    if r.get('via_agent'): note+="。发帖方是中介/劳务，帖子写明了用人单位。"
    if r.get('employer_from_location'): note+="。帖子没写公司名，只写地点和直拨电话（群帖惯例），雇主栏记地点。"
    return {"chain": f"{BASKET_ZH.get(r['basket'],r['basket'])}：{(r.get('title') or '')[:16]}",
            "store": f"{r.get('employer') or '—'}（{SRC_ZH.get(r['source'],r['source'])}，{r.get('account','')}）",
            "basket": r['basket'], "ingest_key": f"{r['source']}|{r.get('source_url','')}|{r.get('wage_value')}",
            "wage": {"value": r['hourly'], "unit": "元/小时", "source_url": r.get('source_url'),
                     "source_name": f"{SRC_ZH.get(r['source'],r['source'])}｜{r.get('account','')}｜{r.get('article_title','')[:30]}",
                     "fetched_at": r.get('fetched_at'), "posted_at": r.get('posted_at'), "confidence": "listing",
                     "contact": r.get('contact'), "note": note,
                     "wage_posted": f"{r['wage_value']:g} {r['wage_unit']}",
                     "hours": {"posted": r.get('hours_text'), "per_day": hpd, "days_per_month": dpm, "monthly": h, "basis": "posted"}}}

cf=os.path.join(ROOT,'cities',f'{CITY}.json'); d=json.load(open(cf,encoding='utf-8'))
manual=[j for j in d.get('jobs',[]) if not j.get('ingest_key')]
new=[entry(r) for r in picked]
d['jobs']=manual+new
d['jobs_ingest']={"updated": datetime.date.today().isoformat(), "raw_rows": len(rows), "unique": len(uniq), "picked": len(new),
                  "rule": "PLAN-v2 §一：确数工资 + 帖子写明工时/班次 + 联系方式 + ≤90 天；每篮子取时薪最低 5 条"}
json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f'{CITY}: raw {len(rows)} → 去重 {len(uniq)} → 入库 {len(new)}（手写保留 {len(manual)}）；篮子：' + '、'.join(f'{BASKET_ZH.get(b,b)} {len(v)}' for b,v in by.items()))

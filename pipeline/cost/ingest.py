#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把各来源适配器通过判据的 jobs_raw.jsonl 写进城市 JSON（PLAN-v2 §一「入库」）。
  python3 pipeline/cost/ingest.py urumqi
- 读 cost/data/raw/<city>/*/jobs_raw.jsonl（所有日期），按 (雇主/地点, 篮子, 工资) 去重，同一岗位留最新发帖；
- 每个篮子取时薪最低的 5 条（「普通人去应聘拿到的价」），写进 cities/<city>.json 的 jobs[]，条目带 ingest_key；
- 手写的条目（没有 ingest_key）原样保留，raw 里和手写条目同一 source_url 的不再重复入库；临时单（temp）不进篮子最低值；重跑先删旧的 ingest 条目再写；
- 「上一休一」没写班长默认 24 h 在岗（basis=default_24h，进有效集）；帖子写明 24 小时的按 24×班数算。
"""
import os, sys, json, glob, datetime, collections, re
PHONE=re.compile(r'(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)')
mask=lambda t:PHONE.sub(lambda m:m.group(1)+'****'+m.group(3),t)   # 公开仓库：帖子原文里的手机号打码
CITY=sys.argv[1] if len(sys.argv)>1 else 'urumqi'
CITY_FILE={'buon_ma_thuot':'buonmathuot'}.get(CITY,CITY)          # raw 目录名 → cities/<file>.json
CUR_ZH={'CNY':'元','VND':'越南盾','JPY':'日元','TWD':'新台币','KRW':'韩元','USD':'美元','EUR':'欧元','AUD':'澳元','MMK':'缅元'}
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
BASKET_ZH={'security':'保安','security_cert':'保安 · 持证/管理岗','food':'餐饮服务员/后厨','retail':'便利店/超市理货收银','delivery':'外卖/快递/仓储','factory':'工厂普工','cleaning':'保洁','home':'家政/钟点（私人家庭）','chain':'连锁锚点'}
SRC_ZH={'weixin_sogou':'微信公众号招工帖（搜狗微信搜索）','wechat_group':'微信群招工帖（群记录导出）','wlmqkp':'乌鲁木齐快聘网','xjhr':'中国新疆人才网','shiliu':'石榴快聘','hellowork':'ハローワーク','vieclamtot':'Việc Làm Tốt','dvvl_daklak':'Đắk Lắk 就业服务中心'}

DISABLED={'urumqi':{'xjhr','wlmqkp'}}   # 用户 2026-09-15：新疆人才网（虚高、不真实）、快聘网（数据前后矛盾）的乌鲁木齐数据不用
rows=[]
for f in sorted(glob.glob(os.path.join(ROOT,'raw',CITY,'*','jobs_raw.jsonl'))):
    for l in open(f,encoding='utf-8'):
        r=json.loads(l)
        if r.get('reasons') or r.get('source') in DISABLED.get(CITY,set()): continue
        rows.append(r)
# 去重：雇主(或地点)+篮子+工资 → 最新
best={}
for r in rows:
    # 同一电话 + 同篮子 + 同工资 = 同一帖（群里转发、公众号两天两发都会重）；没电话再退到雇主/地点
    ph=r.get('contact') if re.search(r'\d{3}|微信',r.get('contact') or '') else None      # 「站内投递」「ハローワーク窓口」不是身份，别把整个来源折成一条
    key=((ph or r.get('employer') or r.get('location_phrase') or r.get('source_url') or '').strip(), r.get('basket'), r.get('wage_value'), r.get('wage_unit'))
    if key not in best or (r.get('posted_at','') > best[key].get('posted_at','')): best[key]=r
uniq=list(best.values())
cf=os.path.join(ROOT,'cities',f'{CITY_FILE}.json'); d=json.load(open(cf,encoding='utf-8')); CUR=CUR_ZH.get(d.get('currency','CNY'),d.get('currency',''))
manual=[j for j in d.get('jobs',[]) if not j.get('ingest_key')]
manual_urls={j['wage'].get('source_url') for j in manual if j['wage'].get('source_url')}   # 群帖没有 URL，别和手写占位条（也没 URL）撞成「重复」
by=collections.defaultdict(list); side=[]; n_dup_manual=0
def tags(r):
    t=[]
    if r.get('temp'): t.append('temp')                               # 临时单/日结：不进篮子最低值、不进首页
    if r.get('suburb'): t.append('suburb')                           # 达坂城等郊区：留列表，不进篮子和首页
    if r.get('basket')=='home': t.append('home')                     # 私人家庭钟点/家政：留列表，不进篮子和首页
    return t
for r in uniq:
    if r.get('source_url') in manual_urls: n_dup_manual+=1; continue      # 手写条目已经是这帖
    if not r.get('hourly'): continue
    r['_tags']=tags(r)
    if set(r['_tags'])&{'temp','suburb','home'}: side.append(r)
    else: by[r['basket']].append(r)
picked=[]
for b,lst in by.items():
    lst.sort(key=lambda r:(r['hourly'], r.get('posted_at','')))
    picked+=lst[:5]
side.sort(key=lambda r:(r['_tags'][0], r['hourly'])); picked+=side[:6]

def entry(r):
    h=r.get('hours_month'); hpd=r.get('hours_per_day'); dpm=r.get('days_per_month'); flag=r.get('hours_flag','')
    note=mask(f"帖子原文：“{r['raw'][:220].replace(chr(10),' / ')}”")
    if '24h岗(默认)' in flag and h: note+=f"。上一休一没写每班几小时：按 24 小时在岗默认（用户 2026-09-15 定），月工时 24 h × {dpm} 班 = {h} h；若按 12 小时在岗算则 {round(r['wage_value']/(12*dpm),1)} {CUR}/时。"
    elif '24h' in flag and h: note+=f"。帖子写明 24 小时在岗：月工时 24 h × {dpm} 班 = {h} h，含夜间值守。"
    if r.get('probation'): note+="。帖子写的是试用期工资。"
    if r.get('wage_floor'): note+=f"。起薪（求人票下限）：求人票写 {r['wage_value']:g}〜{r['wage_hi']:g}，按经验/班次给幅度，下限是新人该班次的保底价（用户 2026-09-15 裁定，只对ハローワーク）。"
    if r.get('via_agent'): note+="。发帖方是中介/劳务，帖子写明了用人单位。"
    if r.get('employer_from_location'): note+="。帖子没写公司名，只写地点和直拨电话（群帖惯例）。"
    return {"chain": f"{BASKET_ZH.get(r['basket'],r['basket'])}：{(r.get('title') or '')[:16]}", "tags": r.get('_tags',[]), "headline": not r.get('_tags'),   # headline=False 的不参与首页中位数
            "store": f"{r.get('employer') or ('地点 '+r['location_phrase'] if r.get('location_phrase') else ('群帖 · '+(r.get('account') or '') if r['source']=='wechat_group' else '—'))}（{SRC_ZH.get(r['source'],r['source'])}，{r.get('account','')}）",
            "basket": r['basket'], "ingest_key": f"{r['source']}|{r.get('source_url') or r.get('article_title','')}|{r.get('wage_value')}",   # 群帖没有 URL，用「截图 文件名」
            "wage": {"value": r['hourly'], "unit": f"{CUR}/小时", "source_url": r.get('source_url'),
                     "source_name": f"{SRC_ZH.get(r['source'],r['source'])}｜{r.get('account','')}｜{r.get('article_title','')[:30]}",
                     "fetched_at": r.get('fetched_at'), "posted_at": r.get('posted_at'), "confidence": "listing",
                     "contact": r.get('contact'), "note": note,
                     "wage_posted": (f"{r['wage_value']:g}〜{r['wage_hi']:g} " if r.get('wage_floor') else f"{r['wage_value']:g} ")+r['wage_unit'].replace('CNY','元').replace('VND','越南盾').replace('JPY','日元')+('（取下限）' if r.get('wage_floor') else ''),
                     "hours": {"posted": r.get('hours_text'), "per_day": hpd, "days_per_month": dpm, "monthly": h,
                               "basis": "default_24h" if '24h岗(默认)' in flag else "posted"}}}   # 上一休一没写班长 → 默认 24h（用户 09-15 18:45）

new=[entry(r) for r in picked]
d['jobs']=manual+new; d['updated']=datetime.date.today().isoformat()
d['jobs_ingest']={"updated": datetime.date.today().isoformat(), "raw_rows": len(rows), "unique": len(uniq), "dup_manual": n_dup_manual, "side": len(side), "picked": len(new),
                  "rule": "PLAN-v2 §一（2026-09-15 maa 定稿）：确数工资 + 帖子写明工时/班次 + 电话/微信/文内二维码 + ≤180 天；每篮子取时薪最低 5 条；临时单/郊区/家政另列不进篮子；首页用 headline 条目的时薪中位数"}
json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f'{CITY}: raw {len(rows)} → 去重 {len(uniq)} → 与手写重复 {n_dup_manual} → 入库 {len(new)}（其中另列 {len(side[:6])}：临时/郊区/家政；手写保留 {len(manual)}）；篮子：' + '、'.join(f'{BASKET_ZH.get(b,b)} {len(v)}' for b,v in by.items()))

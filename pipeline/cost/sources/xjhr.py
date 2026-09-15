#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源：中国新疆人才网 xjhr.com（正规招聘站，九成区间薪资；但公司直发的兼职/日结帖偶尔写确数+班次，2.8% 命中，留着）。
  python3 pipeline/cost/sources/xjhr.py urumqi --from-jsonl cost/data/raw/urumqi/20260915/xjhr.jsonl   # 把昨晚扫的详情行过一遍 PLAN-v2 判据
  python3 pipeline/cost/sources/xjhr.py urumqi --ids 8413081 8274905                                     # 现抓这些详情页
联系方式：站内投递（site_apply）+ 帖子里的电话若有。中介（人力资源/劳务/企业管理咨询/派遣/外包）只在正文写明用人单位时入库。
"""
import re, os, sys, json, html, time, random, argparse, datetime, subprocess
from common import Rec, write_outputs, extract_common
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
CITY_HINT={'urumqi':{'in':['乌鲁木齐','乌市','天山区','沙依巴克区','沙区','新市区','水磨沟区','水区','头屯河区','头区','米东区','达坂城','高新区','经开区','开发区','机场','地铁'],
                     'out':['昌吉','石河子','库尔勒','哈密','吐鲁番','克拉玛依','伊犁','喀什','阿克苏','五家渠','阜康','呼图壁','奇台','和田','博乐','塔城','阿勒泰','乌苏','奎屯','库车','沙湾']}}
AGENT=re.compile(r'人力资源|劳务|企业管理咨询|人才|派遣|外包|商务服务|企业服务')

def text(h):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',h,flags=re.S); t=re.sub(r'<[^>]+>','\n',t); t=html.unescape(t)
    t=re.sub(r'[ \t　]+',' ',t); return re.sub(r'\n\s*\n+','\n',t)

def rel_date(s, today):
    m=re.search(r'(\d+)\s*(小时|天|分钟)前|(\d+)小时内',s or '')
    if m: return (today-datetime.timedelta(days=int(m.group(1)) if m.group(2)=='天' else 0)).isoformat()
    m=re.search(r'(\d{4}-\d{2}-\d{2})',s or ''); return m.group(1) if m else ''

def fetch(jid):
    url=f'https://www.xjhr.com/zhaopin/job_{jid}.html'
    h=subprocess.run(['curl','-s','-m','25','-A',UA,url],capture_output=True,text=True).stdout; t=text(h)
    title=(re.search(r'<title>(.*?)[_\-|]',h) or [None,''])[1].strip()
    comp=(re.search(r'公司名称[:：]?\s*([^\n]{2,40})',t) or re.search(r'([一-龥（）()]{4,30}(?:公司|集团|医院|学校|酒店|超市|中心))',t) or [None,''])[1].strip()
    upd=(re.search(r'(?:更新|发布)(?:时间|日期)[:：]?\s*([^\n]{2,20})',t) or [None,''])[1]
    body=(re.search(r'职位描述\n(.*?)(?:\n公司简介|\n联系方式|\n工作地址|$)',t,re.S) or [None,''])[1].strip()
    return {'id':jid,'url':url,'title':title,'company':comp,'updated':upd,'body':body,'area':''}

def to_rec(d, city, today):
    raw=f"{d.get('title','')}\n{d.get('company','')}\n{d.get('area','')}\n{d.get('body','')}"
    r=Rec(city=city, source='xjhr', source_url=d['url'], fetched_at=today.isoformat(), posted_at=rel_date(d.get('updated',''),today), raw=raw, account='新疆人才网', article_title=d.get('title',''), site_apply=True)
    extract_common(r, CITY_HINT[city])
    comp=d.get('company') or ''
    if AGENT.search(comp):                                           # 中介：雇主要从正文里找，且不能又是中介名
        r['via_agent']=True; body=raw.replace(comp,'')
        em=re.search(r'([一-龥A-Za-z0-9·]{2,20}(?:公司|集团|酒店|饭店|餐厅|超市|便利店|工厂|厂|医院|学校|幼儿园|物业|商场|广场|仓|驿站|门店|店|院|中心|基地|银行|车站|机场))',body)
        r['employer']=em.group(1) if em and not AGENT.search(em.group(1)) else None; r['employer_from_location']=False
    else: r['employer']=comp or r.get('employer'); r['employer_from_location']=False
    if d.get('area') and '乌鲁木齐' in d['area'] and not any(h in d['area'] for h in CITY_HINT[city]['out']): r['in_city']=True if r['in_city'] is not False or '乌鲁木齐市(' in d['area'] else r['in_city']
    if d.get('title') and not r.get('title'): r['title']=d['title'][:16]
    return r

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--from-jsonl'); ap.add_argument('--ids',nargs='*',default=[]); ap.add_argument('--days',type=int,default=180); a=ap.parse_args()
    city=a.city; today=datetime.date.today(); outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    recs=[]; log=[]
    if a.from_jsonl:
        rows=[json.loads(l) for l in open(a.from_jsonl,encoding='utf-8')]; det=[r for r in rows if r.get('detail_fetched') and (r.get('body') or '').strip()]
        log.append(f'{a.from_jsonl}：{len(rows)} 行，其中取过正文 {len(det)} 行')
        for d in det: recs.append(to_rec(d,city,today))
    for jid in a.ids:
        d=fetch(jid); time.sleep(random.uniform(1,2))
        if d['body']: recs.append(to_rec(d,city,today)); log.append(f'抓 {jid}：{d["title"][:30]}')
        else: log.append(f'抓 {jid}：正文取不到')
    write_outputs(outdir, 'xjhr', recs, log, a.days)

if __name__=='__main__': main()

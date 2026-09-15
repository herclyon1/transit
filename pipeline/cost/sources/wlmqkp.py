#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源②：乌鲁木齐快聘网 wlmqkp.com（本地蓝领站，纯 HTML、无验证码、不登录可见薪资；PLAN-v2 §一）。
  python3 pipeline/cost/sources/wlmqkp.py urumqi [--pages 2]
按篮子关键词搜 list.php?searchkey=保安&city=210 → 详情页 show.php?id=N：标题、薪资、公司、区域、职位详情（确数工资和工作时间通常在这里）、
更新时间 → 同一套 extract_common/judge → jobs_raw.jsonl / rejected.jsonl / report.md。联系方式 = 帖子 URL（站内投递），符合判据。
请求间隔 1–2 秒。
"""
import re, os, sys, time, html, random, subprocess, argparse, datetime, urllib.parse
from common import Rec, write_outputs, extract_common

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
KW={'urumqi':['保安','服务员','收银','理货','超市','快递','分拣','仓储','普工','保洁','门卫','后厨','便利店','骑手']}
CITY={'urumqi':'210'}
CITY_HINT={'urumqi':{'in':['乌鲁木齐','乌市','天山区','沙依巴克区','沙区','新市区','水磨沟区','头屯河区','米东区','达坂城','高新区','经开区'],'out':['昌吉','石河子','库尔勒','哈密','吐鲁番','克拉玛依','伊犁','喀什','阿克苏','五家渠','阜康','呼图壁','奇台','和田','博乐','塔城','阿勒泰']}}

def get(url):
    return subprocess.run(['curl','-s','-m','25','-A',UA,url],capture_output=True,text=True).stdout

def text(h):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',h,flags=re.S); t=re.sub(r'<[^>]+>','\n',t); t=html.unescape(t)
    t=re.sub(r'[ \t　]+',' ',t); return re.sub(r'\n\s*\n+','\n',t)

def rel_date(s, today):
    m=re.search(r'(\d+)\s*(小时|天|分钟)前',s or '')
    if not m: return None
    n=int(m.group(1)); return (today-datetime.timedelta(days=n if m.group(2)=='天' else 0)).isoformat()

def detail(jid, today):
    url=f'https://www.wlmqkp.com/show.php?id={jid}'; t=text(get(url))
    if '职位详情' not in t: return None
    title=(re.search(r'<title>(.*?)</title>',t) or [None,''])[1]
    m=re.search(r'举报\n(.+?)\n(.+?)\n基本信息',t,re.S); title=m.group(1).strip() if m else ''; pay=m.group(2).strip() if m else ''
    region=(re.search(r'所在区域\n(.+?)\n',t) or [None,''])[1].strip()
    company=(re.search(r'网站提示.*?\n\s*([^\n]{2,40}(?:公司|店|厂|院|中心|集团|超市|酒店|餐厅|物业|户\)|\)))\n企业类型',t,re.S) or [None,''])[1].strip()
    if not company:
        m=re.search(r'_(.+?) - 乌鲁木齐快聘',get(url)[:400]); company=m.group(1) if m else ''
    upd=(re.search(r'最后更新时间：([^\n]+)',t) or [None,''])[1]
    body=(re.search(r'职位详情\n(.*?)\n本职位没有收费项目|职位详情\n(.*?)\n网站提示',t,re.S) or [None,'',''])
    body=(body[1] or body[2] or '').strip() if body else ''
    posted=rel_date(upd,today) or (re.search(r'(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}\n企业最近登录',t) or [None,None])[1]
    raw=f'{title}\n{pay}\n{company}\n所在区域 {region}\n{body}'
    return {'url':url,'title':title,'pay':pay,'company':company,'region':region,'posted':posted,'raw':raw}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--span',type=int,default=260,help='从首页最大 id 往下扫多少个'); ap.add_argument('--days',type=int,default=90); a=ap.parse_args()
    city=a.city; today=datetime.date.today()
    outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    # 站内搜索和翻页都跳登录（2026-09-15 实测），只有首页 20 条和 show.php?id= 详情页是公开的：从首页最大 id 往下逐个读详情
    front=get('https://www.wlmqkp.com/list.php'); ids=[int(x) for x in re.findall(r'show\.php\?id=(\d+)',front)]
    if not ids: print('首页取不到职位'); return
    top=max(ids); log=[f'首页 20 条，最大 id {top}；往下扫 {a.span} 个详情页']
    recs=[]; miss=0; kws=KW[city]
    for jid in range(top, top-a.span, -1):
        d=detail(jid,today); time.sleep(random.uniform(0.8,1.6))
        if not d: miss+=1; continue
        if not any(k in (d['title']+d['raw'][:200]) for k in kws): continue
        r=Rec(city=city, source='wlmqkp', source_url=d['url'], fetched_at=today.isoformat(), posted_at=d['posted'] or '', raw=d['raw'], account='乌鲁木齐快聘网', article_title=d['title'])
        extract_common(r, CITY_HINT[city])
        r['employer']=d['company'] or r.get('employer'); r['title']=d['title'] or r.get('title'); r['location']=d['region'] or r.get('location'); r['in_city']=True if d['region'] else r['in_city']
        if r['employer'] and re.search(r'人力资源|劳务|派遣|外包|人才',r['employer']): r['via_agent']=True
        recs.append(r)
    log.append(f'详情页缺失/删除 {miss} 个；命中篮子关键词 {len(recs)} 条')
    write_outputs(outdir, 'wlmqkp', recs, log, a.days)

if __name__=='__main__': main()

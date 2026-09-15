#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源⑤之二：微信群聊天记录导出（微信 Mac 版「导出聊天记录」的 .docx / .txt）→ 一条消息一个气泡 → 编号岗位各成一条 →
common.py 抽取 + 判据 → jobs_raw / rejected / report（source=wechat_group，account=发消息的昵称，posted_at=记录里的日期）。
  python3 pipeline/cost/wechat_chat.py urumqi 聊天.docx [--days 180] [--outdir 测试目录] [--table]
- 「上一休一」没写每班几小时：按用户 2026-09-15 18:30 定的默认 24 小时在岗算（标 24h岗(默认)）；「上24休24」= 24 小时班、月 15 班。
- 手机号写盘前打码；--table 打印逐条判定表给人看。
"""
import re, os, sys, json, argparse, datetime, zipfile, html
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE,'sources')); sys.path.insert(0, HERE)
from common import Rec, extract_common, write_outputs, judge, is_post, mask
from weixin_sogou import CITY_HINT
from wechat_ingest import split_bubble
from weixin_sogou import split_posts
import collections

DATE=re.compile(r'^[—-]+\s*(\d{4}-\d{2}-\d{2})\s*[—-]+$')
HEAD=re.compile(r'^(.{1,24}?)\s{2,}(\d{1,2}:\d{2})$')

def docx_text(path):
    if path.lower().endswith('.docx'):
        xml=zipfile.ZipFile(path).read('word/document.xml').decode('utf-8')
        return [html.unescape(''.join(re.findall(r'<w:t[^>]*>(.*?)</w:t>',p,flags=re.S))) for p in re.findall(r'<w:p[ >].*?</w:p>',xml,flags=re.S)]
    return open(path,encoding='utf-8').read().split('\n')

def messages(lines):
    """→ [{'date','sender','time','text'}]"""
    out=[]; date=None; cur=None
    for ln in lines:
        s=ln.strip()
        m=DATE.match(s)
        if m: date=m.group(1); cur=None; continue
        m=HEAD.match(s)
        if m and not re.search(r'\d{4,}',m.group(1)) or (m and re.match(r'^[^\d]{0,6}1[3-9]\d{9}$',m.group(1))):   # 昵称可能就是「罗15276776616」
            cur={'date':date,'sender':m.group(1).strip(),'time':m.group(2),'lines':[]}; out.append(cur); continue
        if cur is not None: cur['lines'].append(s)
    for m in out: m['text']=re.sub(r'\n{3,}','\n\n','\n'.join(m['lines'])).strip()
    return [m for m in out if m['text']]

AD=re.compile(r'培训学校|培训机构|培训班|考证班|学费|报名费|取证后|拿证后|证.{0,4}(?:办理|速办|代办)')   # 「必需有消防国考证」「岗前培训」不是广告
STREET=re.compile(r'(北京|上海|广州|深圳|成都|重庆|西安|兰州|南京|武汉|郑州|西宁|银川|昆明|贵阳|长沙|天津|济南|青岛|沈阳|哈尔滨|合肥|福州|厦门|南昌|太原|石家庄|海口|三亚|苏州|宁波|东莞|佛山|珠海|伊犁|哈密|吐鲁番|喀什|和田|塔城|阿勒泰|昌吉|石河子|库尔勒|克拉玛依|阿克苏)(?:东|西|南|北|中)?(?:路|街|大道|巷|大厦)')
def posts_of(text):
    """一条消息里可能贴了好几个岗位：先按空行分块，含电话的块收尾一条；再交给文章切帖器切编号/工资行"""
    blocks=[b.strip() for b in re.split(r'\n\s*\n', text) if b.strip()]
    posts=[]; cur=[]
    for b in blocks:
        cur.append(b)
        if re.search(r'1[3-9]\d{9}|微信',b): posts.append('\n'.join(cur)); cur=[]
    if cur: posts.append('\n'.join(cur))
    out=[]
    for p in posts: out+=(split_bubble(p) if re.search(r'^\s*(?:\d{1,2}[.、．]|[①-⑩])',p,flags=re.M) else split_posts(p))   # 编号岗位：公共行（时间/联系）附给每条
    phones=set(re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)', text))
    if len(phones)==1:   # 一条消息只有一个电话：贴了几个岗位都是它
        ph=phones.pop(); out=[o if re.search(r'1[3-9]\d{9}|微信',o) else o+'\n联系：'+ph for o in out]
    return out

def fix_city(r, hint):
    t=STREET.sub('', r['raw'])
    r['in_city']=any(h in t for h in hint['in']) or not any(h in t for h in hint['out'])

def shift_defaults(r):
    t=r['raw']
    m=re.search(r'上\s*(\d{2})\s*休\s*(\d{2})',t)
    if m and not r.get('hours_per_day') and int(m.group(1))>=12:      # 上24休24 / 上12休24
        on=int(m.group(1)); off=int(m.group(2)); r['hours_per_day']=float(on); r['days_per_month']=round(30*24/(on+off)); r['hours_flag']=(r.get('hours_flag','')+' %dh班'%on).strip()
    elif '上一休一未写班长' in r.get('hours_flag','') and not r.get('hours_per_day'):
        r['hours_per_day']=24.0; r['hours_flag']=r['hours_flag'].replace('上一休一未写班长','24h岗(默认)')
    hpd=r.get('hours_per_day'); dpm=r.get('days_per_month'); w=r.get('wage_value'); u=r.get('wage_unit')
    r['hours_month']=round(hpd*dpm) if (hpd and dpm) else None
    if r['hours_month'] and w: r['hourly']=round(w/r['hours_month'],1) if u=='CNY/月' else (w if u=='CNY/小时' else (round(w/hpd,1) if u=='CNY/天' and hpd else None))
    elif w: r['hourly']=w if u=='CNY/小时' else (round(w/hpd,1) if (u=='CNY/天' and hpd) else None)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('file'); ap.add_argument('--days',type=int,default=180); ap.add_argument('--outdir'); ap.add_argument('--table',action='store_true'); a=ap.parse_args()
    today=datetime.date.today(); outdir=a.outdir or os.path.join(HERE,'..','..','cost','data','raw',a.city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    msgs=messages(docx_text(a.file)); recs=[]; log=[f'{os.path.basename(a.file)}: {len(msgs)} 条消息']
    for m in msgs:
        for p in posts_of(m['text']):
            r=Rec(city=a.city, source='wechat_group', source_url=None, fetched_at=today.isoformat(), posted_at=m['date'] or today.isoformat(), raw=p, account=m['sender'], article_title=os.path.basename(a.file))
            extract_common(r, CITY_HINT[a.city]); fix_city(r, CITY_HINT[a.city]); shift_defaults(r); r['ad']=bool(AD.search(p)); r['raw']=mask(r['raw']); recs.append(r)
    # 同一帖子两天各发一次 / 同一人刷屏：按 (电话, 工资, 岗位) 去重留最新；纯重复原文也去掉
    seen={}; uniq=[]
    for r in sorted(recs, key=lambda r:r['posted_at']):
        k=(r.get('contact'), r.get('wage_value'), r.get('title'), (r.get('hours_text') or '')[:20])
        if k in seen: uniq[seen[k]]=r
        else: seen[k]=len(uniq); uniq.append(r)
    log.append(f'切出 {len(recs)} 条，去重后 {len(uniq)} 条'); recs=uniq
    if a.table:
        rows=[r for r in recs if is_post(r)]
        print(f'消息 {len(msgs)} 条 → 招工帖 {len(rows)} 条（非招工 {len(recs)-len(rows)} 条不计）\n')
        print('| # | 日期 | 发帖人 | 岗位 | 雇主/地点 | 工资 | 工时 | 月工时 | 时薪 | 联系 | 判定 |'); print('|---|---|---|---|---|---|---|---|---|---|---|')
        ZH={'no_wage':'没写工资','range_wage':'工资是区间','no_hours':'没写工时','hours_partial':'工时只写一半','no_contact':'没联系方式','off_basket':'不在篮子','off_city':'外地','agent_unnamed':'中介未写单位','no_date':'没日期','stale':'过期'}
        for i,r in enumerate(rows,1):
            rs=[x for x in judge(r,a.days) if x!='no_url']; 
            if r.get('ad'): rs=['广告(培训/考证)']
            v='✅ 合格' if not rs else '、'.join(ZH.get(x,x) for x in rs); r['verdict']=v
            print(f"| {i} | {r['posted_at'][5:]} | {r['account'][:8]} | {r.get('title') or '—'} | {(r.get('employer') or r.get('location_phrase') or '—')[:18]} | {r.get('wage_value') or '—'} {r.get('wage_unit') or ''} | {(r.get('hours_text') or '—')[:26]} {r.get('hours_flag','')} | {r.get('hours_month') or '—'} | {r.get('hourly') or '—'} | {r.get('contact') or '—'} | {v} |")
        ok=[r for r in rows if r.get('verdict')=='✅ 合格']; c=collections.Counter()
        for r in rows:
            if r.get('verdict')!='✅ 合格':
                for x in r['verdict'].split('、'): c[x]+=1
        print(f"\n合格 {len(ok)} / {len(rows)}；缺项分布：" + '、'.join(f'{k} {v}' for k,v in c.most_common()))
        if ok: print('合格的：' + '；'.join(f"{r.get('title')} {r.get('wage_value'):g}元/月 {r.get('hours_text','')} → {r.get('hourly')} 元/时" for r in ok))
    for r in recs:
        if r.get('ad'): r['reasons_extra']=['ad']
    write_outputs(outdir,'wechat_group',recs,log,a.days)

if __name__=='__main__': main()

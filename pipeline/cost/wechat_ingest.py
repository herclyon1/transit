#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源⑤「转发即入库」：用户发来的微信群招工帖截图 → 离线 OCR（Apple Vision，简体中文）→ 切成一条条帖子 → 走 common.py 的
抽取与 PLAN-v2 判据 → jobs_raw.jsonl / rejected.jsonl / report.md（source = wechat_group），再由 ingest.py 写进城市 JSON。
  python3 pipeline/cost/wechat_ingest.py urumqi 截图1.png 截图2.png … [--date 2026-09-15] [--days 90] [--dump]
- 截图里的一个聊天气泡 = 一条帖子；气泡里「1./2./①」编号的多个岗位各成一条，气泡里的公共行（工作地点/工作时间/联系）附给每条；
- 发帖日期：截图里有「昨天 12:20」「9月14日 08:10」这种时间分隔就用它，没有就用 --date（默认今天）；
- 手机号在写盘前就打码（raw 里也打），群截图不进仓库，只留 OCR 出来的文字；`--dump` 打印每个气泡的文字，用来核 OCR。
OCR 工具：pipeline/cost/tools/ocr.swift（首次运行自动 swiftc 编译到 tools/.build/ocr）。
"""
import re, os, sys, json, argparse, datetime, subprocess, statistics
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE,'sources'))
from common import Rec, extract_common, write_outputs
from weixin_sogou import CITY_HINT

TOOLS=os.path.join(HERE,'tools'); OCR=os.path.join(TOOLS,'.build','ocr')
SHARED=re.compile(r'^.{0,2}(?:工作时间|上班时间|班次|工作地点|上班地点|地址|地点|联系|电话|☎|📞|要求|招录条件|任职要求|待遇|福利|薪资待遇|工资待遇)|^\D{0,4}1[3-9]\d{9}')   # 表情被 OCR 成杂字，前面容 2 个字；整行是电话也算公共行
ITEM=re.compile(r'^\s*(?:(\d{1,2})[.、．:：)](?![\d:：])|[①②③④⑤⑥⑦⑧⑨⑩])\s*')   # 「10:00-19:00」不是第 10 条
CHROME=re.compile(r'^(?:\d{1,2}:\d{2}|<|[•。]+|\^?\s*\d+条新消息|按住\s*说话|发送|微信|WeChat)$')
TIME_SEP=re.compile(r'^(?:(今天|昨天|前天)|(\d{1,2})月(\d{1,2})日|(星期[一二三四五六日天]))?\s*(?:上午|下午|晚上|凌晨)?\s*(\d{1,2}):(\d{2})$')
PHONE=re.compile(r'(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)')

def ocr(paths):
    if not os.path.exists(OCR):
        os.makedirs(os.path.dirname(OCR),exist_ok=True)
        subprocess.run(['swiftc','-O','-o',OCR,os.path.join(TOOLS,'ocr.swift')],check=True)
    out=subprocess.run([OCR]+paths,capture_output=True,text=True,check=True).stdout
    return [json.loads(l) for l in out.splitlines() if l.strip()]

def bubbles(page):
    """OCR 行 → 气泡列表 [{'account','lines':[(text,wide)], 'date'}]。状态栏/标题/输入栏按位置和样式丢掉；
       发送者昵称 = 气泡前一行、短、没数字、x 略靠左；时间分隔 = 居中的短行。"""
    W,H=page['width'],page['height']; L=[l for l in page['lines'] if l['h']>0]
    L=[l for l in L if 0.07*H<l['y']<0.92*H and not CHROME.match(l['text'].strip()) and not (l['x']<0.12*W and l['w']<0.08*W)]   # 头像里的字（x 太靠左又很窄）丢掉
    if not L: return [],None
    hs=statistics.median([l['h'] for l in L]); title=None
    out=[]; cur=None; prev=None; pending_name=None; date=None
    for l in L:
        t=l['text'].strip(); cx=l['x']+l['w']/2
        if page['lines'].index(l)<6 and abs(cx-W/2)<0.12*W and re.search(r'群|（\d+）|\(\d+\)',t) and l['y']<0.12*H: title=t; continue
        m=TIME_SEP.match(t)
        if m and abs(cx-W/2)<0.15*W and l['w']<0.5*W: date=m; cur=None; prev=None; continue
        gap=(l['y']-(prev['y']+prev['h'])) if prev else 1e9
        is_name = len(t)<=8 and not re.search(r'\d|[:：]',t) and l['w']<0.35*W and (prev is None or gap>0.9*hs) and l['conf']>=0.5
        if is_name and (cur is None or gap>0.9*hs):
            # 昵称：下一行开始是新气泡
            pending_name=t; prev=l; cur=None; continue
        if cur is None or gap>1.6*hs or (pending_name and gap>0.3*hs):
            cur={'account':pending_name or title or '', 'lines':[], 'date':date, 'x0':l['x'], 'wmax':0}; out.append(cur); pending_name=None
        cur['lines'].append([t,l['w']]); cur['wmax']=max(cur['wmax'],l['w']); prev=l
    for b in out:
        joined=''; parts=[]
        for i,(t,w) in enumerate(b['lines']):
            nxt=b['lines'][i+1][0] if i+1<len(b['lines']) else None
            joined+=t
            wrapped = w>=0.82*b['wmax'] and nxt is not None and not ITEM.match(nxt) and not SHARED.match(nxt)
            if not wrapped: parts.append(joined); joined=''
        if joined: parts.append(joined)
        b['text']='\n'.join(parts)
    return out,title

def split_bubble(text):
    """编号岗位各成一条：raw = 本岗位的行 + 气泡里其它公共行（地点/时间/联系）。没有编号 → 整个气泡一条。"""
    lines=text.split('\n'); items=[]; shared=[]; cur=None
    for ln in lines:
        if ITEM.match(ln): cur=[ln]; items.append(cur)
        elif cur is not None and not SHARED.match(ln): cur.append(ln)
        else: shared.append(ln)
    if not items: return [text]
    return ['\n'.join(it)+'\n'+'\n'.join(shared) for it in items]

def mask(t): return PHONE.sub(lambda m:m.group(1)+'****'+m.group(3),t)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('images',nargs='+'); ap.add_argument('--date',default=datetime.date.today().isoformat())
    ap.add_argument('--days',type=int,default=90); ap.add_argument('--dump',action='store_true'); ap.add_argument('--outdir',help='测试用：写到别处，不碰 cost/data/raw'); a=ap.parse_args()
    today=datetime.date.today(); base=datetime.date.fromisoformat(a.date)
    outdir=a.outdir or os.path.join(HERE,'..','..','cost','data','raw',a.city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    recs=[]; log=[]
    for page in ocr([os.path.abspath(p) for p in a.images]):
        name=os.path.basename(page['file'])
        if page.get('error'): log.append(f'{name}: OCR 失败 {page["error"]}'); continue
        bs,title=bubbles(page)
        log.append(f'{name}: OCR {len(page["lines"])} 行 → {len(bs)} 个气泡（群：{title or "?"}）')
        for b in bs:
            d=b['date']; posted=base
            if d:
                if d.group(1)=='昨天': posted=base-datetime.timedelta(days=1)
                elif d.group(1)=='前天': posted=base-datetime.timedelta(days=2)
                elif d.group(2): posted=datetime.date(base.year,int(d.group(2)),int(d.group(3)))
            if a.dump: print(f'--- {name} 「{b["account"]}」 {posted}\n{b["text"]}\n')
            posts=split_bubble(b['text'])
            for p in posts:
                r=Rec(city=a.city, source='wechat_group', source_url=None, fetched_at=today.isoformat(), posted_at=posted.isoformat(),
                      raw=p, account=b['account'] or (title or ''), article_title=f'截图 {name}')
                extract_common(r, CITY_HINT[a.city]); r['raw']=mask(r['raw']); recs.append(r)
            log.append(f'  「{b["account"]}」气泡 {len(b["lines"])} 行 → {len(posts)} 条')
    write_outputs(outdir, 'wechat_group', recs, log, a.days)

if __name__=='__main__': main()

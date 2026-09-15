#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源③：微信群的网页可抓版——搜狗微信搜索里本地公众号的招工文章（PLAN-v2 §一）。
  python3 pipeline/cost/sources/weixin_sogou.py urumqi [--max-articles 30]
流程：按城市的查询词搜 weixin.sogou.com（type=2 文章）→ 解 /link 反爬（k/h + cookie）→ 取 mp.weixin.qq.com 正文
  → 按分隔线/空行切成一条条帖子 → 抽工资/工时/联系/雇主 → 按 PLAN-v2 判据分进 jobs_raw.jsonl / rejected.jsonl → 写 report.md。
每次请求间隔 2–4 秒；一轮最多 --max-articles 篇；只读公开网页。
"""
import re, sys, os, json, time, html, random, subprocess, argparse, datetime, urllib.parse
from common import Rec, judge, write_outputs, BASKET_KW, extract_common

UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
QUERIES={
  'urumqi':['乌鲁木齐 招聘 保安 工资 月休','乌鲁木齐 招聘 服务员 工资 月休','乌鲁木齐 招聘 超市 理货 收银 工资','乌鲁木齐 招聘 保洁 工资 月休',
            '乌鲁木齐 招聘 普工 工资 月休','乌鲁木齐 招聘 快递 分拣 工资','乌鲁木齐 兼职 招聘信息','乌鲁木齐 招聘会 岗位 工资'],
}
CITY_HINT={'urumqi':{'in':['乌鲁木齐','乌市','天山区','沙依巴克区','沙区','新市区','水磨沟区','头屯河区','米东区','达坂城','高新区','经开区','开发区','红山','南湖','火车站','铁路局','红光山','八道湾','维泰路','友好','小西门','大巴扎','幸福路','北京路','长江路','河滩'],
                     'out':['呼图壁','昌吉','奇台','库尔勒','石河子','伊犁','伊宁','哈密','吐鲁番','阿克苏','喀什','克拉玛依','五家渠','玛纳斯','阜康','芳草湖','团场','和田','博乐','塔城','阿勒泰','库车','轮台',
                            '北京','上海','广州','深圳','成都','重庆','西安','兰州','拉萨','日喀则','连云港','杭州','南京','武汉','郑州','西宁','银川','昆明','贵阳','长沙','天津','济南','青岛','沈阳','哈尔滨','合肥','福州','厦门','南昌','太原','石家庄','呼和浩特','海口','三亚','苏州','宁波','东莞','佛山','珠海']}}

def curl(url, jar, referer=None, extra=()):
    cmd=['curl','-s','-m','25','-L','-A',UA,'-b',jar,'-c',jar]+(['-e',referer] if referer else [])+list(extra)+[url]
    return subprocess.run(cmd,capture_output=True,text=True).stdout

def search(q, jar):
    url='https://weixin.sogou.com/weixin?type=2&ie=utf8&s_from=input&query='+urllib.parse.quote(q)
    h=curl(url, jar, 'https://weixin.sogou.com/')
    items=re.findall(r'<h3>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?timeConvert\(\'(\d+)\'\)',h,re.S)
    out=[]
    for u,t,ts in items:
        out.append({'link':html.unescape(u).replace(' ','%20'),'title':html.unescape(re.sub('<[^>]+>','',t)).strip(),'ts':int(ts)})
    return out

def resolve(link, jar):
    b=random.randint(1,100); a=link.index('url='); u=link+'&k=%d&h=%s'%(b,link[a+4+21+b])
    r=curl('https://weixin.sogou.com'+u, jar, 'https://weixin.sogou.com/weixin?type=2')
    parts=re.findall(r"url \+= '([^']*)'",r); full=''.join(parts).replace('@','')
    return full if full.startswith('http') else None

def article(url, jar, cache_dir=None):
    import hashlib
    cf=cache_dir and os.path.join(cache_dir, hashlib.md5(url.encode()).hexdigest()[:12]+'.html')
    art=open(cf,encoding='utf-8').read() if (cf and os.path.exists(cf)) else curl(url, jar)
    if cf and not os.path.exists(cf) and 'js_content' in art: open(cf,'w',encoding='utf-8').write(art)
    if 'js_content' not in art: return None
    t=re.sub(r'<script.*?</script>','',art,flags=re.S); t=re.sub(r'<style.*?</style>','',t,flags=re.S)
    m=re.search(r'id="js_content"(.*?)(<div class="rich_media_tool|id="js_pc_qr_code)',t,re.S); body=m.group(1) if m else t
    body=re.sub(r'<br\s*/?>|</p>|</section>|</div>|</li>','\n',body); body=html.unescape(re.sub(r'<[^>]+>','',body))
    body=re.sub(r'[ \t　]+',' ',body); body=re.sub(r'\n\s*\n+','\n',body).strip()
    title=html.unescape(re.sub(r'<[^>]+>','',(re.search(r'<h1[^>]*>(.*?)</h1>',art,re.S) or [None,''])[1])).strip()
    acct=re.search(r'id="js_name"[^>]*>\s*(.*?)\s*<',art,re.S); pub=re.search(r"createTime = '([^']+)'",art)
    return {'title':title,'account':acct.group(1).strip() if acct else '','published':(pub.group(1)[:10] if pub else ''),'text':body}

WAGE_LINE=re.compile(r'(?:工资|月薪|薪资|待遇|到手|时薪|日薪|元/|/月|/天|单休|双休|包吃|管吃|包住|管住)')
HEAD_LINE=re.compile(r'^\s*(?:[❶-❿①-⑩]|\d{1,2}\s*[，,.、]\s*|【(?!转正|待遇|福利|要求|工作)|\[庆祝\]|招\s?聘|急招|诚聘|招[^\n]{0,12}(?:名|人)\b|[^\n]{0,30}(?:厂|公司|店|院|仓|驿站|物业|超市|酒店|餐厅|基地|学校|医院)[^\n]{0,8}招)')
SEP_LINE=re.compile(r'^\s*[-—_=·•～~]{4,}\s*$')
CONTACT=re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)|(?:微信|VX|vx|v信|qq|QQ)[:：\s]*[A-Za-z0-9_\-]{5,20}')
def split_posts(text):
    """一篇文章十几条帖子：分隔线/编号/「××厂招」起新条；同一条里出现第二个工资行也起新条；
       只有联系方式的小块（「报名加微信…」）把联系方式补给前面缺联系的条，然后丢掉。"""
    blocks=[[]]
    for line in text.split('\n'):
        if SEP_LINE.match(line): blocks.append([]); continue
        cur=blocks[-1]; joined='\n'.join(cur)
        nums_line=set(re.findall(r'\d{3,5}',line)); nums_prev=set(re.findall(r'\d{3,5}',joined))
        new = bool(cur) and (HEAD_LINE.match(line) or (WAGE_LINE.search(line) and nums_line and WAGE_LINE.search(joined) and nums_prev and not (nums_line & nums_prev)))
        if new: blocks.append([line])
        else: cur.append(line)
    blocks=['\n'.join(b).strip() for b in blocks if '\n'.join(b).strip()]
    out=[]
    for b in blocks:
        contact_only = CONTACT.search(b) and not re.search(r'\d{3,5}',re.sub(r'1[3-9]\d{9}','',b)) and len(b)<80
        if contact_only and out:
            c=CONTACT.search(b).group(0)
            for k in range(len(out)-1, max(-1,len(out)-3), -1):
                if not CONTACT.search(out[k]): out[k]+='\n联系：'+c
            continue
        if out and len(b)<25 and not re.search(r'\d',b): out[-1]+='\n'+b; continue
        out.append(b)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--max-articles',type=int,default=30); ap.add_argument('--days',type=int,default=90); a=ap.parse_args()
    city=a.city; today=datetime.date.today(); outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    jar=os.path.join(outdir,'.sogou.cookies'); open(jar,'a').close(); curl('https://weixin.sogou.com/',jar)
    cache=os.path.join(outdir,'articles'); os.makedirs(cache,exist_ok=True)
    for f in ('jobs_raw.jsonl','rejected.jsonl'):
        fp=os.path.join(outdir,f)
        if os.path.exists(fp): os.remove(fp)   # 一天内重跑覆盖当天结果
    seen=set(); recs=[]; log=[]; n_art=0
    for q in QUERIES[city]:
        items=search(q,jar); time.sleep(random.uniform(2,4)); log.append(f'搜「{q}」：{len(items)} 篇')
        for it in sorted(items,key=lambda x:-x['ts']):
            if n_art>=a.max_articles: break
            age=(today-datetime.date.fromtimestamp(it['ts'])).days
            if age>a.days: log.append(f'  跳过（{age} 天前）：{it["title"][:40]}'); continue
            key=it['title']+str(it['ts'])
            if key in seen: continue
            seen.add(key)
            mp=resolve(it['link'],jar); time.sleep(random.uniform(2,4))
            if not mp: log.append(f'  反爬没解开：{it["title"][:40]}'); continue
            art=article(mp,jar,cache); time.sleep(random.uniform(2,4)); n_art+=1
            if not art: log.append(f'  正文取不到：{it["title"][:40]}'); continue
            posts=split_posts(art['text'])
            log.append(f'  {art["published"] or "?"} 「{art["account"]}」{art["title"][:40]}：切出 {len(posts)} 条')
            for p in posts:
                r=Rec(city=city, source='weixin_sogou', source_url=mp, fetched_at=today.isoformat(), posted_at=art['published'] or datetime.date.fromtimestamp(it['ts']).isoformat(),
                      raw=p, account=art['account'], article_title=art['title'])
                extract_common(r, CITY_HINT[city]); recs.append(r)
        if n_art>=a.max_articles: break
    write_outputs(outdir, 'weixin_sogou', recs, log, a.days)

if __name__=='__main__': main()

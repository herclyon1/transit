#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源③：微信群的网页可抓版——搜狗微信搜索里本地公众号的招工文章（PLAN-v2 §一）。
  python3 pipeline/cost/sources/weixin_sogou.py urumqi [--max-articles 30]
流程：按城市的查询词搜 weixin.sogou.com（type=2 文章）→ 解 /link 反爬（k/h + cookie）→ 取 mp.weixin.qq.com 正文
  → 按分隔线/空行切成一条条帖子 → 抽工资/工时/联系/雇主 → 按 PLAN-v2 判据分进 jobs_raw.jsonl / rejected.jsonl → 写 report.md。
每次请求间隔 2–4 秒；一轮最多 --max-articles 篇；只读公开网页。
文章按 biz_mid_idx 缓存（articles/index.json 记搜狗条目→缓存键→原链接），同一篇不重下；--replay 从缓存重跑解析不碰网。
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

def art_key(art):
    biz=re.search(r'biz = "([^"]*)"',art); mid=re.search(r'var mid = "(\d+)"',art); idx=re.search(r'var idx = "(\d+)"',art)
    return f"{biz.group(1) if biz else ''}_{mid.group(1) if mid else ''}_{idx.group(1) if idx else ''}".replace('=','')

def parse_article(art):
    if 'js_content' not in art: return None
    t=re.sub(r'<script.*?</script>','',art,flags=re.S); t=re.sub(r'<style.*?</style>','',t,flags=re.S)
    m=re.search(r'id="js_content"(.*?)(<div class="rich_media_tool|id="js_pc_qr_code)',t,re.S); body=m.group(1) if m else t
    body=re.sub(r'<br\s*/?>|</p>|</section>|</div>|</li>','\n',body); body=html.unescape(re.sub(r'<[^>]+>','',body))
    body=re.sub(r'[ \t　]+',' ',body); body=re.sub(r'\n\s*\n+','\n',body).strip()
    title=html.unescape(re.sub(r'<[^>]+>','',(re.search(r'<h1[^>]*>(.*?)</h1>',art,re.S) or [None,''])[1])).strip()
    acct=re.search(r'id="js_name"[^>]*>\s*(.*?)\s*<',art,re.S); pub=re.search(r"createTime = '([^']+)'",art)
    return {'title':title,'account':acct.group(1).strip() if acct else '','published':(pub.group(1)[:10] if pub else ''),'text':body,'key':art_key(art)}

def load_index(cache_dir):
    f=os.path.join(cache_dir,'index.json'); return json.load(open(f,encoding='utf-8')) if os.path.exists(f) else {'sogou':{},'articles':{}}
def save_index(cache_dir, ix): json.dump(ix,open(os.path.join(cache_dir,'index.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=0)

def article(url, jar, cache_dir):
    """下载并按 biz_mid_idx 缓存；返回 parse_article 结果 + url。同一篇文章不同轮的搜狗链接签名不同，所以缓存键不能用 URL。"""
    art=curl(url, jar); a=parse_article(art)
    if not a: return None
    ix=load_index(cache_dir); cf=os.path.join(cache_dir,a['key']+'.html')
    if not os.path.exists(cf): open(cf,'w',encoding='utf-8').write(art)
    ix['articles'][a['key']]={'url':url,'title':a['title'],'account':a['account'],'published':a['published']}; save_index(cache_dir,ix)
    a['url']=url; return a

def cached_article(key, cache_dir):
    cf=os.path.join(cache_dir,key+'.html')
    if not os.path.exists(cf): return None
    a=parse_article(open(cf,encoding='utf-8').read())
    if a: a['url']=load_index(cache_dir)['articles'].get(key,{}).get('url')
    return a

WAGE_LINE=re.compile(r'(?:工资|月薪|薪资|待遇|到手|时薪|日薪|元/|/月|/天|单休|双休|包吃|管吃|包住|管住)')
HEAD_LINE=re.compile(r'^\s*(?:🔥|『地址』|[❶-❿①-⑩]|\d{1,2}\s*[，,.、]\s*|岗位[一二三四五六七八九十\d]+\s*[:：]?|【(?!转正|待遇|福利|要求|工作)|\[庆祝\]|招\s?聘(?!名额|职位|要求|人数|岗位|条件|对象|范围|流程|时间|地址|说明|需求|信息|简章|电话|方式|专业)|急招|诚聘|招[^\n]{0,12}(?:名|人)\b|[^\n]{0,30}(?:厂|公司|店|院|仓|驿站|物业|超市|酒店|餐厅|基地|学校|医院)[^\n]{0,8}招)')
SEP_LINE=re.compile(r'^\s*[-—_=·•～~]{4,}\s*$|长按二维码查看详情|扫二维码报名|应聘时请备注|^\s*DR\d{6,}\s*$')
ACCOUNT_BLOCK=['川渝掌上厨师平台','厨师互帮圈','掌上厨夜推号']   # 全国厨师汇总号，几乎全外地：不是口径紧，是来源不对
CONTACT=re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)|(?:微信|VX|vx|v信|qq|QQ)[:：\s]*[A-Za-z0-9_\-]{5,20}')
def split_posts(text):
    """一篇文章十几条帖子：分隔线/编号/「××厂招」起新条；同一条里出现第二个工资行也起新条；
       只有联系方式的小块（「报名加微信…」）把联系方式补给前面缺联系的条，然后丢掉。"""
    blocks=[[]]
    text=re.sub(r'(?<!\n)(岗位[一二三四五六七八九十\d]+\s*[:：])',r'\n\1',text)
    text=re.sub(r'(?<!\n)\s*([❶-❿①-⑩](?=[^\n]{0,25}(?:招聘|招\d|诚聘|急招|招[^\n]{0,8}(?:名|人))))',r'\n\1',text)   # 「…联系微信：xxx ③××厂招聘」→ ③ 起新条
    for line in text.split('\n'):
        if SEP_LINE.search(line): blocks.append([]); line=SEP_LINE.sub('',line)
        if not line.strip(): continue
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
        if out and len(b)<25 and not re.search(r'\d',b) and not HEAD_LINE.match(b): out[-1]+='\n'+b; continue   # 短碎片并回上一条；但「③××厂招聘」这种头不能并
        out.append(b)
    return out

def process(art, city, today, recs, log, fallback_date=''):
    posts=split_posts(art['text'])
    log.append(f'  {art["published"] or "?"} 「{art["account"]}」{art["title"][:40]}：切出 {len(posts)} 条')
    for p in posts:
        r=Rec(city=city, source='weixin_sogou', source_url=art.get('url'), fetched_at=today.isoformat(), posted_at=art['published'] or fallback_date,
              raw=p, account=art['account'], article_title=art['title'])
        extract_common(r, CITY_HINT[city]); recs.append(r)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--max-articles',type=int,default=30); ap.add_argument('--days',type=int,default=180)
    ap.add_argument('--replay',action='store_true',help='不碰网：把 articles/ 缓存里的文章重新切帖抽取（调解析用）'); ap.add_argument('--date',default=None,help='用哪天的 raw 目录（默认今天）')
    a=ap.parse_args()
    city=a.city; today=datetime.date.today(); outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',city,a.date or today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    cache=os.path.join(outdir,'articles'); os.makedirs(cache,exist_ok=True); ix=load_index(cache)
    recs=[]; log=[]
    if a.replay:
        keys=sorted(k[:-5] for k in os.listdir(cache) if k.endswith('.html') and not re.fullmatch(r'[0-9a-f]{12}\.html',k))
        log.append(f'replay：缓存 {len(keys)} 篇')
        for k in keys:
            art=cached_article(k,cache)
            if not art: continue
            if art['account'] in ACCOUNT_BLOCK: log.append(f'  跳过全国厨师号「{art["account"]}」：{art["title"][:30]}'); continue
            try: age=(today-datetime.date.fromisoformat(art['published'])).days
            except Exception: age=0
            if age>a.days: log.append(f'  跳过（{age} 天前）：{art["title"][:40]}'); continue
            process(art, city, today, recs, log)
        write_outputs(outdir, 'weixin_sogou', recs, log, a.days); return
    jar=os.path.join(outdir,'.sogou.cookies'); open(jar,'a').close(); curl('https://weixin.sogou.com/',jar)
    seen=set(); n_art=0; n_net=0
    for q in QUERIES[city]:
        items=search(q,jar); time.sleep(random.uniform(2,4)); log.append(f'搜「{q}」：{len(items)} 篇')
        for it in sorted(items,key=lambda x:-x['ts']):
            if n_art>=a.max_articles: break
            age=(today-datetime.date.fromtimestamp(it['ts'])).days
            if age>a.days: log.append(f'  跳过（{age} 天前）：{it["title"][:40]}'); continue
            key=it['title']+'|'+str(it['ts'])
            if key in seen: continue
            seen.add(key)
            art=None
            if key in ix['sogou']: art=cached_article(ix['sogou'][key],cache)      # 上一轮已下过这篇：不解反爬、不重下
            if not art:
                mp=resolve(it['link'],jar); time.sleep(random.uniform(2,4))
                if not mp: log.append(f'  反爬没解开：{it["title"][:40]}'); continue
                day=datetime.date.fromtimestamp(it['ts']).isoformat()
                hit=next((k for k,v in ix['articles'].items() if v.get('title')==it['title'] and v.get('published')==day),None)   # 同标题同日期的已缓存：只补链接不重下
                if hit:
                    art=cached_article(hit,cache)
                    if art: art['url']=art['url'] or mp; ix['articles'][hit]['url']=ix['articles'][hit].get('url') or mp
                if not art:
                    art=article(mp,jar,cache); time.sleep(random.uniform(2,4)); n_net+=1
                    if not art: log.append(f'  正文取不到：{it["title"][:40]}'); continue
                    ix=load_index(cache)
                ix['sogou'][key]=art['key']; save_index(cache,ix)
            n_art+=1
            if art['account'] in ACCOUNT_BLOCK: log.append(f'  跳过全国厨师号「{art["account"]}」：{art["title"][:30]}'); continue
            process(art, city, today, recs, log, datetime.date.fromtimestamp(it['ts']).isoformat())
        if n_art>=a.max_articles: break
    log.append(f'本轮取文章 {n_art} 篇，其中联网下载 {n_net} 篇（其余走缓存）')
    write_outputs(outdir, 'weixin_sogou', recs, log, a.days)

if __name__=='__main__': main()

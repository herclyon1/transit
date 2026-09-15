#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""イオンネットスーパー（野田阪神店，配送大阪市北区梅田）搜索页 → raw/osaka/<date>/aeon.jsonl（和 ddmc.jsonl 同构：keyword/rank/name/price/url）。
   python3 pipeline/cost/aeon_grab.py 薄力粉 キャノーラ油 じゃがいも トマト はくさい キャベツ 若どり 豚肉 りんご
   おすすめ順（s=recommend，站点默认）第一页前 12 条；price = 税込（页面标本体价，食品 8% 税，税込 = 本体 × 1.08，和页面「税込」一致）。不登录，店舗見学模式。"""
import json, re, sys, os, html, datetime, urllib.request, urllib.parse
STORE='01050000003080'; STORE_NAME='イオン野田阪神店'
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data','raw','osaka')
def fetch(kw):
    u=f'https://shop.aeon.com/netsuper/{STORE}/search/?q={urllib.parse.quote(kw)}&s=recommend'
    req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36'})
    s=urllib.request.urlopen(req,timeout=40).read().decode('utf-8','ignore')
    items=[]
    for b in re.split(r'class="product details product-item-details"',s)[1:]:
        n=re.search(r'<a class="product-item-link"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>',b); p=re.search(r'class="floor-price">([\d,]+)',b)
        if n and p: items.append((n.group(1),n.group(2),p.group(1)))
    out=[]
    for i,(href,name,price) in enumerate(items[:12]):
        name=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',name))).strip(); base=float(price.replace(',',''))
        out.append({'city':'osaka','platform':'イオンネットスーパー','store':STORE_NAME,'keyword':kw,'sort':'おすすめ順','rank':i+1,'name':name,'price':round(base*1.08,2),'base':base,'unit':'日元','url':href,'fetched_at':datetime.date.today().isoformat()})
    return out,len(items)
def main():
    kws=sys.argv[1:] or ['薄力粉','キャノーラ油','じゃがいも','トマト','はくさい','キャベツ','若どり','豚肉','りんご']
    d=os.path.join(ROOT,datetime.date.today().strftime('%Y%m%d')); os.makedirs(d,exist_ok=True); fp=os.path.join(d,'aeon.jsonl')
    old=[json.loads(l) for l in open(fp,encoding='utf-8')] if os.path.exists(fp) else []
    old=[r for r in old if r['keyword'] not in kws]
    for kw in kws:
        rows,total=fetch(kw); old+=rows; print(f'{kw}: 共 {total} 条，存前 {len(rows)} 条')
    with open(fp,'w',encoding='utf-8') as f:
        for r in old: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('→',fp)
if __name__=='__main__': main()

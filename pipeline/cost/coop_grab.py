#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Co.op Online（Saigon Co.op 官方网店 cooponline.vn，Teko discovery 公开接口）按关键词搜 Co.opmart Buôn Ma Thuột（terminal 138_sgc）
   默认排序前 10 → raw/buon_ma_thuot/<日期>/coop.jsonl（和 ddmc.jsonl 同构）。
   python3 pipeline/cost/coop_grab.py "bột mì" "dầu ăn" ...
   价 = latestPrice（现价，含促销）；规格在商品名里（1kg / 500g / 1L / 400ml / khay 500g）。"""
import json, sys, os, datetime, urllib.request
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data','raw','buon_ma_thuot')
API='https://discovery.tekoapis.com/api/v1/search'; TERMINAL='138_sgc'
def fetch(q,n=10):
    body=json.dumps({'terminalCode':TERMINAL,'query':q,'pagination':{'index':0,'limit':n}}).encode()
    req=urllib.request.Request(API,data=body,headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    d=json.loads(urllib.request.urlopen(req,timeout=40).read().decode('utf-8'))
    out=[]
    for i,p in enumerate(d.get('result',{}).get('products',[])[:n]):
        info=p.get('productInfo',{}); price=p.get('prices') or [{}]; pr=price[0] if isinstance(price,list) else price
        latest=float(pr.get('latestPrice') or info.get('latestPrice') or p.get('latestPrice') or 0); supplier=float(pr.get('supplierRetailPrice') or info.get('supplierRetailPrice') or 0)
        out.append({'city':'buon_ma_thuot','platform':'Co.op Online','store':'Co.opmart Buôn Ma Thuột（71 Nguyễn Tất Thành）','keyword':q,'sort':'默认','rank':i+1,'name':info.get('name',''),'price':latest,'list_price':supplier,'unit':'越南盾','uom':info.get('uomName',''),'sku':info.get('sku'),'url':'https://cooponline.vn/products/'+str(info.get('sku','')),'fetched_at':datetime.date.today().isoformat()})
    return out
def main():
    kws=sys.argv[1:]
    d=os.path.join(ROOT,datetime.date.today().strftime('%Y%m%d')); os.makedirs(d,exist_ok=True); fp=os.path.join(d,'coop.jsonl')
    old=[json.loads(l) for l in open(fp,encoding='utf-8')] if os.path.exists(fp) else []
    old=[r for r in old if r['keyword'] not in kws]
    for kw in kws:
        rows=fetch(kw); old+=rows; print(kw,len(rows),[ (r['name'][:34],r['price']) for r in rows[:4]])
    with open(fp,'w',encoding='utf-8') as f:
        for r in old: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('→',fp)
if __name__=='__main__': main()

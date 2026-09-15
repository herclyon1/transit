#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础食材月费 = 篮子实价 × 项目统一用量（单身），写进 cities/<city>.json 的 living_official.food（confidence=estimated，标「按篮子实价推算」）。
  python3 pipeline/cost/food_basket.py urumqi
规则（maa/用户 2026-09-15）：有**市级**官方统计（大阪 家計調査 那种）就用官方，不跑这个脚本；没有的城市用篮子推算并标明；
「全省人均消费 × 食品占比」这种省级推算一律不用。
统一用量（单身一个月，粗）：大米 5 kg ×1、鸡蛋 10 个 ×3、牛奶 1 L ×10、面包 1 kg ×2、拌面/一顿快餐 ×22（工作日午餐）、可乐 1 L ×2、啤酒 6 罐 ×1。
"""
import json, sys, os, datetime
QTY={'rice5kg':1,'eggs10':3,'milk1l':10,'bread1kg':2,'curry_rice':22,'cola1l':2,'beer6':1}
ZH={'rice5kg':'大米 5 kg','eggs10':'鸡蛋 10 个','milk1l':'牛奶 1 L','bread1kg':'面包 1 kg','curry_rice':'一顿快餐','cola1l':'可乐 1 L','beer6':'啤酒 6 罐'}
CITY=sys.argv[1]; FILE={'buon_ma_thuot':'buonmathuot'}.get(CITY,CITY)
p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data','cities',f'{FILE}.json'); d=json.load(open(p,encoding='utf-8'))
b=d.get('basket',{}); parts=[]; total=0; missing=[]
for k,q in QTY.items():
    v=b.get(k,{}).get('value')
    if v is None: missing.append(k); continue
    total+=v*q; parts.append(f"{ZH[k]} {v:g}×{q}")
cur=d.get('currency','')
unit={'CNY':'元/月','VND':'越南盾/月','JPY':'日元/月'}.get(cur,cur+'/月')
d['living_official']['food']={"label":"基础食材月费（按篮子实价推算）","value":round(total),"unit":unit,"confidence":"estimated","n":None,
  "source_url":None,"source_name":"本页篮子各项的平台实价 × 项目统一用量（单身）","fetched_at":datetime.date.today().isoformat(),
  "note":"= "+" + ".join(parts)+f" = {round(total):,}。用量是项目统一假定（见 cost/data/README.md），价是篮子里当地人实际在用的平台现价；不是统计均值。"+(f" 缺 {', '.join(missing)}，没算进去。" if missing else "")}
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f"{CITY}: 基础食材月费 {round(total):,} {unit}（{len(parts)} 项）"+(f" 缺 {missing}" if missing else ''))

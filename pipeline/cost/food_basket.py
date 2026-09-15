#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础食材月费 = 篮子实价 × 项目统一用量（单身），写进 cities/<city>.json 的 living_official.food（confidence=estimated，标「按平台实价推算」）。
  python3 pipeline/cost/food_basket.py urumqi
规则（maa/用户 2026-09-15）：食费一律篮子推算进公式（各城同一把尺）；官方统计（大阪 家計調査 単身 是全国/地方块，没有市表）留作「官方参考」不进公式；
「全省人均消费 × 食品占比」这种省级推算一律不用。
统一用量（单身一个月）：大米 5 kg、面粉 2 kg（或挂面 2 kg）、鸡蛋 30、牛奶 10 L、食用油 1 L、蔬菜 15 kg（土豆/西红柿/白菜各 5）、肉 4 kg（鸡肉 2 牛肉 2；没取到牛肉先用羊肉顶）、苹果 6 kg、馕 15 个、外食 22 顿、可乐 2 L、啤酒 6 罐；没有馕/面粉的城市用面包 2 kg。
"""
import json, sys, os, datetime
# 统一用量（单身一个月；maa/用户 2026-09-15）。篮子里没有的项跳过并在 note 里列出；面包只在没有馕/面粉时顶上
QTY={'rice5kg':1,'flour1kg':2,'noodles1kg':0,'eggs10':3,'milk1l':10,'oil1l':1,'potato1kg':5,'tomato1kg':5,'cabbage1kg':5,'chicken1kg':2,'beef1kg':2,'mutton1kg':0,'apple1kg':6,'naan1':15,'curry_rice':22,'cola1l':2,'beer6':1,'bread1kg':2}
ZH={'rice5kg':'大米 5 kg','flour1kg':'面粉 1 kg','noodles1kg':'挂面 1 kg','eggs10':'鸡蛋 10 个','milk1l':'牛奶 1 L','oil1l':'食用油 1 L','potato1kg':'土豆 1 kg','tomato1kg':'西红柿 1 kg','cabbage1kg':'白菜 1 kg',
    'chicken1kg':'鸡肉 1 kg','beef1kg':'牛肉 1 kg','mutton1kg':'羊肉 1 kg','apple1kg':'苹果 1 kg','naan1':'馕 1 个','curry_rice':'一顿快餐','cola1l':'可乐 1 L','beer6':'啤酒 6 罐','bread1kg':'面包 1 kg'}
CITY=sys.argv[1]; FILE={'buon_ma_thuot':'buonmathuot'}.get(CITY,CITY)
p=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data','cities',f'{FILE}.json'); d=json.load(open(p,encoding='utf-8'))
b=d.get('basket',{}); parts=[]; total=0; missing=[]
qty=dict(QTY)
if b.get('flour1kg',{}).get('value') is None and b.get('noodles1kg',{}).get('value') is not None: qty['noodles1kg']=2        # 面粉/挂面二选一
if b.get('naan1',{}).get('value') is not None or b.get('flour1kg',{}).get('value') is not None: qty['bread1kg']=0            # 有馕/面粉就不算面包
if b.get('beef1kg',{}).get('value') is None and b.get('mutton1kg',{}).get('value') is not None: qty['mutton1kg']=2; qty['beef1kg']=0   # 用户 09-16：肉改牛肉（国外羊肉少）；还没取到牛肉的城先用羊肉顶
if b.get('oil1l',{}).get('value') is None and b.get('oil5l',{}).get('value') is not None: qty['oil5l']=0.2; ZH['oil5l']='食用油 5 L 桶'
if b.get('curry_rice',{}).get('value') is None and b.get('bigmac_set',{}).get('value') is not None: qty['curry_rice']=0; qty['bigmac_set']=22; ZH['bigmac_set']='一顿快餐（用巨无霸套餐价顶）'   # 没有「一顿快餐」的城市（大阪）用巨无霸套餐当一顿外食
for k,q in qty.items():
    if not q: continue
    v=b.get(k,{}).get('value')
    if v is None: missing.append(ZH.get(k,k)); continue
    total+=v*q; parts.append(f"{ZH[k]} {v:g}×{q:g}")
old_food=d['living_official'].get('food') or {}
if old_food.get('confidence')=='official' and old_food.get('value') is not None and '篮子' not in (old_food.get('label') or ''):
    # 官方统计只作参考线（maa 09-15：各城同一把尺，食费一律篮子推算进公式）
    ref=dict(old_food); ref['label']='食费官方参考（不进公式）：'+(ref.get('label') or '统计平均'); d['living_official']['food_official_ref']=ref
cur=d.get('currency','')
unit={'CNY':'元/月','VND':'越南盾/月','JPY':'日元/月'}.get(cur,cur+'/月')
d['living_official']['food']={"label":"基础食材月费（按平台实价推算）","value":round(total),"unit":unit,"confidence":"estimated","n":None,
  "source_url":None,"source_name":"本页各项食材的平台实价 × 项目统一用量（单身）","source_short":"按各项实价推算","fetched_at":datetime.date.today().isoformat(),
  "how":"上面各项食材的平台现价 × 项目统一用量："+"、".join(parts)+("；"+"、".join(missing)+" 还没有价，没算进去。" if missing else "。"),
  "note":"= "+" + ".join(parts)+f" = {round(total):,}。用量是项目统一假定（见 cost/data/README.md），价是篮子里当地人实际在用的平台现价；不是统计均值。"+(f" 缺 {', '.join(missing)}，没算进去。" if missing else "")}
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f"{CITY}: 基础食材月费 {round(total):,} {unit}（{len(parts)} 项）"+(f" 缺 {missing}" if missing else ''))

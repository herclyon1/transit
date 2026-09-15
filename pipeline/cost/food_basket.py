#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
饮食费两态（用户 2026-09-16 定，细则见 cost/data/FOOD-MODEL-DRAFT.md）：
  在岗（进公式，living_official.food）      = 食材 0，全外食：一周五天有班、周末休 → 工作日 1 顿外食 + 1 顿员工餐，周末 2 顿外食；
                                             一顿 = 当地最便宜的单人正餐（日本 = 松のや ロースかつ定食，用户券后 630；乌鲁木齐 = 美团特价团拌面）；
                                             可乐 2 L/月；茶 0；啤酒 0。员工餐是个人参数（personal.json）。
  脱产 / 过渡期（只展示，living_official.food_transition） = 全自炊：厚労省 令和5年 国民健康・栄養調査 第5表 男性 20–29 岁实测克数 × 当地平台现价；
                                             调料五件按月耗量；茶 45 L/月（瓶装；瓶装折最低时薪的小时数超过日本同口径 2 倍就退回自泡）；可乐 4 L；啤酒 0。
  python3 pipeline/cost/food_basket.py osaka
官方统计（家計調査 等）留在 living_official.food_official_ref 只作参考。
"""
import json, sys, os, datetime, math
HERE=os.path.dirname(os.path.abspath(__file__)); DATA=os.path.join(HERE,'..','..','cost','data')
CITY=sys.argv[1]; FILE={'buon_ma_thuot':'buonmathuot'}.get(CITY,CITY)
p=os.path.join(DATA,'cities',f'{FILE}.json'); d=json.load(open(p,encoding='utf-8')); b=d.get('basket',{})
P=json.load(open(os.path.join(DATA,'personal.json'),encoding='utf-8')); PC={**P.get('default',{}),**P.get(FILE,{})}
cur=d.get('currency',''); unit={'CNY':'元/月','VND':'越南盾/月','JPY':'日元/月'}.get(cur,cur+'/月')
DAYS=30.4
# —— 脱产：NHNS 令和5年 第5表 男性 20–29 歳 平均 g/日（e-Stat statInfId 000040275961）→ 每月购买量 ——
G={'米_炊飯後':370.3,'パン':25.4,'めん_ゆで':49.7,'パスタ_ゆで':28.7,'いも':55.0,'野菜':230.9,'生果':23.8,'鶏肉':55.3,'豚肉':58.2,'ハムソーセージ':17.6,'牛肉':19.2,
   '魚介':43.8,'豆腐類':45.2,'卵':44.3,'牛乳':52.5,'発酵乳':30.4,'植物性油脂':13.0,'しょうゆ':12.4,'味噌':8.8,'塩':1.6,'砂糖':5.0,'マヨネーズ':3.3}
Q={  # 键: (月用量, 用量单位说明)
 'rice5kg':   (G['米_炊飯後']/2.2*DAYS/1000/5, '米 370 g/日（炊饭后）÷2.2 = 生米 5.1 kg'),
 'bread1kg':  (G['パン']*DAYS/1000, 'パン 25 g/日'),
 'flour1kg':  ((G['めん_ゆで']+G['パスタ_ゆで'])*0.4*DAYS/1000, 'めん・パスタ ゆで 78 g/日 ×0.4 = 干面/面粉'),
 'potato1kg': (G['いも']*DAYS/1000, 'いも 55 g/日'),
 'cabbage1kg':(G['野菜']*0.5*DAYS/1000, '野菜 231 g/日 的 50%（はくさい・キャベツ・淡色）'),
 'onion1kg':  (G['野菜']*0.35*DAYS/1000, '野菜的 35%（たまねぎ・根菜）'),
 'tomato1kg': (G['野菜']*0.15*DAYS/1000, '野菜的 15%（トマト・緑黄色）'),
 'apple1kg':  (G['生果']*DAYS/1000, '生果 24 g/日'),
 'chicken1kg':(G['鶏肉']*DAYS/1000, '鶏肉 55 g/日'),
 'pork1kg':   ((G['豚肉']+G['ハムソーセージ'])*DAYS/1000, '豚肉 58 + ハム・ソーセージ 18 g/日'),
 'beef1kg':   (G['牛肉']*DAYS/1000, '牛肉 19 g/日'),
 'fish1kg':   (G['魚介']*DAYS/1000, '魚介 44 g/日'),
 'tofu1kg':   (G['豆腐類']*DAYS/1000, '豆腐 34 + 納豆 5 + 油揚げ 6 g/日'),
 'eggs10':    (G['卵']*DAYS/60/10, '卵 44 g/日 ÷60 g = 22 个'),
 'milk1l':    ((G['牛乳']+G['発酵乳'])*DAYS/1000/1.03, '牛乳 52 + 発酵乳 30 g/日'),
 'oil1l':     (G['植物性油脂']*DAYS/1000/0.92, '植物性油脂 13 g/日'),
 'soy1l':     (G['しょうゆ']*DAYS/1000/1.15, 'しょうゆ 12.4 g/日'),
 'miso1kg':   (G['味噌']*DAYS/1000, '味噌 8.8 g/日'),
 'salt1kg':   (G['塩']*DAYS/1000, '塩 1.6 g/日'),
 'sugar1kg':  (G['砂糖']*DAYS/1000, '砂糖 5 g/日'),
 'mayo1kg':   (G['マヨネーズ']*DAYS/1000, 'マヨネーズ 3.3 g/日'),
}
# 各城替换（同热量同蛋白的替换，不是当地人真这么吃）：键 → (替换键, 说明)
SUB={'urumqi':{'pork1kg':('mutton1kg','乌鲁木齐羊肉是主肉，猪肉份额换羊肉'),'miso1kg':('vinegar1l','味噌换陈醋/香醋'),'mayo1kg':('cooking_wine1l','蛋黄酱换料酒')},
     'buonmathuot':{'pork1kg':('pork1kg',''),'miso1kg':('fish_sauce1l','味噌换鱼露'),'mayo1kg':('cooking_wine1l','蛋黄酱换料酒')}}.get(FILE,{})
ZH={'rice5kg':'大米 5 kg','bread1kg':'面包 1 kg','flour1kg':'面粉/面条 1 kg','potato1kg':'土豆 1 kg','cabbage1kg':'白菜 1 kg','onion1kg':'洋葱 1 kg','tomato1kg':'西红柿 1 kg','apple1kg':'苹果 1 kg',
    'chicken1kg':'鸡肉 1 kg','pork1kg':'猪肉 1 kg','mutton1kg':'羊肉 1 kg','beef1kg':'牛肉 1 kg','fish1kg':'鱼 1 kg','tofu1kg':'豆腐 1 kg','eggs10':'鸡蛋 10 个','milk1l':'牛奶 1 L','oil1l':'食用油 1 L',
    'soy1l':'酱油 1 L','miso1kg':'味噌 1 kg','vinegar1l':'醋 1 L','fish_sauce1l':'鱼露 1 L','salt1kg':'盐 1 kg','sugar1kg':'糖 1 kg','mayo1kg':'蛋黄酱 1 kg','cooking_wine1l':'料酒 1 L',
    'tea2l':'瓶装茶 2 L','tea_leaf1kg':'茶叶 1 kg','mugicha':'麦茶パック 1 袋','cola1l':'可乐 1 L','curry_rice':'一顿正餐','set_meal':'一顿正餐'}
parts=[]; total=0; missing=[]; subs=[]
for k,(q,why) in Q.items():
    key=k
    if k in SUB and b.get(k,{}).get('value') is None:
        key,why2=SUB[k]; subs.append(f'{ZH[k]}→{ZH.get(key,key)}（{why2}）')
    v=b.get(key,{}).get('value')
    if v is None: missing.append(ZH.get(key,key)); continue
    total+=v*q; parts.append(f"{ZH.get(key,key)} {v:g}×{q:.2f}")
# 茶：瓶装 45 L/月；瓶装折最低时薪小时数 > 日本同口径 × 2 就退回自泡（用户 09-16）
TEA_L=PC.get('tea_l_per_month',45); minw=(d.get('wage_ref',{}).get('min_official') or {}).get('value'); tea_note=''
JP_TEA_H=P.get('_ref',{}).get('japan_bottled_tea_hours')   # 日本同口径的小时数，由大阪先算出写回 personal.json
tea_cost=None
bottle_per_l=(b['tea2l']['value']/2 if b.get('tea2l',{}).get('value') is not None else b.get('tea_bottle1l',{}).get('value'))   # 大阪 2 L 装 / 乌鲁木齐按 L
if bottle_per_l is not None:
    bottled=TEA_L*bottle_per_l; hours=bottled/minw if minw else None
    if FILE=='osaka': P.setdefault('_ref',{})['japan_bottled_tea_hours']=round(hours,2); json.dump(P,open(os.path.join(DATA,'personal.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1); JP_TEA_H=hours
    if JP_TEA_H and hours and hours>2*JP_TEA_H and (b.get('mugicha',{}).get('value') is not None or b.get('tea_leaf1kg',{}).get('value') is not None):
        if b.get('mugicha',{}).get('value') is not None: tea_cost=TEA_L*b['mugicha']['value']; tea_note=f'瓶装茶 {TEA_L} L = {bottled:,.0f}，折最低时薪 {hours:.1f} h，超过日本同口径（{JP_TEA_H:.1f} h）的 2 倍 → 退回自泡麦茶 {TEA_L} 袋'
        else: tea_cost=TEA_L/100*b['tea_leaf1kg']['value']; tea_note=f'瓶装茶折最低时薪 {hours:.1f} h 超阈值 → 退回茶叶（1 g 泡 100 ml，{TEA_L*10:g} g）'
    else: tea_cost=bottled; tea_note=f'瓶装茶 2 L × {TEA_L/2:g} 瓶（折最低时薪 {hours:.1f} h，日本同口径 {JP_TEA_H:.1f} h 的 2 倍以内）' if hours and JP_TEA_H else f'瓶装茶 2 L × {TEA_L/2:g} 瓶'
elif b.get('tea_leaf1kg',{}).get('value') is not None:
    tea_cost=TEA_L/100*b['tea_leaf1kg']['value']; tea_note=f'没有瓶装茶价，茶叶 1 g 泡 100 ml → {TEA_L*10:g} g'
if tea_cost is not None: total+=tea_cost; parts.append(f'茶 {TEA_L} L {tea_cost:,.0f}')
else: missing.append('茶')
cola_t=PC.get('cola_l_transition',4)
if b.get('cola1l',{}).get('value') is not None: total+=b['cola1l']['value']*cola_t; parts.append(f"可乐 1 L {b['cola1l']['value']:g}×{cola_t}")
else: missing.append('可乐')
today=datetime.date.today().isoformat()
d['living_official']['food_transition']={"label":"过渡期饮食费（脱产自炊，不进公式）","value":round(total),"unit":unit,"confidence":"estimated","n":None,
  "source_url":"https://www.e-stat.go.jp/stat-search/files?layout=dataset&toukei=00450171&tstat=000001041744&tclass1=000001228532",
  "source_name":"厚生労働省 令和5年 国民健康・栄養調査 第5表 食品群別摂取量（男性 20–29 歳）× 本页篮子平台现价","source_short":"NHNS 用量 × 平台现价","fetched_at":today,
  "how":"全自炊、不外食：厚労省 令和5年 国民健康・栄養調査 男性 20–29 岁每天吃进去的克数折成每月购买量，乘本页篮子的平台现价："+"、".join(parts)+"。"+(tea_note+'。' if tea_note else '')
        +(f"替换：{'；'.join(subs)}——同热量同蛋白的替换，不是当地人真这么吃。" if subs else '')+(f"缺 {'、'.join(missing)}，没算进去。" if missing else '')+"啤酒 0。",
  "note":"用量：米 370 g/日÷2.2、パン 25、めん 78×0.4、いも 55、野菜 231（白菜类 50%/洋葱根菜 35%/番茄 15%）、生果 24、鶏 55、豚+加工 76、牛 19、魚 44、豆腐類 45、卵 44、乳 83、油 13、しょうゆ 12.4、味噌 8.8、塩 1.6、砂糖 5、マヨ 3.3 g/日；茶 45 L、可乐 4 L 是用户习惯。"}
# —— 在岗：全外食，5 天班表 ——
meal=b.get('set_meal') or b.get('curry_rice') or {}
mv=PC.get('meal_price_override') or meal.get('value'); staff=PC.get('staff_meal',0); cola_w=PC.get('cola_l_work',2)
W=22; F=DAYS-W   # 工作日有班 22 天：1 外食 + 1 员工餐；周末 8.4 天：2 外食
out=W*1+F*2; staff_n=W
work_total=(out*mv if mv else 0)+staff_n*staff+(b.get('cola1l',{}).get('value') or 0)*cola_w
d['living_official']['food']={"label":"在岗饮食费（全外食，一周五天有班）","value":round(work_total),"unit":unit,"confidence":"estimated","n":None,
  "source_url":meal.get('source_url'),"source_name":f"一顿正餐 = {meal.get('label','')}（{meal.get('source_short','')}）× 班表；员工餐、券后价是个人参数（cost/data/personal.json）","source_short":"5 天班表","fetched_at":today,
  "how":f"食材 0、全外食。一周五天有班、周末休：工作日 1 顿外食 + 1 顿员工餐，周末 2 顿外食 → 外食 {out:.1f} 顿 × {mv:g}"+(f"（{PC.get('meal_price_note','')}）" if PC.get('meal_price_note') else '')
        +f" + 员工餐 {staff_n} 顿 × {staff:g} + 可乐 {cola_w} L × {b.get('cola1l',{}).get('value',0):g}。茶 0、啤酒 0。",
  "note":"用户 09-16：法律只限工时不限班次，一律按一周五天有班；周末有班那天两顿员工餐（本表按周末休）。"}
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(f"{CITY}: 在岗饮食费 {round(work_total):,} {unit}（外食 {out:.1f} 顿×{mv} + 员工餐 {staff_n}×{staff}）；过渡期饮食费 {round(total):,}（{len(parts)} 项）"+(f" 缺 {missing}" if missing else ''))

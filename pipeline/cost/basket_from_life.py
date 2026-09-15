#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw/osaka/<date>/life.jsonl（ライフネットスーパー 搜索页第一屏 関連順，用户登录后从 Flutter 语义树读出）→ osaka.json basket。
   python3 pipeline/cost/basket_from_life.py [--date 20260916]
   用户 2026-09-16：大阪只认ライフ（他只在ライフ买），イオン作废。口径同 basket_from_grab.py：第一屏前 10 → 剔掉不是同一种东西的 →
   按规格折到篮子单位 → 去掉离中位 2 倍以外的 → 取中位。同一商品不同包装（若どりもも 560/280/1120 g）算一条。
   量り売り肉：用页面标的「100g ¥本体」×1.08 折 kg。按个/切块卖的蔬果：ライフ也不标重量，折 kg 用 ＪＡ全農広島 出荷規格表
   （はくさい M 玉 2.0–2.5 kg、ばれいしょ L 玉 110–170 g、トマト L 玉 4 kg/24 個）和产地玉数（りんご），how 里写明出处。"""
import json, re, sys, os, statistics, datetime, subprocess
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
TAX=1.08
# 键：(关键词, 篮子单位, 折算方式, 同类剔除正则, label, 备注)
KEYS={
 'rice5kg':   ('米 5kg','円/5kg','pack5kg',r'もち米|無洗米.*増量',"大米 5kg",''),
 'bread1kg':  ('食パン','円/kg','loaf',r'3枚|サンドイッチ用|12枚',"面包 1kg（食パン 1 斤折算）",'食パン 4–10 枚装 = 1 斤，JAS 1 斤 ≥340 g，按 340 g 折'),
 'flour1kg':  ('薄力粉','円/kg','g',r'クッキングフラワー|パン専用|強力',"面粉 1kg（薄力粉）",''),
 'eggs10':    ('卵','円/10 個','eggs',r'ヨード|平飼い|ゆでたまご|ウズラ|茜美人|グルメ',"鸡蛋 10 个",''),
 'milk1l':    ('牛乳','円/L','ml',r'低脂肪|200ml',"牛奶 1L",''),
 'oil1l':     ('サラダ油','円/L','oil',r'こめ油|MCT|アマニ|えごま|カメリナ|オリーブ',"食用油 1L（サラダ油/キャノーラ）",''),
 'potato1kg': ('じゃがいも','円/kg','piece',r'ポテトサラダ|ポテトチップス|1袋',"土豆 1kg",'1 個 = ＪＡ全農広島 出荷規格 ばれいしょ L 玉（110–170 g）取 150 g；「1袋」不标个数不用'),
 'tomato1kg': ('トマト','円/kg','piece',r'ミニトマト|パック|袋|カットトマト|きゅうり|高リコピン|王様',"西红柿 1kg",'1 玉 = ＪＡ全農広島 出荷規格 トマト L 玉（4 kg 箱 24 個）≈167 g'),
 'cabbage1kg':('はくさい','円/kg','piece',r'キャベツ|ざく切り|ミックス|小松菜|ほうれん草|にら|鍋|豆苗',"白菜 1kg（はくさい）",'1/4 切・1/2 切 = ＪＡ全農広島 出荷規格 はくさい M 玉（2.0–2.5 kg）的 1/4 = 600 g、1/2 = 1,200 g'),
 'onion1kg':  ('たまねぎ','円/kg','piece',r'にんじん|ばれいしょ|みじん切り|ペースト|ドレッシング',"洋葱 1kg",'ライフ只标个数：北海道産 1 玉按 ホクレン『野菜標準全道統一規格』L 玉 190–250 g 取中值 220 g（二手转引：北のやさい便 2025-12-03，原 PDF 未找到）；淡路島産 L 偏大按 250 g'),
 'apple1kg':  ('りんご','円/kg','piece',r'ml|ジュース|ぶどう|コロロ|パインアップル|アップルサラダ',"苹果 1kg",'Mサイズ 1 玉按 青森 大湯ファーム「りんごサイズ比較」M = 320–360 g（10 kg 箱 32–36 個）取 340 g；大玉按 L = 360 g 起取 360 g——产地参考值，非 JA 規格'),
 'chicken1kg':('若どり','円/kg','per100',r'から揚げ|唐揚げ済|やきとり|惣菜',"鸡肉 1kg（腿/胸/翅/角切り都算）",'用户 09-16：各部位都收，只剔零食/惣菜'),
 'pork1kg':   ('豚こま','円/kg','per100',r'味付|惣菜',"猪肉 1kg（こま切れ）",''),
 'beef1kg':   ('牛肉','円/kg','per100',r'すきやき|焼肉|ステーキ|カルビ|バラ|チャプチェ|プルコギ|炒め|切りおとしとにんにく',"牛肉 1kg（こま切れ）",'只收普通 こま切れ/切り落とし；焼肉用/ステーキ/惣菜不算'),
 'fish1kg':   ('鮭','円/kg','slice',r'小切れ|純米酒|料理専用|淡麗|スモーク',"鱼 1kg（塩鮭/銀鮭切身）",'1 切按 80 g 折——平台标注（イオン同类商品「塩銀鮭 切身1切・80g」），ライフ本身不标'),
 'tofu1kg':   ('豆腐','円/kg','g',r'焼き豆腐|豆皿',"豆腐 1kg",''),
 'soy1l':     ('しょうゆ','円/L','ml',r'さしみ',"酱油 1L",''),
 'miso1kg':   ('味噌','円/kg','g',r'粉末|液みそ',"味噌 1kg",''),
 'salt1kg':   ('塩 1kg','円/kg','g',r'アイス|餅|スパゲッティ|糖|小麦粉',"盐 1kg",''),
 'sugar1kg':  ('塩 1kg','円/kg','g',r'アイス|餅|スパゲッティ|塩|小麦粉|三温糖|グラニュ',"糖 1kg（上白糖）",''),
 'mayo1kg':   ('マヨネーズ','円/kg','g',r'燻製|からし',"蛋黄酱 1kg",''),
 'tea2l':     ('爽健美茶|十六茶','円/2L','bottle2l',r'ケース|300ml|600ml|660ml',"瓶装茶 2L（爽健美茶/十六茶）",'用户脱产时当水喝的茶'),
 'mugicha':   ('麦茶','円/袋','teabag',r'ml|ケース|はとむぎ|有機|胡麻|黒豆|40g',"麦茶パック 1 袋（自泡 1 L）",'瓶装茶太贵时的退路'),
 'cola1l':    ('コカ・コーラ','円/L','ml',r'ゼロ|プラス|檸檬堂|350ml|700ml',"可乐 1L（1.5L 装折算）",''),
 'beer6':     ('ビール 350ml','円/6 罐','six',r'ケース|ヱビス|糖質|黒生|ホワイト',"啤酒 350ml×6",'只作展示，两态都不进公式'),
}
def unit_price(key,r):
    name=r['name']; p=r['price']; how=KEYS[key][2]
    if how=='per100':
        return (r['per100_base']*TAX*10,'100g 本体 %g 円'%r['per100_base']) if r.get('per100_base') else (None,'')
    if how=='pack5kg':
        return (p,'5kg') if '5kg' in name else (None,'')
    if how=='loaf':
        m=re.search(r'(\d+)枚',name)
        return (p/0.34,'1 斤 340 g') if m and 4<=int(m.group(1))<=10 else (None,'')
    if how=='g':
        m=re.search(r'(\d+(?:\.\d+)?)\s?(kg|g)(?:×|x|\b)',name)
        if not m: return None,''
        g=float(m.group(1))*(1000 if m.group(2)=='kg' else 1)
        n=re.search(r'[×x](\d+)',name)
        if n: g*=int(n.group(1))
        return p/g*1000, f'{g:g} g'
    if how=='ml':
        m=re.search(r'(\d+(?:\.\d+)?)\s?(ml|l|L)\b',name)
        if not m: return None,''
        ml=float(m.group(1))*(1 if m.group(2)=='ml' else 1000); return p/ml*1000, f'{ml:g} ml'
    if how=='oil':
        m=re.search(r'(\d+)g',name)
        if not m: return None,''
        l=float(m.group(1))/1000/0.92; return p/l, f'{m.group(1)} g ≈ {l:.2f} L'
    if how=='eggs':
        m=re.search(r'(\d+)\s?(?:コ|個)',name)
        return (p/int(m.group(1))*10,f'{m.group(1)} 個') if m else (None,'')
    if how=='piece':
        if key=='potato1kg' and re.search(r'1個|1コ',name): return p/0.15,'1 個 ≈150 g（JA L 玉）'
        if key=='tomato1kg' and '1玉' in name: return p/0.167,'1 玉 ≈167 g（JA L 玉）'
        if key=='cabbage1kg':
            if '1/4切' in name: return p/0.6,'1/4 切 ≈600 g（JA M 玉 2.0–2.5 kg）'
            if '1/2切' in name: return p/1.2,'1/2 切 ≈1,200 g'
        if key=='apple1kg':
            if 'Mサイズ1玉' in name: return p/0.34,'M 1 玉 ≈340 g（大湯ファーム M 320–360 g）'
            if '2玉入' in name: return p/0.72,'大玉 2 玉 ≈720 g（L 360 g 起）'
        if key=='onion1kg':
            m=re.search(r'【(\d+)コ】',name); n=int(m.group(1)) if m else (1 if re.search(r'1個|1コ',name) else 0)
            if not n: return None,''
            w=0.25 if '淡路' in name else 0.22
            return p/(n*w),f'{n} 玉 × {int(w*1000)} g（{"淡路 L" if "淡路" in name else "ホクレン L 玉 190–250 g 中值"}）'
        return None,''
    if how=='slice':
        m=re.search(r'(\d+)切',name)
        return (p/(int(m.group(1))*0.08),f'{m.group(1)} 切 × 80 g') if m else (None,'')
    if how=='bottle2l':
        return (p,'2 L') if re.search(r'2L\b',name) and 'ケース' not in name else (None,'')
    if how=='teabag':
        m=re.search(r'(\d+)袋',name)
        return (p/int(m.group(1)),f'{m.group(1)} 袋') if m else (None,'')
    if how=='six':
        return (p,'6 缶') if '6缶' in name else (None,'')
    return None,''
STAT={'onion1kg':('たまねぎ 1kg',497),'flour1kg':('小麦粉 1袋·1kg',334),'oil1l':('食用油 1本·900g',412),'potato1kg':('じゃがいも 1kg',651),'tomato1kg':('トマト 1kg',771),'cabbage1kg':('はくさい 1kg',193),
      'chicken1kg':('鶏肉 100g',1640),'pork1kg':('豚肉(輸入品，ロース) 100g',1760),'beef1kg':('牛肉(輸入品) 100g',3540),'apple1kg':('りんご 1kg',834),'eggs10':('鶏卵 1パック·10個',319),'milk1l':('牛乳 1本·1,000mL',274),'rice5kg':('うるち米 コシヒカリ以外 5kg',4916),'bread1kg':('食パン 1kg',581)}
STAT_SRC=('总务省统计局 小売物価統計調査（動向編）2026 年 2 月 第１表 大阪市','https://www.e-stat.go.jp/stat-search/files?layout=dataset&query=5g&stat_infid=000040427931')
def main():
    date=(sys.argv[sys.argv.index('--date')+1] if '--date' in sys.argv else sorted(x for x in os.listdir(os.path.join(ROOT,'raw','osaka')) if x.isdigit())[-1])
    rows=[json.loads(l) for l in open(os.path.join(ROOT,'raw','osaka',date,'life.jsonl'),encoding='utf-8')]
    cf=os.path.join(ROOT,'cities','osaka.json'); d=json.load(open(cf,encoding='utf-8')); b=d['basket']; done=[]
    for k in ('mutton1kg',): b.pop(k,None)
    for key,(kw,unit,how,excl,label,note) in KEYS.items():
        rs=[]; seen=set()
        for k1 in kw.split('|'):
            for r in sorted([r for r in rows if r['keyword']==k1],key=lambda r:r['rank'])[:(20 if key=='mugicha' else 10)]:   # 麦茶パック排在瓶装后面，看到第 20 条
                if r['name'] in seen: continue
                seen.add(r['name']); rs.append(r)
        if not rs: continue
        dropped=[r['name'][:18] for r in rs if re.search(excl,r['name'])]; keep0=[r for r in rs if not re.search(excl,r['name'])]
        priced=[]
        for r in keep0:
            u,sp=unit_price(key,r)
            if u: priced.append((r,u,sp))
        if not priced: b.pop(key,None); print(key,'剔完一条不剩，拿掉'); continue
        uniq=[]; seenk=set()
        for x in priced:   # 同一商品不同包装算一条
            kk=(re.sub(r'\d+g目安|\d+\s?g|\d+ml|\d+l\b|\d+kg|\d+枚|\d+切|\d+コ|\d+個|\d+玉|【.*?】|\(.*?\)','',x[0]['name']).strip(),round(x[1]))
            if kk in seenk: continue
            seenk.add(kk); uniq.append(x)
        med=statistics.median([u for _,u,_ in uniq]); kept=[x for x in uniq if med/2<=x[1]<=med*2] or uniq
        val=round(statistics.median([u for _,u,_ in kept]))
        b[key]={'value':val,'unit':'日元','label':label,'source_url':'https://www.life-netsuper.jp/product_search_results?keyword='+kw.split('|')[0],
                'source_name':f"ライフネットスーパー（用户账号，大阪市内配送店）搜索“{kw.replace('|','」「')}” 関連順第一屏前 {len(rs)}",
                'source_short':'ライフネットスーパー','fetched_at':rs[0]['fetched_at'],'confidence':'listing','n':len(kept),
                'how':f'ライフネットスーパー搜「{kw.replace("|","」「")}」関連順第一屏前 {len(rs)} 条，剔掉不是同一种东西的 {len(dropped)} 条'+(f'（{"、".join(dropped)}）' if dropped else '')+f'，同一商品不同包装算一条，其余折到 {unit}，去掉离中位 2 倍以外的，取中位（n={len(kept)}）。'+(note+'。' if note else ''),
                'items':[{'name':r['name'][:60],'price':r['price'],'unit':'日元','note':f'{sp} → {u:,.0f} {unit}'+('（広告の品）' if r.get('flag') else '')} for r,u,sp in uniq],
                'items_label':f'看 {len(uniq)} 款',
                'note':'；'.join(f"{r['rank']}.{r['name'][:30]} {r['price']:g} 円 {sp} → {u:.0f} {unit}" for r,u,sp in kept)}
        if key in STAT: b[key]['compare']={'label':f'统计对照（{STAT[key][0]}，大阪市 2026-02，折 {unit}）','value':STAT[key][1],'unit':'日元','n':None,'source_url':STAT_SRC[1],'source_name':STAT_SRC[0]}
        done.append(f'{label} {val:,}（n={len(kept)}）')
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('篮子写入：'+'；'.join(done))
    subprocess.run([sys.executable,os.path.join(os.path.dirname(os.path.abspath(__file__)),'food_basket.py'),'osaka'])
if __name__=='__main__': main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw/osaka/<date>/aeon.jsonl → osaka.json basket 八项（面粉/油/土豆/西红柿/白菜/鸡腿/猪肉(顶羊肉)/苹果），口径和 basket_from_grab.py 一样：
   おすすめ順第一屏 → 剔掉不是同一种东西的（EXCL）→ 按规格折到篮子单位 → 去掉离中位 2 倍以外的 → 取中位。
   python3 pipeline/cost/basket_from_aeon.py [--date 20260916]
   蔬果按「1個/1/4カット」卖、平台不标重量：折 kg 用 WEIGHT 里的假定重量（日本超市常见规格），how 里写明是假定，
   并把总务省 小売物価統計 2026-02 大阪市 每 kg 统计价写进 compare 做对照。鸡肉各部位都收；第二种肉 = 牛肉 普通小間切れ/切り落とし/ミンチ（用户 09-16）。"""
import json, re, sys, os, statistics, datetime, subprocess
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
# 键：(关键词, 篮子单位, 折算方式, 同类剔除正则, label)
KEYS={'flour1kg':('薄力粉','円/kg','g',r'ライスフラワー|お米の粉|天ぷら粉|パン粉|ホットケーキ','面粉 1kg（薄力粉）'),
      'oil1l':('キャノーラ油','円/L','oil',r'オリーブ|ケース販売|天かす|シーズニング|ごま油','食用油 1L（サラダ油/キャノーラ）'),
      'potato1kg':('じゃがいも','円/kg','piece',r'うらごし|ポテト|カレー|ハッシュ|カット|ジャーマン|冷凍','土豆 1kg'),
      'tomato1kg':('トマト','円/kg','piece',r'ミニトマト|カットトマト|ソース|焼|ライス|トマト \d+g','西红柿 1kg'),
      'cabbage1kg':('はくさい','円/kg','piece',r'キムチ|煮|炒め|鍋|の素|白菜 \d+g|クリーム','白菜 1kg（はくさい）'),
      # 用户 09-16：鸡肉各部位都收（腿/胸/翅/柳/碎肉，品牌鸡也算），只剔零食/惣菜/调味料/鸭
      'chicken1kg':('若どり|鶏肉','円/kg','per100',r'から揚げ|からあげ|唐揚|やきとり|惣菜|ソース|の素|スープ|サラダチキン|鴨|ダック|HomeCooking|缶|レトルト','鸡肉 1kg（腿/胸/翅/碎肉都算）'),
      # 用户 09-16：第二种肉改牛肉——只收 国産/輸入 的普通 小間切れ/切り落とし/ミンチ，和牛/ステーキ/焼肉用 不算
      'beef1kg':('牛肉|牛こま','円/kg','per100',r'和牛|黒毛|ステーキ|ロースト|かたまり|牛丼の具|チャプチェ|の素|ソース|焼肉用|すき焼き|しゃぶしゃぶ|スライス','牛肉 1kg（小間切れ/切り落とし/ミンチ）'),
      'apple1kg':('りんご','円/kg','piece',r'カットリンゴ|すりおろし|すりりんご|ml|ジュース|ひとくち|チューハイ','苹果 1kg')}
INCL={'beef1kg':r'小間切れ|切りおとし|切り落とし|こま切れ|ミンチ'}   # 有 INCL 的键：只收匹配的
# 假定重量（g）：平台按个/切块卖、不标重量。日本超市常见规格：じゃがいも M 玉 ≈150、トマト M 玉 ≈180、はくさい 1 棵 ≈2.4 kg（1/4 ≈600、1/6 ≈400）、りんご ≈300
WEIGHT={'potato1kg':{r'1個':150,r'2個入':300},'tomato1kg':{r'1個':180},'cabbage1kg':{r'1／4カット':600,r'1／6カット':400},'apple1kg':{r'1個':300}}
STAT={'beef1kg':('牛肉(輸入品) 100g',3540),'flour1kg':('小麦粉 1袋·1kg',334),'oil1l':('食用油 1本·900g',412),'potato1kg':('じゃがいも 1kg',651),'tomato1kg':('トマト 1kg',771),'cabbage1kg':('はくさい 1kg',193),'chicken1kg':('鶏肉 100g',1640),'apple1kg':('りんご 1kg',834)}
STAT_SRC=('总务省统计局 小売物価統計調査（動向編）2026 年 2 月 第１表 大阪市','https://www.e-stat.go.jp/stat-search/files?layout=dataset&query=5g&stat_infid=000040427931')
def unit_price(key,r):
    name=r['name']; p=r['price']; how=KEYS[key][2]
    if how=='per100':
        m=re.search(r'100gあたり（本体）(\d+)円',name); return (float(m.group(1))*1.08*10, '100g 本体 '+m.group(1)+' 円') if m else (None,'')
    if how=='g':
        m=re.search(r'(\d+(?:\.\d+)?)\s?(kg|g)\b',name)
        if not m: return None,''
        g=float(m.group(1))*(1000 if m.group(2)=='kg' else 1); return p/g*1000, f'{m.group(0)}'
    if how=='oil':
        m=re.search(r'(\d+)\s?g\b',name)
        if not m: return None,''
        l=float(m.group(1))/1000/0.92; return p/l, f'{m.group(1)} g ≈ {l:.2f} L'   # 植物油密度 ≈0.92
    if how=='piece':
        for pat,w in WEIGHT.get(key,{}).items():
            if re.search(pat,name): return p/w*1000, f'按 {pat.replace(chr(92),"")} ≈{w} g 假定'
        return None,''
def main():
    date=(sys.argv[sys.argv.index('--date')+1] if '--date' in sys.argv else sorted(x for x in os.listdir(os.path.join(ROOT,'raw','osaka')) if x.isdigit())[-1])
    rows=[json.loads(l) for l in open(os.path.join(ROOT,'raw','osaka',date,'aeon.jsonl'),encoding='utf-8')]
    cf=os.path.join(ROOT,'cities','osaka.json'); d=json.load(open(cf,encoding='utf-8')); b=d['basket']; done=[]
    b.pop('mutton1kg',None)   # 09-16 起第二种肉是牛肉，猪肉替身作废
    for key,(kw,unit,how,excl,label) in KEYS.items():
        rs=[]; seen_name=set()
        for k1 in kw.split('|'):   # 几个关键词合成一组；同一商品被几个词搜到只算一次
            for r in sorted([r for r in rows if r['keyword']==k1],key=lambda r:r['rank'])[:10]:
                if r['name'] in seen_name: continue
                seen_name.add(r['name']); rs.append(r)
        if not rs: continue
        kwz=kw.replace('|','」「')
        bad=lambda r: bool(re.search(excl,r['name'])) or (key in INCL and not re.search(INCL[key],r['name']))
        dropped=[r['name'][:18] for r in rs if bad(r)]; keep0=[r for r in rs if not bad(r)]
        priced=[]
        for r in keep0:
            u,sp=unit_price(key,r)
            if u: priced.append((r,u,sp))
        if not priced: b.pop(key,None); print(key,'剔完一条不剩，拿掉'); continue
        # 同一商品不同包装（若どりもも 1枚/2枚/3枚 都是 118 円/100g）算一条
        seen=set(); uniq=[]
        for x in priced:
            k=(re.sub(r'\d+枚・|\d+\s?g|\d+個|\d+パック|\d+kg','',x[0]['name']).strip(),round(x[1]))   # 同一商品不同包装算一条：去掉包装数字后同名 + 同单价
            if k in seen: continue
            seen.add(k); uniq.append(x)
        med=statistics.median([u for _,u,_ in uniq]); kept=[x for x in uniq if med/2<=x[1]<=med*2] or uniq
        val=round(statistics.median([u for _,u,_ in kept]))
        assumed=how=='piece'
        b[key]={'value':val,'unit':'日元','label':label,'source_url':rs[0]['url'],'source_name':f"イオンネットスーパー 野田阪神店（配送 大阪市北区梅田，店舗見学模式不登录可看，税込） 搜索“{kwz}” おすすめ順前 {len(rs)}",
                'source_short':'イオンネットスーパー','fetched_at':rs[0]['fetched_at'],'confidence':'listing','n':len(kept),
                'how':f'イオンネットスーパー搜「{kwz}」おすすめ順前 {len(rs)} 条，剔掉不是同一种东西的 {len(dropped)} 条'+(f'（{"、".join(dropped)}）' if dropped else '')+f'，同一商品不同包装算一条，其余折到 {unit}，去掉离中位 2 倍以外的，取中位（n={len(kept)}）。'
                      +('平台按个/切块卖不标重量，折 kg 用的是假定重量（'+'、'.join(f'{k.replace(chr(92),"")} ≈{v} g' for k,v in WEIGHT[key].items())+'），不是平台标注；总务省大阪市每 kg 统计价放对照。' if assumed else '')
                      +('只收国産/輸入的普通小間切れ・切り落とし・ミンチ，和牛/ステーキ/焼肉用不算。' if key=='beef1kg' else '')+('各部位都收（用户 09-16），只剔零食/惣菜/调味料/鸭。' if key=='chicken1kg' else ''),
                'items':[{'name':r['name'][:60],'price':r['price'],'unit':'日元','note':f'{sp} → {u:,.0f} {unit}'} for r,u,sp in uniq],
                'items_label':f'看 {len(uniq)} 款',
                'compare':{'label':f'统计对照（{STAT[key][0]}，大阪市 2026-02，折 {unit}）','value':STAT[key][1],'unit':'日元','n':None,'source_url':STAT_SRC[1],'source_name':STAT_SRC[0]},
                'note':'；'.join(f"{r['rank']}.{r['name'][:30]} {r['price']:g} 円 {sp} → {u:.0f} {unit}" for r,u,sp in kept)}
        done.append(f'{label} {val:,}（n={len(kept)}）')
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('篮子写入：'+'；'.join(done))
    subprocess.run([sys.executable,os.path.join(os.path.dirname(os.path.abspath(__file__)),'food_basket.py'),'osaka'])
if __name__=='__main__': main()

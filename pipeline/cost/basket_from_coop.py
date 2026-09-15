#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""raw/buon_ma_thuot/<date>/coop.jsonl（Co.op Online 定位 Co.opmart Buôn Ma Thuột，默认排序前 10）→ buonmathuot.json basket。
   python3 pipeline/cost/basket_from_coop.py [--date 20260916]
   口径同 basket_from_grab.py：前 10 → 剔掉不是同一种东西的 → 按商品名里的规格折到篮子单位 → 去掉离中位 2 倍以外的 → 取中位。
   生鲜按「kg」卖的直接是每 kg 价；包装品从名字读 500g / 1kg / 1L / 900ml / 25x2g / 6x330ml。价 = latestPrice（现价，含促销）。"""
import json, re, sys, os, statistics, subprocess
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
# 键: (关键词们, 单位, 折算, 剔除, 只收(可空), label, 备注)
KEYS={
 'flour1kg':   ('bột mì|bột mì 1kg','越南盾/kg','g',r'chiên|pha sẵn|Javel|Nho|tẩy|trộn sẵn|sắn|năng|gạo|nếp|ngọt|canh|nêm|bắp|cà ri|cacao|sữa',r'bột', '面粉 1kg',''),
 'oil1l':      ('dầu ăn','越南盾/L','ml',r'olive|ô liu|gạo lứt|hướng dương|hạt cải nguyên chất|mè|đậu phộng',r'dầu ăn|dầu', '食用油 1L',''),
 'potato1kg':  ('khoai tây','越南盾/kg','g',r'Pringles|snack|bánh|chiên|sấy|lát|đông lạnh|Lutosa|nghiền',r'khoai tây', '土豆 1kg',''),
 'cabbage1kg': ('cải thảo','越南盾/kg','g',r'kim chi|muối|hỏa tiễn',r'cải thảo', '白菜 1kg（cải thảo）',''),
 'onion1kg':   ('hành tây','越南盾/kg','g',r'bánh|lát|snack|phi|sấy',r'hành tây', '洋葱 1kg',''),
 'tomato1kg':  ('cà chua','越南盾/kg','g',r'\bbi\b|cherry|socola|xốt|sốt|tương|đóng hộp|Beef|trái cây|3 màu|sữa chua|pizza|bánh|snack|mì|sấy',r'cà chua', '西红柿 1kg','Beef/cherry 是另一档番茄，只收普通 cà chua'),
 'apple1kg':   ('táo','越南盾/kg','g',r'organic|nước|ép|sấy|giấm|xanh Mỹ',r'táo', '苹果 1kg',''),
 'chicken1kg': ('thịt gà|đùi gà|ức gà','越南盾/kg','g',r'mề|tim|chân|chay|chiên|nấm|xúc xích|viên|sụn|kho|nướng|xông khói|lạp|snack|khô|hộp|vịt|bánh|Orion|sợi|Nestdo',r'gà', '鸡肉 1kg（腿/胸/翅都算）','只剔内脏/鸡爪/零食/熟食'),
 'pork1kg':    ('ba rọi heo|nạc heo','越南盾/kg','g',r'giò|ham|chay|chiên|xông khói|lạp|xúc xích|hộp|Tulip|khô',r'heo', '猪肉 1kg（ba rọi/nạc）',''),
 'beef1kg':    ('thịt bò kg|bò xay','越南盾/kg','g',r'cá ngừ|cá basa|xốt|sốt|pizza|bánh|viên|khô|hộp|Mr\.T|đông lạnh',r'bò', '牛肉 1kg（bắp/thăn/xay）',''),
 'fish1kg':    ('cá basa|cá ngừ','越南盾/kg','g',r'tẩm ướp|kho|hộp|xốt|sốt|mắt cá|đại dương|viên|chả|bao tử|khô|ngâm|bánh|thức ăn|mèo|chó|snack|ruốc|pate|nước mắm|mắm',r'cá basa|cá ngừ', '鱼 1kg（cá basa/cá ngừ 整条或片）','内陆城市，超市冷冻鱼'),
 'tofu1kg':    ('đậu hũ','越南盾/kg','g',r'chiên|ky|nước|sữa|sắn|phộng|Hà Lan|bơ|nấm',r'đậu hũ', '豆腐 1kg',''),
 'soy1l':      ('nước tương','越南盾/L','ml',r'chay|tỏi ớt|đậm đặc',r'nước tương', '酱油 1L',''),
 'fish_sauce1l':('nước mắm','越南盾/L','ml',r'chay|tỏi ớt|ớt|pha sẵn',r'nước mắm', '鱼露 1L（味噌的替换）',''),
 'salt1kg':    ('muối i-ốt','越南盾/kg','g',r'tôm|tiêu|chanh|ớt|sả',r'muối', '盐 1kg',''),
 'sugar1kg':   ('đường trắng','越南盾/kg','g',r'phèn|organic|ăn kiêng|nâu|thốt nốt',r'đường', '糖 1kg',''),
 'tea_bottle1l':('trà xanh không độ|trà xanh 0 độ|trà','越南盾/L','ml',r'túi lọc|Thái Nguyên|gói|hộp|24x|24 x|t24|thùng|bánh|sữa|lon \d+g|Matcha|việt quất|bí đao',r'trà', '瓶装茶 1L（trà xanh 瓶装）',''),
 'tea_leaf1kg': ('trà túi lọc|trà xanh không độ','越南盾/kg','g',r'ml|đào|hồng|sữa|olong|ô long|atiso|thùng|việt quất|dâu|chanh|hương|gừng|hoa',r'trà', '茶叶 1kg（trà xanh 袋泡/散茶）','自泡：1 g 泡 100 ml'),
}
NUM=r'(\d+(?:[.,]\d+)?)'
def unit_price(key,r):
    name=r['name']; p=r['price']; how=KEYS[key][2]
    if how=='g':
        if re.search(r'\bkg\b',name,re.I) and not re.search(NUM+r'\s?kg',name,re.I): return p,'按 kg 卖'
        m=re.search(r'(\d+)\s?x\s?'+NUM+r'\s?(kg|g)\b',name,re.I)
        if m:
            g=int(m.group(1))*float(m.group(2).replace(',','.'))*(1000 if m.group(3).lower()=='kg' else 1); return p/g*1000,f'{m.group(0)}'
        m=re.search(NUM+r'\s?(kg|g)\b',name,re.I)
        if not m: return None,''
        g=float(m.group(1).replace(',','.'))*(1000 if m.group(2).lower()=='kg' else 1); return p/g*1000,f'{m.group(0)}'
    if how=='ml':
        m=re.search(r'(\d+)\s?x\s?'+NUM+r'\s?(ml|l|lít)\b',name,re.I)
        if m:
            ml=int(m.group(1))*float(m.group(2).replace(',','.'))*(1 if m.group(3).lower()=='ml' else 1000); return p/ml*1000,f'{m.group(0)}'
        m=re.search(NUM+r'\s?(ml|l|lít)\b',name,re.I)
        if not m: return None,''
        ml=float(m.group(1).replace(',','.'))*(1 if m.group(2).lower()=='ml' else 1000); return p/ml*1000,f'{m.group(0)}'
    return None,''
def main():
    date=(sys.argv[sys.argv.index('--date')+1] if '--date' in sys.argv else sorted(x for x in os.listdir(os.path.join(ROOT,'raw','buon_ma_thuot')) if x.isdigit())[-1])
    rows=[json.loads(l) for l in open(os.path.join(ROOT,'raw','buon_ma_thuot',date,'coop.jsonl'),encoding='utf-8')]
    cf=os.path.join(ROOT,'cities','buonmathuot.json'); d=json.load(open(cf,encoding='utf-8')); b=d['basket']; done=[]
    for key,(kw,unit,how,excl,incl,label,note) in KEYS.items():
        rs=[]; seen=set()
        for k1 in kw.split('|'):
            for r in sorted([r for r in rows if r['keyword']==k1],key=lambda r:r['rank'])[:10]:
                if r['name'] in seen: continue
                seen.add(r['name']); rs.append(r)
        if not rs: continue
        bad=lambda r: bool(re.search(excl,r['name'],re.I)) or (incl and not re.search(incl,r['name'],re.I))
        dropped=[r['name'][:22] for r in rs if bad(r)]; keep0=[r for r in rs if not bad(r)]
        priced=[]
        for r in keep0:
            u,sp=unit_price(key,r)
            if u: priced.append((r,u,sp))
        if not priced: b.pop(key,None); print(key,'剔完/读不出规格，拿掉'); continue
        med=statistics.median([u for _,u,_ in priced]); kept=[x for x in priced if med/2<=x[1]<=med*2] or priced
        val=round(statistics.median([u for _,u,_ in kept]))
        b[key]={'value':val,'unit':'越南盾','label':label,'source_url':rs[0]['url'],
                'source_name':f"Co.op Online（cooponline.vn，Teko discovery 接口）定位 Co.opmart Buôn Ma Thuột（71 Nguyễn Tất Thành，terminal 138_sgc）搜索“{kw.replace('|','”“')}”默认排序前 {len(rs)}",
                'source_short':'Co.op Online','fetched_at':rs[0]['fetched_at'],'confidence':'listing','n':len(kept),
                'how':f'Co.op Online 定位邦美蜀 Co.opmart 搜「{kw.replace("|","」「")}」默认排序前 {len(rs)} 条，剔掉不是同一种东西的 {len(dropped)} 条'+(f'（{"、".join(dropped)}）' if dropped else '')+f'，其余按商品名里的规格折到 {unit}（按 kg 卖的直接是每 kg 价），去掉离中位 2 倍以外的，取中位（n={len(kept)}）。价是网店现价（含促销）。'+(note+'。' if note else ''),
                'items':[{'name':r['name'][:60],'price':r['price'],'unit':'越南盾','note':f'{sp} → {u:,.0f} {unit}'} for r,u,sp in priced],'items_label':f'看 {len(priced)} 款',
                'note':'；'.join(f"{r['rank']}.{r['name'][:30]} {r['price']:,.0f} đ {sp} → {u:,.0f} {unit}" for r,u,sp in kept)}
        done.append(f'{label} {val:,}（n={len(kept)}）')
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('篮子写入：'+'；'.join(done))
    subprocess.run([sys.executable,os.path.join(os.path.dirname(os.path.abspath(__file__)),'food_basket.py'),'buonmathuot'])
if __name__=='__main__': main()

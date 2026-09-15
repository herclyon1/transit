#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多多买菜 / 美团 抓到的 jsonl → 篮子单价（cities/<city>.json basket[<key>]），规格折算到 1 kg / 1 L / 10 个 / 1 个，再重算食费。
  python3 pipeline/cost/basket_from_grab.py urumqi [--date 20260915]
每个关键词一组：取综合排序前 N 条里能读出规格的，算「元 / 篮子单位」，去掉离中位 2 倍以外的（礼盒/进口/散称异常），取中位；
note 里逐条列「名次. 商品名 价 → 折算」，和之前手工写的一个口径（鸡蛋 30 枚 20.99 ÷ 3 = 7.00 元/10 枚）。
关键词 → 篮子键 见 KEYS；搜别的词也能进（写 --kw 时 phone_grab 记的 keyword 就是它）。
"""
import json, re, sys, os, statistics, datetime, subprocess
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','cost','data')
# 关键词（含同义）→ (篮子键, 篮子单位, 折算方式)：kg = 按重量折到 1 kg；l = 按容量折到 1 L；n10 = 按个数折到 10 个；n1 = 按个数折到 1 个
KEYS={'鸡蛋':('eggs10','n10'),'牛奶':('milk1l','l'),'纯牛奶':('milk1l','l'),'大米':('rice5kg','kg5'),'面粉':('flour1kg','kg'),'挂面':('noodles1kg','kg'),
      '食用油':('oil1l','l'),'菜籽油':('oil1l','l'),'葵花籽油':('oil1l','l'),'土豆':('potato1kg','kg'),'马铃薯':('potato1kg','kg'),'西红柿':('tomato1kg','kg'),'番茄':('tomato1kg','kg'),
      '白菜':('cabbage1kg','kg'),'大白菜':('cabbage1kg','kg'),'鸡腿':('chicken1kg','kg'),'琵琶腿':('chicken1kg','kg'),'鸡全腿':('chicken1kg','kg'),'鸡大腿':('chicken1kg','kg'),'鸡肉':('chicken1kg','kg'),'鸡翅根':('chicken1kg','kg'),'牛肉':('beef1kg','kg'),'牛腩':('beef1kg','kg'),'牛腱':('beef1kg','kg'),'羊肉':('mutton1kg','kg'),'苹果':('apple1kg','kg'),'馕':('naan1','n1'),
      '面包':('bread1kg','kg'),'可乐':('cola1l','l'),'啤酒':('beer6','n6')}
PROXY={}   # 剔完为空时的替身：只认这个词，来源写明
LABEL={'eggs10':'鸡蛋 10 个','milk1l':'牛奶 1L','rice5kg':'大米 5kg','flour1kg':'面粉 1kg','noodles1kg':'挂面 1kg','oil1l':'食用油 1L','potato1kg':'土豆 1kg','tomato1kg':'西红柿 1kg',
       'cabbage1kg':'白菜 1kg','chicken1kg':'鸡肉 1kg（腿/翅根/块）','mutton1kg':'羊肉 1kg','beef1kg':'牛肉 1kg','apple1kg':'苹果 1kg','naan1':'馕 1 个','bread1kg':'面包 1kg','cola1l':'可乐 1L','beer6':'啤酒 6 罐'}
# 同类才比价：搜索结果里混进来的别的品类（乌鸡蛋/卤蛋/鹌鹑蛋、酸奶/奶粉/淡奶油、米粉/糯米、洗菜篮…）按键剔除，再取中位——不然「鸡蛋」的中位会被乌鸡蛋和卤蛋抬到 10 元
EXCL={'eggs10':r'乌鸡|卤蛋|鹌鹑|鸽|咸蛋|皮蛋|茶叶蛋|溏心|篮|蛋糕|蛋挞','milk1l':r'酸奶|奶粉|奶茶|乳饮|蛋白饮|淡奶油|奶油|奶酪|炼乳|豆奶|椰|燕麦奶','rice5kg':r'糯米|米粉|米线|米饼|粥|黑米|紫米|小米',
      'bread1kg':r'蛋糕|饼干|面包机|月饼','cola1l':r'无糖|零度|气泡水|雪碧|美年达|芬达|汉斯|果汁','beer6':r'精酿|白啤|果啤|无醇|啤酒杯|开瓶器','flour1kg':r'面包粉|蛋糕粉|饺子皮|面条|挂面|饼',
      'noodles1kg':r'方便面|拉面|粉丝|米线','oil1l':r'香油|芝麻油|橄榄油|亚麻|茶油|猪油|黄油','potato1kg':r'红薯|紫薯|蜜薯|山药|薯片|薯条|粉条|洋葱|皮芽子','tomato1kg':r'番茄酱|圣女果|小番茄|樱桃番茄|沙司|莴笋|西兰花|黄瓜|辣椒',
      'cabbage1kg':r'娃娃菜|包包菜|包菜|甘蓝|泡菜|酸菜|西兰花|莴笋|菜花|油菜|菠菜|生菜|芹菜|韭菜','chicken1kg':r'鸡爪|鸡脖|鸡架|炸鸡|卤|鸭|盐焗|零食|即食','mutton1kg':r'羊蝎子|羊排|羊杂|羊蹄|羊头|烤串|肉串|羊肉串|羊肉卷|羊肉片|脊骨|羊骨|水饺|饺子|抓饭','apple1kg':r'苹果醋|苹果干|苹果汁|果酱|干|火龙果|香梨|梨|桃|橙|柑|葡萄|哈密瓜','naan1':r'馕坑|馕饼机|馕包肉'}
NUM=r'(\d+(?:\.\d+)?)'
def spec(name):
    """商品名里的规格 → (总重 kg, 总容量 L, 个数)。「200mL*20袋」「净重1.65kg±50g」「5斤」「30枚/板」「500g*2袋」。"""
    s=name.replace('毫升','ml').replace('升','L').replace('千克','kg').replace('公斤','kg').replace('克','g').replace('斤','jin').replace('×','*').replace('x','*').replace('X','*')
    mult=1.0
    m=re.search(r'\*\s*(\d+)\s*(?:袋|盒|包|瓶|罐|桶|板|个|箱|条|块|只|支|提)?',s)
    if m: mult=float(m.group(1))
    kg=L=n=None
    m=re.search(NUM+r'\s*kg',s,re.I)
    if m: kg=float(m.group(1))*mult
    else:
        m=re.search(NUM+r'\s*g(?![a-z])',s,re.I)
        if m: kg=float(m.group(1))/1000*mult
        else:
            m=re.search(NUM+r'\s*jin',s)
            if m: kg=float(m.group(1))*0.5*mult
    m=re.search(NUM+r'\s*L(?![a-z])',s)
    if m: L=float(m.group(1))*mult
    else:
        m=re.search(NUM+r'\s*ml',s,re.I)
        if m: L=float(m.group(1))/1000*mult
    m=re.search(r'(\d+)\s*(?:枚|个|只|张|片|块|罐|听|瓶)',s)
    if m: n=float(m.group(1))*(mult if not re.search(r'\*\s*\d+\s*(?:枚|个|只|张|片|块|罐|听|瓶)',s) else 1)
    return kg,L,n
def unit_price(row,how):
    kg,L,n=spec(row['name']); p=row.get('price')
    if p is None: return None,''
    if how=='kg' and kg: return p/kg, f'{kg:g} kg'
    if how=='kg5' and kg: return p/kg*5, f'{kg:g} kg'
    if how=='l' and L: return p/L, f'{L:g} L'
    if how=='n10' and n: return p/n*10, f'{n:g} 个'
    if how=='n1': return p/(n or 1), f'{n:g} 个' if n else '1 份'   # 馕：团购一份 = 一个（名字里没写个数按 1）
    if how=='n6' and (n or L): return (p/n*6 if n else None), f'{n:g} 罐' if n else ''
    return None,''
def main():
    city=sys.argv[1]; date=(sys.argv[sys.argv.index('--date')+1] if '--date' in sys.argv else sorted(x for x in os.listdir(os.path.join(ROOT,'raw',city)) if x.isdigit())[-1])   # 只认日期目录（README.md 排最后会被当日期）
    rows=[]
    for fn in ('ddmc.jsonl','meituan.jsonl'):
        fp=os.path.join(ROOT,'raw',city,date,fn)
        if os.path.exists(fp): rows+=[json.loads(l) for l in open(fp,encoding='utf-8')]
    if not rows: sys.exit(f'{city}/{date} 没有 ddmc.jsonl / meituan.jsonl')
    cf=os.path.join(ROOT,'cities',f'{city}.json'); d=json.load(open(cf,encoding='utf-8')); b=d.setdefault('basket',{})
    groups={}
    for r in rows:
        kw=(r.get('keyword') or '').strip(); key=next((KEYS[k] for k in KEYS if k in kw),None)
        if key: groups.setdefault(key,[]).append(r)          # 同一篮子键的几个关键词（鸡腿/琵琶腿/鸡全腿）合成一组，免得后搜的空组把先写的值删掉
    done=[]
    for key_how,rs in groups.items():
        key,how=key_how; kw='/'.join(sorted({(r.get('keyword') or '').strip() for r in rs}))
        rs=[r for r in sorted(rs,key=lambda r:r.get('rank',99)) if (r.get('rank') or 99)<=10]   # rank 每页从 1 起，多页（美团馕跑了 3 页）都留，只去每页 10 名以外的
        seen_names=set(); rs=[r for r in rs if not (r['name'] in seen_names or seen_names.add(r['name']))]   # 几个关键词搜到同一件商品只算一次
        allrows=list(rs)
        dropped=[r['name'][:16] for r in rs if EXCL.get(key) and re.search(EXCL[key],r['name'])]
        rs=[r for r in rs if not (EXCL.get(key) and re.search(EXCL[key],r['name']))]
        priced=[]
        for r in rs:
            u,sp=unit_price(r,how)
            if u: priced.append((r,u,sp))
        proxy_note=''
        if not priced and key in PROXY:
            pat,why=PROXY[key]; cand=[r for r in allrows if pat.search(r['name'])]
            seen=set(); cand=[r for r in cand if not (r['name'] in seen or seen.add(r['name']))]
            for r in cand:
                u,sp=unit_price(r,how)
                if u: priced.append((r,u,sp))
            if priced: proxy_note='替身：'+why+'；'
        elif priced and key in PROXY and all(PROXY[key][0].search(r['name']) for r,_,_ in priced): proxy_note='替身：'+PROXY[key][1]+'；'
        if not priced:
            # 剔完同类/读不出规格就一条不剩：不保留旧值也不写 null（validate 不许 null），把这项从篮子里拿掉，等换词再搜（如「鸡腿」→「琵琶腿」「鸡全腿」）
            reason=f'搜「{kw}」前 {len(rs)+len(dropped)} 条剔掉不是同一种东西的 {len(dropped)} 条'+(f'（{"、".join(dropped)}）' if dropped else '')+'后一条不剩'
            b.pop(key,None); print(f'  {kw}：{reason}，从篮子拿掉，换个词再搜'); done.append(f'{LABEL.get(key,key)} 拿掉（{kw}：一条同类都没有）'); continue
        med=statistics.median([u for _,u,_ in priced]); keep=[x for x in priced if med/2<=x[1]<=med*2] or priced
        val=round(statistics.median([u for _,u,_ in keep]),2)
        unit_zh={'kg':'元/kg','kg5':'元/5kg','l':'元/L','n10':'元/10 个','n1':'元/个','n6':'元/6 罐'}[how]
        plat=rs[0].get('platform','多多买菜'); where=max((r.get('pickup') or r.get('location') or '' for r in rs), key=lambda w:(not w.endswith('...'), len(w)))   # 树里有的页把定位块截成「二运司...」，取没截断的
        note='；'.join(f"{r.get('rank','?')}.{r['name'][:28]} {r['price']:g} 元/{sp} → {u:.2f} {unit_zh}" for r,u,sp in keep)
        b[key]={'value':val,'unit':'元','label':LABEL.get(key,key),
                'source_url':'pinduoduo://com.xunmeng.pinduoduo/ywgnpxpt.html?_p_page=vgt_search' if plat=='多多买菜' else None,
                'source_name':f"{plat}（拼多多 App）{d.get('city',city)} 自提点 {where} 搜索“{kw}” {rs[0].get('sort','综合')}排序前 {len(rs)}" if plat=='多多买菜' else f"{plat}团购（美团 App）乌鲁木齐 定位 {where} 搜索“{kw}” {rs[0].get('sort','智能排序')}前 {len(rs)}",
                'source_short':plat,'fetched_at':rs[0].get('fetched_at',datetime.date.today().isoformat()),'confidence':'listing','n':len(keep),
                'how':proxy_note+f'前 {len(rs)+len(dropped)} 条里先剔掉不是同一种东西的 {len(dropped)} 条'+(f'（{"、".join(dropped)}）' if dropped else '')+f'，其余按商品名里的规格折到 {unit_zh}，去掉离中位 2 倍以外的，取中位（n={len(keep)}）——'+('美团团购 智能排序前一屏（团购一份 = 一个，到店自取，馕不能快递）' if plat=='美团' else '买菜 App 综合排序前一屏里普通人挑得到的价')+'',
                'note':f'篮子单位价 = 中位 {val:g} {unit_zh}。{note}'}
        done.append(f'{LABEL.get(key,key)} {val:g} 元（{kw}，n={len(keep)}）')
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('篮子写入：'+('；'.join(done) if done else '无'))
    subprocess.run([sys.executable,os.path.join(os.path.dirname(os.path.abspath(__file__)),'food_basket.py'),city])
if __name__=='__main__': main()

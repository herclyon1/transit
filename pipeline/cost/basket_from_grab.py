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
      '白菜':('cabbage1kg','kg'),'大白菜':('cabbage1kg','kg'),'鸡腿':('chicken1kg','kg'),'羊肉':('mutton1kg','kg'),'苹果':('apple1kg','kg'),'馕':('naan1','n1'),
      '面包':('bread1kg','kg'),'可乐':('cola1l','l'),'啤酒':('beer6','n6')}
LABEL={'eggs10':'鸡蛋 10 个','milk1l':'牛奶 1L','rice5kg':'大米 5kg','flour1kg':'面粉 1kg','noodles1kg':'挂面 1kg','oil1l':'食用油 1L','potato1kg':'土豆 1kg','tomato1kg':'西红柿 1kg',
       'cabbage1kg':'白菜 1kg','chicken1kg':'鸡腿 1kg','mutton1kg':'羊肉 1kg','apple1kg':'苹果 1kg','naan1':'馕 1 个','bread1kg':'面包 1kg','cola1l':'可乐 1L','beer6':'啤酒 6 罐'}
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
    if how=='n1' and n: return p/n, f'{n:g} 个'
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
        if key: groups.setdefault((key,kw),[]).append(r)
    done=[]
    for (key_how,kw),rs in groups.items():
        key,how=key_how
        rs=sorted(rs,key=lambda r:r.get('rank',99))[:10]
        priced=[]
        for r in rs:
            u,sp=unit_price(r,how)
            if u: priced.append((r,u,sp))
        if not priced: print(f'  {kw}：{len(rs)} 条都读不出规格，跳过'); continue
        med=statistics.median([u for _,u,_ in priced]); keep=[x for x in priced if med/2<=x[1]<=med*2] or priced
        val=round(statistics.median([u for _,u,_ in keep]),2)
        unit_zh={'kg':'元/kg','kg5':'元/5kg','l':'元/L','n10':'元/10 个','n1':'元/个','n6':'元/6 罐'}[how]
        plat=rs[0].get('platform','多多买菜'); where=rs[0].get('pickup') or rs[0].get('location') or ''
        note='；'.join(f"{r.get('rank','?')}.{r['name'][:28]} {r['price']:g} 元/{sp} → {u:.2f} {unit_zh}" for r,u,sp in keep)
        b[key]={'value':val,'unit':'元','label':LABEL.get(key,key),
                'source_url':'pinduoduo://com.xunmeng.pinduoduo/ywgnpxpt.html?_p_page=vgt_search' if plat=='多多买菜' else None,
                'source_name':f"{plat}（拼多多 App）{d.get('city',city)} 自提点 {where} 搜索“{kw}” {rs[0].get('sort','综合')}排序前 {len(rs)}" if plat=='多多买菜' else f"{plat} {where} 搜索“{kw}”",
                'source_short':plat,'fetched_at':rs[0].get('fetched_at',datetime.date.today().isoformat()),'confidence':'listing','n':len(keep),
                'how':f'前 {len(rs)} 条按商品名里的规格折到 {unit_zh}，去掉离中位 2 倍以外的，取中位（n={len(keep)}）',
                'note':f'篮子单位价 = 中位 {val:g} {unit_zh}。{note}'}
        done.append(f'{LABEL.get(key,key)} {val:g} 元（{kw}，n={len(keep)}）')
    json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('篮子写入：'+('；'.join(done) if done else '无'))
    subprocess.run([sys.executable,os.path.join(os.path.dirname(os.path.abspath(__file__)),'food_basket.py'),city])
if __name__=='__main__': main()

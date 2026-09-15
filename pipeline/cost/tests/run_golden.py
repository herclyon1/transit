#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析回归样本：pipeline/cost/tests/golden.jsonl（一行一条：raw 原文 + expect 期望字段）。
  python3 pipeline/cost/tests/run_golden.py         # 全对才许重跑正式数据（maa 2026-09-15 定的规矩）
expect 里 contact 可以写 True/False（有没有）或具体值；reasons 不看顺序；没写的字段不比。
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sources'))
from common import Rec, extract_common, judge
from weixin_sogou import CITY_HINT
gold=[json.loads(l) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'golden.jsonl'),encoding='utf-8')]
bad=0
for g in gold:
    r=Rec(city='urumqi', source=g.get('source','weixin_sogou'), source_url='https://example.test/x', fetched_at='2026-09-15', posted_at=datetime.date.today().isoformat(), raw=g['raw'], account='golden', article_title='golden')
    if g.get('site_apply'): r['site_apply']=True
    extract_common(r, CITY_HINT['urumqi']); r['reasons']=judge(r,180)
    diffs=[]
    for k,v in g['expect'].items():
        got=r.get(k)
        if k=='reasons': ok=set(got or [])==set(v)
        elif k=='contact' and isinstance(v,bool): ok=bool(got)==v
        elif isinstance(v,(int,float)) and got is not None and not isinstance(v,bool): ok=abs(float(got)-float(v))<0.06
        else: ok=(got==v)
        if not ok: diffs.append(f'{k}: 期望 {v!r} 得到 {got!r}')
    if diffs: bad+=1; print('✗',g['name']); [print('   ',d) for d in diffs]
    else: print('✓',g['name'])
print(f'\n{len(gold)-bad}/{len(gold)} 通过'); sys.exit(1 if bad else 0)

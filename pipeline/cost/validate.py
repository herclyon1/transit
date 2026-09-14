#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
城市数据自检：岗位时薪必须带帖子写明的工时（basis=posted）；没写工时的帖不能折时薪，只能空。
  python3 pipeline/cost/validate.py            # 检查 cost/data/cities/*.json
退出码非 0 = 有问题。提交前跑一遍。
"""
import glob, json, re, sys
bad=0
for f in sorted(glob.glob('cost/data/cities/*.json')):
    d=json.load(open(f,encoding='utf-8'))
    for j in d.get('jobs',[]):
        w=j.get('wage',{}); h=w.get('hours')
        if w.get('value') is None: continue
        if not h or h.get('basis')!='posted':
            print(f'{f}: 岗位「{j["chain"][:20]}」时薪 {w.get("value")} 没有帖子写明的工时（hours.basis 必须是 posted，不允许 assumed）'); bad+=1; continue
        if re.search(r'÷\s*174', w.get('note','')) and '对照' not in w.get('note','') and h.get('monthly')==174:
            print(f'{f}: 岗位「{j["chain"][:20]}」主数用了 174 小时法定口径'); bad+=1
    for sec in ('basket','utilities'):
        for k,v in d.get(sec,{}).items():
            if isinstance(v,dict) and v.get('value') is None:
                print(f'{f}: {sec}.{k} 是 null'); bad+=1
print('OK' if not bad else f'{bad} 个问题'); sys.exit(1 if bad else 0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
城市数据自检：岗位时薪必须带帖子写明的工时（basis=posted）；「上一休一」没写班长默认 24 h 在岗（basis=default_24h，用户 2026-09-15 18:45 定）；
没写工时的帖不能折时薪，只能空；不允许 assumed（法定 174 h 之类的默认值）。
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
        if not h or h.get('basis') not in ('posted','default_24h'):
            print(f'{f}: 岗位「{j["chain"][:20]}」时薪 {w.get("value")} 没有帖子写明的工时（hours.basis 必须是 posted，或「上一休一」默认 24h 的 default_24h）'); bad+=1; continue
        if h.get('basis')=='default_24h' and not (h.get('days_per_month') and h.get('posted')):
            print(f'{f}: 岗位「{j["chain"][:20]}」default_24h 但帖子没写班制'); bad+=1; continue
        pa=w.get('posted_at')
        if not pa:
            print(f'{f}: 岗位「{j["chain"][:20]}」没有 posted_at（帖子日期），半年有效期无法判定'); bad+=1
        else:
            import datetime
            age=(datetime.date.today()-datetime.date.fromisoformat(pa)).days
            if age>180: print(f'{f}: 岗位「{j["chain"][:20]}」帖子 {pa} 已 {age} 天，超过半年不能用'); bad+=1
    for sec in ('basket','utilities'):
        for k,v in d.get(sec,{}).items():
            if isinstance(v,dict) and v.get('value') is None:
                print(f'{f}: {sec}.{k} 是 null'); bad+=1
print('OK' if not bad else f'{bad} 个问题'); sys.exit(1 if bad else 0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 source_name 里的内部记录（原始文件路径、无障碍树抓取字样）挪到 raw 字段，页面只显示干净的来源名。幂等；ingest 后、提交前跑一遍。
   python3 pipeline/cost/tidy_sources.py"""
import glob, json, re
PAT=re.compile(r'[（(][^（()）]*(?:无障碍树|原始 cost/data|原始 raw/)[^（()）]*[）)]')
RAW=re.compile(r'(?:cost/data/)?raw/[\w/.\-]+\.jsonl?')
n=0
for f in sorted(glob.glob('cost/data/cities/*.json')):
    d=json.load(open(f,encoding='utf-8')); changed=False
    def walk(o):
        global changed
        if isinstance(o,dict):
            sn=o.get('source_name')
            if isinstance(sn,str):
                r=RAW.search(sn)
                if r and not o.get('raw'): o['raw']=r.group(0)
                sn2=PAT.sub('',sn); sn2=RAW.sub('',sn2); sn2=re.sub(r'[（(]\s*[）)]','',sn2); sn2=re.sub(r'\s{2,}',' ',sn2).strip(' ，,；;')
                if sn2!=sn: o['source_name']=sn2; changed=True
            for v in o.values(): walk(v)
        elif isinstance(o,list):
            for v in o: walk(v)
    walk(d)
    if changed:
        json.dump(d,open(f,'w',encoding='utf-8'),ensure_ascii=False,indent=1); n+=1; print('tidy',f)
print(n,'files changed')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
各来源适配器共用：记录格式、字段抽取（工资/工时/联系/雇主）、PLAN-v2 判据、输出（jobs_raw.jsonl / rejected.jsonl / report.md）。
判据（PLAN-v2 §一）：用人单位自己发（中介帖须写明具体用人单位，标 via_agent）+ 确数工资 + 写明工时或班次 + 日期 ≤90（最长 180）+ 联系方式或链接。
时薪 = 月薪 ÷ 帖子写明的月工时（wage-must-carry-hours）；算不出月工时的不算「有工时」。
"""
import re, os, json, datetime, collections

BASKET_KW={'security':['保安','门卫','安保','消防','消控','特勤','保卫'],'food':['服务员','后厨','传菜','洗碗','厨师','收银员','餐厅','奶茶','咖啡师','店员'],
           'retail':['理货','超市','便利店','收银','导购','店员','营业员'],'delivery':['快递','分拣','骑手','外卖','配送','仓储','仓库','打包'],
           'factory':['普工','操作工','包装工','车间','厂','生产'],'cleaning':['保洁','清洁','阿姨','家政','钟点','育儿','护理','月嫂'],
           'chain':['麦当劳','肯德基','KFC','星巴克','瑞幸','必胜客','汉堡王','7-Eleven','全家','罗森']}
AGENT_KW=['人力资源','劳务','中介','派遣','外包','人才','推荐工作','进群','求职群','加微信报名','报名咨询']
RANGE=re.compile(r'(\d{3,5})\s*[-–—~至到]\s*(\d{3,5})')

class Rec(dict):
    def __init__(self,**kw): super().__init__(**kw)

def _num(s): return float(s.replace(',',''))

def extract_common(r, city_hint):
    t=r['raw']
    # ---- 工资：确数优先；区间/面议/保底+提成记为 range
    wage=None; unit=None; rng=RANGE.search(t) and not re.search(r'(\d{1,2})[:：]\d{2}\s*[-–—~至到]\s*(\d{1,2})[:：]\d{2}',RANGE.search(t).group(0))
    m=(re.search(r'(\d{1,3}(?:\.\d)?)\s*元\s*(?:/|一|每|一个)?\s*小时',t) or re.search(r'(?:时薪|每小时|元/小时|/时|/h)[^\d\n]{0,4}(\d{1,3}(?:\.\d)?)',t))
    if m: wage=_num(m.group(1)); unit='CNY/小时'
    else:
        m=(re.search(r'(?:月薪|月工资|工资|薪资|薪水|待遇|综合到手|到手)[^\d\n]{0,8}(\d{4,5})(?!\s*[-–—~至到]\s*\d)(?!\d)',t) or re.search(r'(\d{4,5})\s*(?:元)?\s*/\s*月',t)
           or re.search(r'(?<![\d\-–—~至到])(\d{4,5})\s*(?:元)?\s*(?:单休|双休|月休|包吃|管吃|包住|管住)',t))
        if m: wage=_num(m.group(1)); unit='CNY/月'
        else:
            m=(re.search(r'(\d{2,3})\s*元\s*(?:/|一|每)\s*天',t) or re.search(r'(?:日薪|日结|日工资)[^\d\n]{0,6}(\d{2,3})(?!\s*[-–—~至到]\s*\d)(?!\d)',t) or re.search(r'一天\s*(\d{2,3})\s*元?(?!\s*[-–—~至到]\s*\d)(?!\d)',t))
            if m and not re.search(r'\d+\s*[-–—~至到]\s*'+m.group(1),t): wage=_num(m.group(1)); unit='CNY/天'
    r['wage_value']=wage; r['wage_unit']=unit; r['wage_range']=bool(rng and wage is None)
    if '面议' in t: r['wage_range']=True
    # ---- 工时/班次
    hours_text=[]; hpd=None; dpm=None; flag=''
    # 班次时间：两边都得是「8点/8:00/8：30」这种钟点，避免把 18-45岁、260-280、9.14-9.27 当成时间
    PFX=r'(?:早上|早|上午|中午|下午|晚上|晚|凌晨|次日|第二天)?'
    ms=re.search(PFX+r'(\d{1,2})(?:[:：](\d{2})|点(半)?|时)\s*[-–—~至到]\s*'+PFX+r'(\d{1,2})(?:[:：](\d{2})|点(半)?|时)',t)
    if ms:
        h1=int(ms.group(1))+(int(ms.group(2) or 0)/60)+(0.5 if ms.group(3) else 0); h2=int(ms.group(4))+(int(ms.group(5) or 0)/60)+(0.5 if ms.group(6) else 0)
        pre=t[max(0,ms.start()-3):ms.start()]
        if h2<=12 and re.search(r'晚|下午|凌晨',t[ms.start():ms.end()]) and h2<=h1: h2+=12
        if h2<=h1: h2+=24
        hpd=round(h2-h1,1); hours_text.append(ms.group(0))
        if re.search(r'中间.{0,6}(休息|吃饭).{0,4}(一|1)\s*小时|吃饭休息一小时',t) and not re.search(r'算入工资|计入工资',t): hpd=round(hpd-1,1); flag+='-1h饭 '
    m=re.search(r'(\d{1,2})\s*小时(?:工作制|/天|一天)?',t)
    if not hpd and m: hpd=float(m.group(1)); hours_text.append(m.group(0))
    m=re.search(r'月休\s*(\d{1,2})\s*天|每月休\s*(\d{1,2})',t)
    if m: dpm=30-int(m.group(1) or m.group(2)); hours_text.append(m.group(0))
    if re.search(r'单休',t): dpm=dpm or 26; hours_text.append('单休')
    if re.search(r'双休',t): dpm=dpm or 22; hours_text.append('双休')
    m=re.search(r'上\s*(\d{1,2}|一|二|三|四|五|六)\s*(?:天)?休\s*(\d{1,2}|一|二|三|四|五|六)',t)
    if m:
        cn={'一':1,'二':2,'三':3,'四':4,'五':5,'六':6}; on=cn.get(m.group(1)) or int(m.group(1)); off=cn.get(m.group(2)) or int(m.group(2))
        dpm=dpm or round(30*on/(on+off)); hours_text.append(m.group(0))
        if on==1 and off>=1 and not hpd: hpd=24; flag+='24h岗 '   # 「上一休一」= 24 小时在岗（含夜间值守），月工时 = 24 × 班数，卡片里注明
    m=re.search(r'(\d{1,2})\s*小时\s*(?:班|制|一班|/班)',t)
    if m and not hpd: hpd=float(m.group(1)); hours_text.append(m.group(0))
    m=re.search(r'(?:每月|一个月|月)[^\n\d]{0,3}休(?:息)?\s*(\d{1,2}|一|两|二|三|四|五|六)\s*(?:个)?\s*(?:整)?天',t)
    if m and not dpm:
        cn={'一':1,'两':2,'二':2,'三':3,'四':4,'五':5,'六':6}; dpm=30-(cn.get(m.group(1)) or int(m.group(1))); hours_text.append(m.group(0))
    if re.search(r'每月\s*(\d)\s*天调休',t) and not dpm: dpm=30-int(re.search(r'每月\s*(\d)\s*天调休',t).group(1)); hours_text.append('调休')
    if re.search(r'两班倒|倒班|白夜班',t): hours_text.append('倒班')
    if re.search(r'白班.{0,12}\d.{0,12}夜班',t) and hpd and hpd>=11: flag+='两班倒 '
    if not hpd and dpm and re.search(r'24\s*小时',t): hpd=24; flag+='24h '
    r['hours_text']=' / '.join(dict.fromkeys(hours_text)); r['hours_per_day']=hpd; r['days_per_month']=dpm; r['hours_flag']=flag.strip()
    r['hours_month']=round(hpd*dpm) if (hpd and dpm) else None
    if r['hours_month'] and wage:
        r['hourly']=round(wage/r['hours_month'],1) if unit=='CNY/月' else (wage if unit=='CNY/小时' else (round(wage/hpd,1) if unit=='CNY/天' and hpd else None))
    else: r['hourly']=wage if unit=='CNY/小时' else (round(wage/hpd,1) if (unit=='CNY/天' and hpd) else None)
    # ---- 联系
    ph=re.findall(r'(?<!\d)1[3-9]\d{9}(?!\d)',t); wx=re.findall(r'(?:微信|VX|vx|v信)[:：\s]*([A-Za-z0-9_\-]{5,20})',t)
    r['contact']=(ph[0][:3]+'****'+ph[0][7:]) if ph else (('微信 '+wx[0]) if wx else None)
    # ---- 雇主/岗位/篮子/地点
    em=re.search(r'([一-龥A-Za-z0-9·（）()]{2,20}(?:公司|集团|酒店|饭店|餐厅|超市|便利店|工厂|厂|医院|学校|幼儿园|小区|物业|商场|广场|仓|驿站|门店|店|院|所|中心|基地|银行|车站|机场))',t)
    r['employer']=re.sub(r'^(?:民族不限|免费住宿|工资周结|工资月结|男女不限|包吃包住|管吃管住|长期|急招|招聘|诚聘|招)+','',em.group(1)) if em else None
    if r['employer'] and len(r['employer'])<3: r['employer']=None
    r['via_agent']=bool(re.search('|'.join(AGENT_KW),t)) or bool(re.search(r'直招|直聘',t)) is False and r['employer'] is None
    # 岗位名：从篮子关键词出发取「××保安员」「仓储操作员」这种短语；没有篮子词的帖子进不了库，所以不会有碎片标题
    r['basket']=None; r['title']=None
    for k,kws in BASKET_KW.items():
        for w in kws:
            m=re.search(r'[一-龥A-Za-z]{0,4}'+re.escape(w)+r'(?:员|工|师傅|人员|岗)?',t)
            if m:
                cand=m.group(0); cand=re.sub(r'^(?:招聘|招|急招|诚聘|需要|聘请|现招|名|名的)+','',cand)
                if r['basket'] is None or m.start()<r.get('_tpos',1e9): r['basket']=k; r['title']=cand; r['_tpos']=m.start()
    r.pop('_tpos',None)
    # 文章本身就是「乌鲁木齐招聘」，帖子没写别的城市就算本市；写了地州/团场的算外地
    hin=city_hint['in'] if isinstance(city_hint,dict) else city_hint; hout=city_hint.get('out',[]) if isinstance(city_hint,dict) else []
    r['location']=next((h for h in hin if h in t),None); r['in_city']=bool(r['location']) or not any(h in t for h in hout)

def judge(r, days=90):
    reasons=[]
    if r.get('wage_value') is None: reasons.append('range_wage' if r.get('wage_range') else 'no_wage')
    u=r.get('wage_unit')
    if (u=='CNY/月' and not r.get('hours_month')) or (u=='CNY/天' and not r.get('hours_per_day')) or (u=='CNY/小时' and not (r.get('hours_per_day') or r.get('hours_text'))) or (u is None and not r.get('hours_month')): reasons.append('no_hours')
    if r.get('via_agent') and not r.get('employer'): reasons.append('agent_unnamed')
    try:
        age=(datetime.date.today()-datetime.date.fromisoformat(r['posted_at'][:10])).days
        if age>180: reasons.append('stale');
        elif age>days: reasons.append('older_than_%d'%days)
    except Exception: reasons.append('no_date')
    if not r.get('contact') and not r.get('source_url'): reasons.append('no_contact')
    if not r.get('in_city'): reasons.append('off_city')
    if not r.get('basket'): reasons.append('off_basket')
    return reasons

def write_outputs(outdir, source, recs, log, days=90):
    acc=[]; rej=[]; dist=collections.Counter()
    for r in recs:
        rs=judge(r, days); r['reasons']=rs
        (acc if not rs else rej).append(r)
        for x in rs: dist[x]+=1
    with open(os.path.join(outdir,'jobs_raw.jsonl'),'a',encoding='utf-8') as f:
        for r in acc: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with open(os.path.join(outdir,'rejected.jsonl'),'a',encoding='utf-8') as f:
        for r in rej: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    rep=os.path.join(outdir,'report.md')
    with open(rep,'a',encoding='utf-8') as f:
        f.write(f"\n## {source} · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n看了 **{len(recs)}** 条，收 **{len(acc)}** 条，拒 {len(rej)} 条。\n\n拒绝原因分布：" + '、'.join(f'{k} {v}' for k,v in dist.most_common()) + "\n\n")
        if acc:
            f.write('| 篮子 | 岗位 | 雇主 | 工资 | 工时 | 月工时 | 时薪 | 发帖 | 来源 |\n|---|---|---|---|---|---|---|---|---|\n')
            for r in acc: f.write(f"| {r.get('basket')} | {r.get('title')} | {r.get('employer') or '—'}{'（中介转）' if r.get('via_agent') else ''} | {r.get('wage_value')} {r.get('wage_unit')} | {r.get('hours_text')} {r.get('hours_flag','')} | {r.get('hours_month') or '—'} | {r.get('hourly') or '—'} | {r.get('posted_at')} | {r.get('account','')} |\n")
        f.write('\n过程：\n' + '\n'.join('- '+l for l in log) + '\n')
    print(f'{source}: 看了 {len(recs)}，收 {len(acc)}，拒 {len(rej)}；分布 {dict(dist)}；报告 {rep}')

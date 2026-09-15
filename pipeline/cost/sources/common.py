#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
各来源适配器共用：记录格式、字段抽取（工资/工时/联系/雇主）、PLAN-v2 判据、输出（jobs_raw.jsonl / rejected.jsonl / report.md）。
判据（PLAN-v2 §一）：用人单位自己发（中介帖须写明具体用人单位，标 via_agent）+ 确数工资 + 写明工时或班次 + 日期最长 180 天（≤90 优先，记 age_days）+ 联系方式
（微信文章来源必须有电话/微信；站内投递的站点 site_apply 用帖子 URL 即可）。
时薪 = 月薪 ÷ 帖子写明的月工时（wage-must-carry-hours）；算不出月工时的不算「有工时」。
2026-09-15 审计后补的规则：区间写法「3500—4000元/月」「4150元 - 4500元/月」记 range；多段班次求和；午休 N 小时扣减；
「地点：」不再写进雇主；篮子关键词不在公司名里找；地址行里的外地地名优先于文章模板头；临时单（今天/预计 N 天）标 temp。
"""
import re, os, json, datetime, collections

BASKET_KW={'security':['保安','门卫','安保','消防','消控','特勤','保卫'],'food':['服务员','服务生','后厨','传菜','洗碗','厨师','收银员','餐厅','奶茶','咖啡师','店员'],
           'retail':['理货','超市','便利店','收银','导购','店员','营业员'],'delivery':['快递','分拣','骑手','外卖','配送','仓储','仓库','打包'],
           'factory':['普工','操作工','包装工','车间','厂','生产'],'cleaning':['保洁','清洁'],'home':['家政','钟点','育儿','护理','月嫂','阿姨'],   # home = 私人家庭钟点/家政：记但不进篮子最低值
           'chain':['麦当劳','肯德基','KFC','星巴克','瑞幸','必胜客','汉堡王','7-Eleven','全家','罗森']}
AGENT_KW=['人力资源','劳务','中介','派遣','外包','人才','推荐工作','进群','求职群','加微信报名','报名咨询']
SEP=r'[-–—~～至到]'
RANGE=re.compile(r'(\d{3,5})\s*(?:元)?\s*'+SEP+r'\s*(\d{3,5})')
CN={'一':1,'两':2,'二':2,'三':3,'四':4,'五':5,'六':6,'半':0.5}

PHONE=re.compile(r'(?<!\d)(1[3-9]\d)(\d{4})(\d{4})(?!\d)')
def mask(t): return PHONE.sub(lambda m:m.group(1)+'****'+m.group(3),t) if isinstance(t,str) else t
def dump(r): return mask(json.dumps(r,ensure_ascii=False))   # 仓库是公开的：raw / 任何字段里的手机号一律打码后落盘（contact 早就打了）

class Rec(dict):
    def __init__(self,**kw): super().__init__(**kw)

def _num(s): return float(s.replace(',',''))

def _is_endpoint(t, n):
    """n 是不是某个「A—B」区间的端点（3500—4000元/月、4150元 - 4500元/月、100-150/天）；钟点 9:00-18:00 不算"""
    n=str(int(n)) if float(n).is_integer() else str(n)
    return bool(re.search(r'(?<![\d.])'+n+r'\s*(?:元)?\s*'+SEP+r'\s*\d{2,5}(?![\d:：.])|(?<![\d.])\d{2,5}\s*(?:元)?\s*'+SEP+r'\s*'+n+r'(?![\d:：.])',t))

def extract_common(r, city_hint):
    t=r['raw']
    # ---- 工资：确数优先；区间/面议/保底+提成记为 range
    wage=None; unit=None
    rng=any(not re.search(r'\d{1,2}[:：.]\d{2}',m.group(0)) for m in RANGE.finditer(t))
    m=(re.search(r'(\d{1,3}(?:\.\d)?)\s*元?\s*(?:/|一|每|一个)\s*小时',t) or re.search(r'(\d{1,3}(?:\.\d)?)\s*(?:元)?\s*/\s*(?:时|h|H)(?![\d])',t) or re.search(r'(?:时薪|每小时|元/小时)[^\d\n]{0,4}(\d{1,3}(?:\.\d)?)',t))
    m2=re.search(r'(?:实习期|试用期)[^\n\d]{0,6}(\d{4,5})[^\n]{0,14}?(?:次月|转正|之后|以后|第二个月|满月|期满)[^\d\n]{0,10}(\d{4,5})(?!\d)',t)   # 「实习期3000次月开始拿到手3800」→ 3800
    if m: wage=_num(m.group(1)); unit='CNY/小时'
    elif m2: wage=_num(m2.group(2)); unit='CNY/月'
    else:
        m=(re.search(r'(?:月薪|月工资|月收入|工资|薪资|薪水|待遇|综合到手|到手|底薪)[^\d\n]{0,8}(\d{4,5})(?!\s*(?:元)?\s*'+SEP+r'\s*\d)(?!\s*/\s*\d)(?!\d)',t) or re.search(r'(?<![\d\-–—~～至到])(?<!['+SEP[1:-1]+r']\s)(\d{4,5})\s*(?:元)?\s*/\s*月',t)
           or re.search(r'(?<![\d\-–—~～至到])(\d{4,5})\s*(?:元)?\s*(?:单休|双休|月休|包吃|管吃|包住|管住)',t))
        if m: wage=_num(m.group(1)); unit='CNY/月'
        else:
            NOTH=r'(?!\s*(?:个)?\s*(?:小时|h|H|天|点|时|[:：]\d))'   # 「一天10小时」「日结150」后面跟小时/天/钟点的不是工资
            m=(re.search(r'(\d{2,3})\s*元?\s*(?:/|一|每)\s*天(?!\s*'+SEP+r'\s*\d)',t) or re.search(r'(?:日薪|日结|日工资)[^\d\n]{0,6}(\d{2,3})(?!\s*'+SEP+r'\s*\d)(?!\d)'+NOTH,t) or re.search(r'一天\s*(\d{2,3})\s*元?(?!\s*'+SEP+r'\s*\d)(?!\d)'+NOTH,t))
            if m: wage=_num(m.group(1)); unit='CNY/天'
    # 抽到的数是区间端点 → 不是确数
    if wage is not None and _is_endpoint(t,wage): wage=None; unit=None; rng=True
    # 「基础薪资1200+餐补+提成」「底薪3000+提成」是组合薪资，不是确数
    if wage is not None and unit=='CNY/月' and re.search(r'(?:底薪|基础薪资|基本工资|保底)[^\n\d]{0,4}'+str(int(wage))+r'\s*(?:元)?\s*[+＋]|'+str(int(wage))+r'\s*(?:元)?\s*[+＋]\s*(?:提成|补贴|绩效|奖金|餐补|月餐补)',t): wage=None; unit=None; rng=True
    r['wage_value']=wage; r['wage_unit']=unit; r['wage_range']=bool(rng and wage is None)
    if '面议' in t: r['wage_range']=True
    r['probation']=bool(wage is not None and re.search(r'试用期?[^\n]{0,12}'+str(int(wage)) if float(wage).is_integer() else r'试用期?[^\n]{0,12}'+str(wage),t))
    # ---- 工时/班次
    hours_text=[]; hpd=None; dpm=None; flag=''
    # 班次时间：两边都得是「8点/8:00/8：30」这种钟点，避免把 18-45岁、260-280、9.14-9.27 当成时间
    PFX=r'(?:早上|早|上午|中午|下午|晚上|晚|凌晨|次日|第二天)?'
    SHIFT=re.compile(PFX+r'(\d{1,2})(?:[:：.](\d{2})|点(半|\d{2})?|时)\s*'+SEP+r'\s*'+PFX+r'(\d{1,2})(?:[:：.](\d{2})|点(半|\d{2})?|时)')   # 9:00 / 9.00 / 9点 / 9点半 / 3点30
    segs=list(SHIFT.finditer(t)) or list(re.finditer(r'早\s*(\d{1,2})()()\s*晚\s*(\d{1,2})()()',t))
    if segs:
        def dur(ms):
            mn=lambda g:(0.5 if g=='半' else int(g)/60) if g else 0
            h1=int(ms.group(1))+(int(ms.group(2) or 0)/60)+mn(ms.group(3)); h2=int(ms.group(4))+(int(ms.group(5) or 0)/60)+mn(ms.group(6))
            if h2<=12 and re.search(r'晚|下午|凌晨',ms.group(0)) and h2<=h1: h2+=12
            if h2<=h1: h2+=24
            return h2-h1
        hpd=dur(segs[0]); hours_text.append(segs[0].group(0)); last=segs[0]
        # 「9.30-14.00，15.30-20.00」：第二段在第一段结束后开始、中间只有逗号 → 同一班两段求和（合计 ≤14h）；
        # 「早8:00–20:00/ 早9:00–21:00 / 午13:30–00:30」是可选班次、「白班 8-20 夜班 20-8」是倒班 → 只取第一段
        def start_h(ms): return int(ms.group(1))+(int(ms.group(2) or 0)/60)
        for ms in segs[1:]:
            gap=t[last.end():ms.start()]
            if re.fullmatch(r'[，,、；;和及\s]{0,3}',gap) and start_h(ms)>=start_h(last)+dur(last) and hpd+dur(ms)<=14: hpd+=dur(ms); hours_text.append(ms.group(0)); last=ms
            else: break
        hpd=round(hpd,1)
        mb=re.search(r'(?:午休|午餐|中间休息|休息|吃饭)[^\n\d]{0,6}(\d(?:\.\d)?|半|一|两|二)\s*(?:个)?\s*(?:半)?\s*小时',t)
        if mb and not re.search(r'算入工资|计入工资|算工时|计入工时|算入工时|算时间|算上班时间',t):
            b=CN.get(mb.group(1)) or float(mb.group(1))
            if '个半' in mb.group(0) or re.search(r'\d\s*个半',mb.group(0)): b+=0.5
            hpd=round(hpd-b,1); flag+=f'-{b:g}h饭 '
    m=re.search(r'(\d{1,2})\s*小时(?:工作制|/天|一天)?',t)
    if not hpd and m: hpd=float(m.group(1)); hours_text.append(m.group(0))
    m=re.search(r'月休\s*(\d{1,2})\s*天|每月休\s*(\d{1,2})',t)
    if m: dpm=30-int(m.group(1) or m.group(2)); hours_text.append(m.group(0))
    if re.search(r'单休',t): dpm=dpm or 26; hours_text.append('单休')
    if re.search(r'双休',t): dpm=dpm or 22; hours_text.append('双休')
    m=re.search(r'上\s*(\d{1,2}|一|二|三|四|五|六)\s*(?:天)?休\s*(\d{1,2}|一|二|三|四|五|六)',t)
    if m:
        on=CN.get(m.group(1)) or int(m.group(1)); off=CN.get(m.group(2)) or int(m.group(2))
        dpm=dpm or round(30*on/(on+off)); hours_text.append(m.group(0))
        if on==1 and off>=1 and not hpd:
            # 「上一休一」= 24 小时在岗；但帖子自己给了 12 小时倒班的选项（「也可白夜班倒」「12小时」）就按 12 算
            if re.search(r'也可.{0,4}(?:白夜|倒班|两班)|白夜班倒|12\s*小时',t): hpd=12; flag+='上一休一可倒班 '
            else: hpd=24; flag+='24h岗 '   # 月工时 = 24 × 班数，卡片里注明
    m=re.search(r'(\d{1,2})\s*小时\s*(?:班|制|一班|/班)',t)
    if m and not hpd: hpd=float(m.group(1)); hours_text.append(m.group(0))
    m=re.search(r'(?:每月|一个月|月)[^\n\d]{0,3}休(?:息)?\s*(\d{1,2}|一|两|二|三|四|五|六)\s*(?:个)?\s*(?:整)?天',t)
    if m and not dpm: dpm=30-int(CN.get(m.group(1)) or int(m.group(1))); hours_text.append(m.group(0))
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
    ph=re.findall(r'(?<!\d)1[3-9]\d(?:\d{4}|\*{4})\d{4}(?!\d)',t); wx=re.findall(r'(?:微信|VX|vx|v信)[:：\s]*([A-Za-z0-9_\-]{5,20})',t)   # 落盘的 raw 已打码，重跑时 192****4918 也算电话
    r['contact']=(ph[0][:3]+'****'+ph[0][-4:]) if ph else (('微信 '+wx[0]) if wx else ('文内二维码' if re.search(r'扫码报名|扫二维码|二维码报名|长按.{0,4}二维码',t) else None))   # 三者之一才算「立刻能去应聘」
    # ---- 雇主/岗位/篮子/地点
    SUF=r'(?:公司|集团|酒店|饭店|餐厅|超市|便利店|工厂|厂|医院|学校|幼儿园|小区|物业|商场|广场|仓|驿站|门店|店|院|所|中心|基地|银行|车站|机场|总部|营业部|网点|站点|\d{1,3}(?:小学|中学|小|中)(?![学时]))'
    em=(re.search(r'(?:单位|公司|雇主|用人单位)[:：]\s*([一-龥A-Za-z0-9·（）()]{2,24})',t) or re.search(r'([一-龥A-Za-z0-9·]{2,20}'+SUF+r')',t))
    emp=em.group(1) if em else None
    if emp:
        emp=re.sub(r'^(?:民族不限|免费住宿|工资周结|工资月结|男女不限|包吃包住|管吃管住|长期|急招|招聘|诚聘|招|地址|地点|位置)+[:：]?','',emp)
        e2=re.sub(r'^.*?(?:交叉口|路口|附近)','',emp)           # 「余杭路与三工路交叉口圆通总部」→「圆通总部」；「××附近酒店」剩「酒店」不是名字 → 整条不算雇主
        emp=e2 if len(e2)>=3 else None
        if emp: emp=re.sub(r'（.*$|\(.*$','',emp)              # 「乌市78小（西站河南庄附近）」→ 括号里是地点
        if emp and (re.search(r'^(?:招聘|招|聘)',emp) or len(emp)<3 or emp in ('乌鲁木齐','乌鲁木齐市')): emp=None
    r['employer']=emp
    loc=re.search(r'([一-龥]{2,12}(?:路|街|附近|小区|广场|商场|大厦|园区|校区|机场|车站|市场|开发区|一号院|城|楼)(?:附近)?)',t)
    r['location_phrase']=loc.group(1) if loc else None
    self_agent=bool(re.search(r'劳务派遣|人力资源(?:服务)?(?:有限)?公司|中介|人才(?:开发|服务)|外包公司|派遣公司',t))
    r['employer_from_location']=bool(r['employer'] is None and r['location_phrase'] and not self_agent)   # 群帖惯例：具体地点 + 直拨电话，没有公司名；雇主栏留空，卡片显示地点
    r['via_agent']=self_agent or bool(re.search('|'.join(AGENT_KW),t))
    # 岗位名/篮子：从篮子关键词出发取「××保安员」这种短语；关键词不在公司名里找（「君缘方舟安保公司 招手推车员」不是保安）
    tb=t.replace(r['employer'],'█'*len(r['employer'])) if (r['employer'] and re.search(r'公司|集团|有限',r['employer'])) else t   # 只遮公司名（「××安保公司」），「京东快递仓」这种地点式雇主不遮
    r['basket']=None; r['title']=None
    MOD=r'(?:兼职|全职|夜班|白班|临时|长期|京东|顺丰|圆通|中通|申通|韵达|极兔|美团|饿了么|麦当劳|肯德基|瑞幸|星巴克|机场|高铁|地铁|商场|小区|学校|医院|酒店|工厂|超市|仓库|物流|快递|川菜|中餐|火锅|烧烤|奶茶)?'
    for k,kws in BASKET_KW.items():
        for w in kws:
            m=re.search(MOD+re.escape(w)+r'(?:员|工|师傅|人员|岗)?',tb)   # 岗位名 = 允许的修饰词 + 篮子词 + 后缀；不再把前面 4 个任意字带进来（「河区京东快递」「须要干过服务员」）
            if m and (r['basket'] is None or m.start()<r.get('_tpos',1e9)): r['basket']=k; r['title']=m.group(0); r['_tpos']=m.start()
    r.pop('_tpos',None)
    if r['basket']=='food' and re.search(r'超市|便利店|商超|卖场',tb) and re.search(r'收银|店员|理货',r['title'] or ''): r['basket']='retail'   # 超市收银员归零售，不归餐饮
    if r['basket']=='retail' and re.search(r'库房|仓库|物流园',tb) and not re.search(r'门店|超市|便利店',tb): r['basket']='delivery'          # 库房理货是仓储，不是门店
    # 临时单：「今天下午需要」「预计干10天」「一次性」——记但不进篮子最低值
    r['temp']=bool(re.search(r'今天(?:上午|下午|晚上)?(?:需要|要|急)|明天(?:上班|需要|要)|预计干\s*\d+\s*天|只做\s*\d+\s*天|一次性|临时(?:工|用工|单)|当天结|活动兼职',t))
    # 城市：先看地址行（「地址：昌吉市榆树沟」），再看全文；文章模板头「乌鲁木齐优汇推荐」不能盖过地址行里的外地地名
    hin=city_hint['in'] if isinstance(city_hint,dict) else city_hint; hout=city_hint.get('out',[]) if isinstance(city_hint,dict) else []
    hsub=city_hint.get('suburb',[]) if isinstance(city_hint,dict) else []
    r['suburb']=any(h in t for h in hsub)   # 行政上属本市但离市区远（达坂城 80 km）：记 suburb，不进篮子最低值和首页
    addr=re.search(r'(?:地址|地点|位置|工作地点|上班地点|上班地址|所在地)[:：]?\s*([^\n]{2,40})',t); addr=addr.group(1) if addr else ''
    _in=re.compile('|'.join(map(re.escape,sorted(hin,key=len,reverse=True)))+'|北京时间'); addr2=_in.sub('',addr)   # 「北京路」是乌市的路
    if addr and any(h in addr2 for h in hout): r['location']=next(h for h in hout if h in addr2); r['in_city']=False
    elif addr and any(h in addr for h in hin): r['location']=next(h for h in hin if h in addr); r['in_city']=True
    else:
        t2=_in.sub('',t)
        r['location']=next((h for h in hin if h in t),None); r['in_city']=not any(h in t2 for h in hout)

def judge(r, days=180):
    reasons=[]
    if r.get('wage_value') is None: reasons.append('range_wage' if r.get('wage_range') else 'no_wage')
    u=r.get('wage_unit')
    if (u=='CNY/月' and not r.get('hours_month')) or (u=='CNY/天' and not r.get('hours_per_day')) or (u=='CNY/小时' and not (r.get('hours_per_day') or r.get('hours_text'))) or (u is None and not r.get('hours_month')):
        reasons.append('hours_partial' if (r.get('hours_per_day') or r.get('days_per_month')) else 'no_hours')   # 只差工时的一半：报告里单列，可打电话确认
    if r.get('via_agent') and not r.get('employer'): reasons.append('agent_unnamed')
    try:
        age=(datetime.date.today()-datetime.date.fromisoformat(r['posted_at'][:10])).days; r['age_days']=age
        if age>days: reasons.append('stale')
    except Exception: reasons.append('no_date')
    if not r.get('contact') and not (r.get('site_apply') and r.get('source_url')): reasons.append('no_contact')   # 微信文章链接不算联系方式
    if not r.get('source_url'): reasons.append('no_url')
    if not r.get('in_city'): reasons.append('off_city')
    if not r.get('basket'): reasons.append('off_basket')
    return reasons

def is_post(r): return bool(re.search(r'\d{3,5}',r['raw'])) and bool(r.get('basket') or re.search(r'招|聘|工资|薪',r['raw']))
def write_outputs(outdir, source, recs, log, days=180):
    junk=[r for r in recs if not is_post(r)]; recs=[r for r in recs if is_post(r)]
    # 同一来源当天重跑：只替换本来源的行，别的来源保留；prev = 上一轮本来源收了几条
    def keep_others(fn):
        fp=os.path.join(outdir,fn); mine=[]; others=[]
        if os.path.exists(fp):
            for l in open(fp,encoding='utf-8'):
                if json.loads(l).get('source')==source: mine.append(json.loads(l))
                else: others.append(l)
            open(fp,'w',encoding='utf-8').write(''.join(others))
        return mine
    prev=keep_others('jobs_raw.jsonl'); keep_others('rejected.jsonl')
    acc=[]; rej=[]; dist=collections.Counter()
    for r in recs:
        rs=judge(r, days); r['reasons']=rs
        (acc if not rs else rej).append(r)
        for x in rs: dist[x]+=1
    with open(os.path.join(outdir,'jobs_raw.jsonl'),'a',encoding='utf-8') as f:
        for r in acc: f.write(dump(r)+'\n')
    with open(os.path.join(outdir,'rejected.jsonl'),'a',encoding='utf-8') as f:
        for r in rej: f.write(dump(r)+'\n')
    rep=os.path.join(outdir,'report.md')
    key=lambda r:(r.get('employer') or r.get('location_phrase') or '', r.get('wage_value'), r.get('wage_unit'))
    lost=[r for r in prev if key(r) not in {key(a) for a in acc}]; gained=[r for r in acc if key(r) not in {key(p) for p in prev}]
    class _M:
        def __init__(s,f): s.f=f
        def write(s,t): s.f.write(mask(t))
    with open(rep,'a',encoding='utf-8') as _f:
        f=_M(_f)
        f.write(f"\n## {source} · {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n看了 **{len(recs)}** 条招工帖（另有 {len(junk)} 条模板/广告/碎片不计），收 **{len(acc)}** 条，拒 {len(rej)} 条" + (f"；上一轮收 {len(prev)} 条，本轮 +{len(gained)} −{len(lost)}" if prev else '') + "。\n\n拒绝原因分布：" + '、'.join(f'{k} {v}' for k,v in dist.most_common()) + "\n\n")
        if lost: f.write('比上一轮丢的：' + '；'.join(f"{r.get('title')} {r.get('employer') or r.get('location_phrase') or '—'} {r.get('wage_value')}" for r in lost) + '\n')
        if gained and prev: f.write('比上一轮新进的：' + '；'.join(f"{r.get('title')} {r.get('employer') or r.get('location_phrase') or '—'} {r.get('wage_value')}" for r in gained) + '\n\n')
        part=[r for r in rej if r['reasons']==['hours_partial']]
        if part:
            f.write(f'只差工时的一半（有月休/班次之一，打电话可确认）{len(part)} 条：\n' + ''.join(f"- {r.get('title')} | {r.get('employer') or '—'} | {r.get('wage_value')} {r.get('wage_unit')} | 已知 {r.get('hours_text')} | {r.get('contact') or ''}\n" for r in part[:20]) + '\n')
        nc=[r for r in rej if r['reasons']==['no_contact']]
        if nc: f.write(f'只缺联系方式（文章里要「加号主微信」）{len(nc)} 条：' + '；'.join(f"{r.get('title')} {r.get('employer') or '—'} {r.get('wage_value')}" for r in nc[:12]) + '\n\n')
        by=collections.defaultdict(lambda:[0,0])
        for r in recs: by[r.get('account','')][0]+=1
        for r in acc: by[r.get('account','')][1]+=1
        f.write('按来源账号：' + '、'.join(f'{k or "?"} 看 {v[0]} 收 {v[1]}' for k,v in sorted(by.items(), key=lambda x:-x[1][0])) + '\n\n')
        if acc:
            f.write('| 篮子 | 岗位 | 雇主 | 工资 | 工时 | 月工时 | 时薪 | 发帖 | 来源 |\n|---|---|---|---|---|---|---|---|---|\n')
            for r in acc: f.write(f"| {r.get('basket')} | {r.get('title')} | {r.get('employer') or ('地点 '+(r.get('location_phrase') or '—'))}{'（中介转）' if r.get('via_agent') else ''}{'（临时单）' if r.get('temp') else ''} | {r.get('wage_value')} {r.get('wage_unit')} | {r.get('hours_text')} {r.get('hours_flag','')} | {r.get('hours_month') or '—'} | {r.get('hourly') or '—'} | {r.get('posted_at')} | {r.get('account','')} |\n")
        f.write('\n过程：\n' + '\n'.join('- '+l for l in log) + '\n')
    print(f'{source}: 看了 {len(recs)}，收 {len(acc)}，拒 {len(rej)}；分布 {dict(dist)}；报告 {rep}')

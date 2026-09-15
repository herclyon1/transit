#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源②（邦美蜀）：Việc Làm Tốt（Chợ Tốt 招聘板，蓝领为主；公开 API gateway.chotot.com/v1/public/ad-listing，region_v2=9053 area_v2=905301）。
  python3 pipeline/cost/sources/vieclamtot.py buon_ma_thuot --from-jsonl cost/data/raw/buon_ma_thuot/20260915/jobs.jsonl   # 已抓的 363 条正文过判据
  python3 pipeline/cost/sources/vieclamtot.py buon_ma_thuot --fetch [--pages 8]                                           # 现抓（列表 + 逐条正文）
判据同 PLAN-v2（common.judge）：确数工资 + 正文写明班次/工时 + 联系方式（站内投递 site_apply + 正文电话若有）+ ≤180 天。
越南语抽取在本文件：工资 20k/h · 300.000 VNĐ/ngày · 6tr · 9,5 triệu · 6.000.000đ/tháng；区间 8–11 triệu / Từ … đến … / Đến N（列表的 Đến 是上限，不算确数）；
班次 8h–13h · 18H00–6H00 · 06:00 – 16:30 · từ 11h đến 24h（多段是可选班，取第一段）；Nghỉ giữa ca 1 tiếng/60p 扣；
天数 tháng nghỉ 1 ngày → 29 · nghỉ 1 ngày/tuần · nghỉ Chủ nhật · 6 ngày/tuần · Thứ 2 – Thứ 7 → 26 · tất cả các ngày → 30。
"""
import re, os, sys, json, time, argparse, datetime, subprocess
from common import Rec, write_outputs, mask
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
BASKET={'security':['bảo vệ','giữ xe'],'food':['phục vụ','phụ bếp','bếp','pha chế','barista','chạy bàn','rửa chén','nhà hàng','quán','cà phê','cafe','coffee','trà sữa'],
        'retail':['bán hàng','bán quần áo','nhân viên bán','thu ngân','siêu thị','cửa hàng','shop','tạp hóa','winmart','bách hóa','circle k','gs25'],
        'delivery':['giao hàng','shipper','kho','phân loại','đóng gói','tài xế giao','bưu','j&t','ghn','viettel post','be ','grab'],
        'factory':['công nhân','lao động phổ thông','sản xuất','xưởng','phụ việc','phụ cơ khí','phụ hồ','thợ phụ'],
        'cleaning':['tạp vụ','vệ sinh','dọn dẹp','lao công'],'home':['giúp việc','trông trẻ','chăm sóc người'],
        'chain':['kfc','lotteria','jollibee','highlands','the coffee house','circle k','mcdonald']}
N=r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d)?)'
def num(s):   # 300.000 / 6.000.000 / 9,5 → 数
    s=s.replace(' ','')
    if re.fullmatch(r'\d{1,3}([.,]\d{3})+',s): return float(re.sub(r'[.,]','',s))
    return float(s.replace(',','.'))
def shift_h(a,b,suf=None):   # 'h'/':' 钟点 → 小时数；「7h tối」= 19h
    h1,m1,h2,m2=int(a[0]),int(a[1] or 0),int(b[0]),int(b[1] or 0)
    t1=h1+m1/60; t2=h2+m2/60
    if suf in ('tối','chiều','đêm') and t2<=12: t2+=12
    if t2<=t1: t2+=24
    return t1, t2
SHIFT=re.compile(r'(?<!\d)(\d{1,2})(?:h|H|giờ|:)(\d{2})?(?:h|H)?[ \t]*(?:trưa|sáng|chiều|tối|đêm)?[ \t]*(?:-|–|—|~|đến|tới|>)[ \t]*(\d{1,2})(?:h|H|giờ|:)(\d{2})?(?:h|H)?[ \t]*(trưa|sáng|chiều|tối|đêm)?')
def extract_vi(r):
    t=r['raw']; low=t.lower()
    wage=None; unit=None; rng=False
    # 区间：8 – 11 triệu / 40k – 55k / từ … đến …
    if re.search(r'\d\s*(?:triệu|tr|k|\.000)?\s*(?:-|–|—|~)\s*\d+[.,]?\d*\s*(?:triệu|tr|k|\.000)\b',low) or re.search(r'từ\s*\d[\d.,]*\s*(?:triệu|tr|k|đ|vnđ)\b[^\n]{0,15}đến\s*\d',low): rng=True   # 「từ 7h30 sáng đến 7h tối」是班次不是区间
    m=re.search(N+r'\s*k\s*/\s*(?:h|giờ)\b',low)    # 「qua 23h30 1h/25k」是加班费率，不算
    if m: wage=num(m.group(1))*1000; unit='VND/小时'
    else:
        m=re.search(N+r'\s*(?:đ|vnđ|vnd|đồng)?\s*/\s*(?:h|giờ)\b',low)
        if m and num(m.group(1))>=10000: wage=num(m.group(1)); unit='VND/小时'
    if wage is None:
        m=re.search(N+r'\s*(?:đ|vnđ|vnd|đồng)?\s*/\s*ngày\b',low) or re.search(N+r'\s*k\s*/\s*ngày\b',low)
        if m: v=num(m.group(1)); wage=v*1000 if v<10000 else v; unit='VND/天'
    if wage is None:
        # 一帖里所有的月薪数：≥2 个不同的 = 多岗位帖（服务员 4.5tr + 保安 6tr），配不上班次，记 ambiguous
        allm=[num(x) for x in re.findall(r'(?:lương|thu nhập)[^\n\d]{0,25}?(\d{1,2}(?:[.,]\d{3}){2}|\d{1,2}(?:[.,]\d)?(?=\s*(?:triệu|tr)\b))',low)]
        allm=set(v*1e6 if v<1000 else v for v in allm)
        m=(re.search(r'(?:lương|thu nhập|mức lương)([^\n\d]{0,25}?)'+N+r'\s*(?:triệu|tr)\b(?!\s*(?:-|–|—|~|đến))',low)
           or re.search(r'(?:lương|thu nhập)([^\n\d]{0,25}?)(\d{1,2}[.,]\d{3}[.,]\d{3})\s*(?:đ|vnđ|vnd)?(?:\s*/\s*tháng)?',low))
        if m and re.search(r'trên|từ|khoảng|lên (?:đến|tới)|tới|đến|có thể|đạt',m.group(1)): m=None    # 「có thể đạt trên 15tr」不是确数
        if m and not re.search(r'(?:-|–|—|~|đến)\s*'+re.escape(m.group(2)),low) and not rng:
            v=num(m.group(2)); wage=v*1e6 if v<1000 else v; unit='VND/月'
            if len(allm)>=2: r['ambiguous']=True; wage=None; unit=None
    # 抽到的数是区间端点
    if wage is not None and m:
        cand=m.group(m.lastindex)
        if re.search(r'(?<![\d.,])'+re.escape(cand)+r'\s*(?:triệu|tr|k|đ|vnđ)?\s*(?:-|–|—|~|đến)\s*\d|\d\s*(?:triệu|tr|k)?\s*(?:-|–|—|~|đến|từ)\s*'+re.escape(cand)+r'(?![\d])',low): wage=None; unit=None; rng=True
    if wage is not None and unit=='VND/月' and re.search(r'lương cứng|lương cơ bản|cố định\s*\+|\+\s*(?:hoa hồng|thưởng|doanh số)',low): wage=None; unit=None; rng=True   # 底薪+提成不是确数
    r['wage_value']=wage; r['wage_unit']=unit; r['wage_range']=bool(rng and wage is None) or ('thương lượng' in low or 'thỏa thuận' in low)
    r['probation']=bool(wage is not None and re.search(r'thử việc[^\n]{0,20}'+str(int(wage)),low))
    # 班次
    hours=[]; hpd=None; dpm=None; flag=''
    segs=list(SHIFT.finditer(t))
    if segs:
        # 同一天的两段（8h–13h / 13h–16h、sáng 7h30–11h30 chiều 13h30–17h30：下一段在上一段结束后 ≤4h 内开始）求和；否则是可选班次，取第一段
        s0=segs[0]; t1,t2=shift_h((s0.group(1),s0.group(2)),(s0.group(3),s0.group(4)),s0.group(5)); hpd=t2-t1; hours.append(s0.group(0).strip()); end=t2
        for sg in segs[1:]:
            a,b=shift_h((sg.group(1),sg.group(2)),(sg.group(3),sg.group(4)),sg.group(5))
            if a>=end and a-end<=4 and hpd+(b-a)<=14: hpd+=b-a; end=b; hours.append(sg.group(0).strip())
            else: break
        hpd=round(hpd,1)
        mb=re.search(r'nghỉ\s*(?:giữa\s*ca|trưa)[^\n\d]{0,10}(\d{1,3})\s*(tiếng|phút|p\b|h\b)',low)
        if mb: b=float(mb.group(1))/(60 if mb.group(2).startswith('p') else 1); hpd=round(hpd-b,1); flag+=f'-{b:g}h nghỉ '
        if len(segs)>len(hours): flag+='多班可选 '
    m=re.search(r'(\d{1,2})\s*(?:tiếng|giờ)\s*/\s*ngày|(\d{1,2})\s*tiếng\s*(?:linh hoạt|/\s*ca)|ca\s*(?:tối|sáng|chiều)?\s*(\d{1,2})\s*tiếng',low)
    if not hpd and m: hpd=float(next(g for g in m.groups() if g)); hours.append(m.group(0))
    if re.search(r'tháng nghỉ\s*(\d)\s*ngày|nghỉ\s*(\d)\s*ngày\s*/\s*tháng',low): n=int(next(g for g in re.search(r'tháng nghỉ\s*(\d)\s*ngày|nghỉ\s*(\d)\s*ngày\s*/\s*tháng',low).groups() if g)); dpm=30-n; hours.append(f'tháng nghỉ {n} ngày')
    elif re.search(r'nghỉ\s*1\s*ngày\s*/\s*tuần|nghỉ chủ nhật|nghỉ cn\b|6\s*ngày\s*/\s*tuần|thứ\s*2\s*(?:-|–|—|đến)\s*thứ\s*7|off\s*1\s*ngày',low): dpm=26; hours.append('nghỉ 1 ngày/tuần')
    elif re.search(r'tất cả các ngày|làm cả tuần|7\s*ngày\s*/\s*tuần|không nghỉ',low): dpm=30; hours.append('tất cả các ngày')
    elif re.search(r'nghỉ\s*2\s*ngày\s*/\s*tuần|thứ\s*2\s*(?:-|–|—|đến)\s*thứ\s*6',low): dpm=22; hours.append('nghỉ 2 ngày/tuần')
    r['hours_text']=' / '.join(dict.fromkeys(hours)); r['hours_per_day']=hpd; r['days_per_month']=dpm; r['hours_flag']=flag.strip()
    r['hours_month']=round(hpd*dpm) if (hpd and dpm) else None
    if unit=='VND/小时': r['hourly']=wage
    elif unit=='VND/天' and hpd: r['hourly']=round(wage/hpd)
    elif unit=='VND/月' and r['hours_month']: r['hourly']=round(wage/r['hours_month'])
    else: r['hourly']=None
    ph=re.findall(r'(?<!\d)(?:0|\+?84)\d{9}(?!\d)',t)
    r['contact']=mask(ph[0]) if ph else ('站内投递' if r.get('site_apply') else None)
    r['temp']=bool(re.search(r'thời vụ|ngắn hạn|theo ngày|1\s*ngày\b|sự kiện|event',low)) and not re.search(r'dài hạn|lâu dài',low)
    r['basket']=None; r['title']=None; hay=(r.get('article_title','')+' '+t).lower()
    for k,kws in BASKET.items():
        for w in kws:
            i=hay.find(w)
            if i>=0 and (r['basket'] is None or i<r.get('_tpos',1e9)): r['basket']=k; r['title']=w; r['_tpos']=i
    r.pop('_tpos',None)
    if r['basket']=='chain' and re.search(r'phục vụ|bếp|pha chế',hay): r['basket']='food'
    r['via_agent']=bool(re.search(r'cung ứng (?:nhân lực|lao động)|công ty nhân lực|tuyển dụng hộ',low))
    r['suburb']=False
def to_rec(d, city, today):
    raw=f"{d.get('title','')}\n{d.get('company') or d.get('account_name') or ''}\n{d.get('location','')}\n{d.get('body','')}"
    r=Rec(city=city, source='vieclamtot', source_url=d['url'], fetched_at=d.get('fetched_at') or today.isoformat(), posted_at=d.get('posted_at',''), raw=raw,
          account='Việc Làm Tốt', article_title=d.get('title',''), site_apply=True, employer=(d.get('company') or d.get('account_name') or None),
          location=d.get('ward') or d.get('location'), in_city=True, employer_from_location=False)
    if not d.get('company_ad'): r['employer']=r['employer'] or None
    extract_vi(r)
    # 列表的结构化工资：min==max 才算确数（Đến N 是上限）
    if r['wage_value'] is None and d.get('min_salary') and d.get('min_salary')==d.get('max_salary'):
        st=d.get('salary_type'); r['wage_value']=float(d['min_salary']); r['wage_unit']={1:'VND/小时',2:'VND/天',3:'VND/月'}.get(st,'VND/月'); r['wage_range']=False
        r['hourly']= r['wage_value'] if st==1 else (round(r['wage_value']/r['hours_per_day']) if st==2 and r.get('hours_per_day') else (round(r['wage_value']/r['hours_month']) if st==3 and r.get('hours_month') else None))
    return r
def fetch(pages, cache):
    out=[]
    for o in range(0,pages*50,50):
        url=f'https://gateway.chotot.com/v1/public/ad-listing?cg=13000&region_v2=9053&area_v2=905301&limit=50&o={o}&st=s,k'
        j=subprocess.run(['curl','-s','-m','30','-A',UA,'-H','Accept: application/json','-H','Origin: https://www.vieclamtot.com','-H','Referer: https://www.vieclamtot.com/',url],capture_output=True,text=True).stdout
        try: ads=json.loads(j).get('ads',[])
        except Exception: break
        if not ads: break
        for a in ads:
            lid=a.get('list_id'); cf=os.path.join(cache,f'{lid}.json')
            if os.path.exists(cf): d=json.load(open(cf,encoding='utf-8'))
            else:
                dj=subprocess.run(['curl','-s','-m','30','-A',UA,'-H','Accept: application/json',f'https://gateway.chotot.com/v1/public/ad-listing/{lid}'],capture_output=True,text=True).stdout
                try: ad=json.loads(dj).get('ad',{})
                except Exception: ad={}
                d={'list_id':lid,'url':f"https://www.vieclamtot.com/viec-lam-thanh-pho-buon-ma-thuot-dak-lak/{lid}.htm",'title':a.get('subject',''),'company':a.get('company_name') or (a.get('account_name') if a.get('company_ad') else None),
                   'account_name':a.get('account_name'),'company_ad':bool(a.get('company_ad')),'location':a.get('location') or ad.get('location'),'ward':a.get('ward_name'),
                   'posted_at':datetime.date.fromtimestamp((a.get('list_time') or 0)/1000).isoformat(),'salary_display':a.get('salary_display'),'min_salary':a.get('min_salary'),'max_salary':a.get('max_salary'),'salary_type':a.get('salary_type'),
                   'body':ad.get('body') or a.get('body') or '','fetched_at':datetime.date.today().isoformat()}
                json.dump(d,open(cf,'w',encoding='utf-8'),ensure_ascii=False); time.sleep(1.0)
            out.append(d)
        time.sleep(1.2)
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--from-jsonl'); ap.add_argument('--fetch',action='store_true'); ap.add_argument('--pages',type=int,default=8); ap.add_argument('--days',type=int,default=180); a=ap.parse_args()
    today=datetime.date.today(); outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',a.city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    recs=[]; log=[]
    if a.from_jsonl:
        rows=[json.loads(l) for l in open(a.from_jsonl,encoding='utf-8')]; log.append(f'{a.from_jsonl}：{len(rows)} 行')
        for d in rows:
            if (d.get('body') or '').strip(): recs.append(to_rec(d,a.city,today))
    if a.fetch:
        cache=os.path.join(outdir,'ads'); os.makedirs(cache,exist_ok=True); rows=fetch(a.pages,cache); log.append(f'API 列表 {a.pages} 页：{len(rows)} 条')
        for d in rows:
            if (d.get('body') or '').strip(): recs.append(to_rec(d,a.city,today))
    write_outputs(outdir,'vieclamtot',recs,log,a.days)
if __name__=='__main__': main()

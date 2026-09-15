#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
来源①（大阪）：ハローワークインターネットサービス 求人情報検索（hellowork.mhlw.go.jp/kensaku/GECA110010.do）。
  python3 pipeline/cost/sources/hellowork.py osaka [--pages 3] [--query コンビニ]
官方公共就业服务，用人单位提交、法律要求写工资工时：列表页每条就带 賃金（時給 min〜max）、就業時間（1）(2)(3)、休日、事業所名、就業場所、求人番号、受付年月日。
只搜 大阪府 × パート（ippanCKBox=2）× 篮子关键词；就業場所 含「大阪市」才收。確数 = 時給 min == max；区间取下限记 wage_floor（用户 09-15 裁定：求人票的幅度是结构性的，下限就是起薪）；班次取（1），多段是可选班次标 多班可选。
联系方式：ハローワーク窓口/オンライン自主応募（site_apply），链接用 求人票（action=kyujinhyoBtn&kJNo=…）。请求间隔 1.5–3 秒，一轮 ≤ --pages 页/词。
"""
import re, os, sys, json, time, html, random, argparse, datetime, subprocess
from common import Rec, write_outputs, mask
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
BASE='https://www.hellowork.mhlw.go.jp/kensaku/GECA110010.do'
QUERIES={'tokyo':None,'osaka':[('security','警備'),('food','ホールスタッフ'),('food','調理補助'),('retail','コンビニ'),('retail','レジ'),('retail','品出し'),('delivery','倉庫'),('delivery','仕分け'),('delivery','配達'),
                  ('factory','製造'),('factory','軽作業'),('cleaning','清掃'),('chain','マクドナルド'),('chain','ケンタッキー'),('chain','セブンイレブン'),('chain','スターバックス')]}   # 自由词只能单词（带空格返回 0 件）
CHAIN_CO=re.compile(r'マクドナルド|ケンタッキー|日本ＫＦＣ|スターバックス|セブン.イレブン|セブンイレブン|ファミリーマート|ローソン|すき家|吉野家|ゼンショー|松屋')
PREF={'osaka':'27','tokyo':'13'}; CITY_STR={'osaka':'大阪市','tokyo':'東京都'}
# 东京：就業場所要在 23 区内（「東京都○○区」）；市部（八王子市等）不算市区
IN_CITY={'osaka':lambda place:'大阪市' in place,'tokyo':lambda place:bool(re.search(r'東京都[^\s、,]{1,4}区',place))}
BASKET_KW={'security':['警備','守衛','保安'],'food':['ホール','接客','調理','キッチン','飲食','レストラン','カフェ','居酒屋','厨房'],'retail':['コンビニ','レジ','品出し','スーパー','販売','店舗スタッフ'],
           'delivery':['倉庫','仕分け','ピッキング','配達','配送','宅配','荷受'],'factory':['製造','軽作業','工場','梱包','組立'],'cleaning':['清掃','ハウスクリーニング','クリーンスタッフ','管理員'],'home':['家事代行','ベビーシッター','家政婦'],
           'chain':['マクドナルド','ケンタッキー','セブン','ファミリーマート','ローソン','スターバックス','すき家','吉野家']}
def post(data, jar):
    cmd=['curl','-s','-m','40','-A',UA,'-c',jar,'-b',jar,'-e',BASE,'-X','POST',BASE]
    for k,v in data: cmd+=['--data-urlencode',f'{k}={v}']
    return subprocess.run(cmd,capture_output=True,text=True).stdout
def text(h):
    t=re.sub(r'<script.*?</script>|<style.*?</style>','',h,flags=re.S); t=html.unescape(re.sub(r'<[^>]+>','|',t)); return re.sub(r'[\s|]+','|',t)
def parse_list(h):
    out=[]
    parts=re.split(r'<table class="kyujin[^"]*">',h)[1:]     # 每条求人一个 table，里面还套小 table，按下一条的开头切
    for blk in parts:
        t=text(blk)
        g=lambda k,n=r'([^|]+)': (re.search(k+r'\|'+n,t) or [None,''])[1].strip()
        kj=g(r'求人番号',r'(\d{5}-\d{8})'); 
        if not kj: continue
        rx=lambda pat: (re.search(pat,t) or [None,''])[1].strip()
        d={'kjno':kj,'posted':rx(r'受付年月日\|：(\d{4}年\d{1,2}月\d{1,2}日)'),'deadline':rx(r'紹介期限日\|：(\d{4}年\d{1,2}月\d{1,2}日)'),
           'kind':rx(r'閲覧済\|(?:新着\|)?([^|]{2,14})\|[^|]{2,14}\|(?:大阪府|[^|]*[都道府県])'),   # 雇用形態 | 求人区分（フル/パート） | 事業所所在地
           'title':g(r'職種'),'desc':(re.search(r'仕事の内容\|(.*?)\|事業所名',t) or [None,''])[1].replace('|','\n'),
           'company':(re.search(r'事業所名\|(.*?)\|就業場所',t) or [None,''])[1].replace('|','').replace('画像あり',''),'place':g(r'就業場所'),
           'wage':g(r'賃金\|（手当等を含む）',r'([\d,]+円〜[\d,]+円)'),'hours':(re.search(r'就業時間\|(.*?)\|休日',t) or [None,''])[1].replace('|',' '),
           'holiday':(re.search(r'休日\|(.*?)\|求人番号',t) or [None,''])[1].replace('|',' '),
           'url':f"https://www.hellowork.mhlw.go.jp/kensaku/GECA110010.do?screenId=GECA110010&action=kyujinhyoBtn&kJNo={kj.replace('-','')}&kJKbn=1"}
        m=re.search(r'求人数：(\d+)名',t); d['n']=int(m.group(1)) if m else None
        out.append(d)
    return out
def jdate(s):
    m=re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日',s or ''); return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''
def to_rec(d, city, basket_hint, today):
    raw=f"{d['title']}\n{d['company']}\n{d['place']}\n{d['kind']} 求人数 {d.get('n') or '?'}\n賃金 {d['wage']}\n就業時間 {d['hours']}\n休日 {d['holiday']}\n{d['desc']}"
    r=Rec(city=city, source='hellowork', source_url=d['url'], fetched_at=today.isoformat(), posted_at=jdate(d['posted']), raw=raw, account='求人番号 '+d['kjno'], article_title=d['title'],
          site_apply=True, employer=d['company'] or None, location=d['place'], in_city=IN_CITY[city](d['place']), employer_from_location=False, suburb=False, kjno=d['kjno'], kind=d['kind'])
    m=re.search(r'([\d,]+)円〜([\d,]+)円',d['wage']); lo=int(m.group(1).replace(',','')) if m else None; hi=int(m.group(2).replace(',','')) if m else None
    hourly_unit=True                            # 本适配器只搜 パート（ippanCKBox=2）= 時給；フル は月給，以后再开
    # 用户 09-15 裁定：ハローワーク的区间是结构性的（同一岗位按经验/班次给幅度，下限 = 新人该班次的保底价），取下限入库标「起薪（求人票下限）」；只对 hellowork 生效，中国来源的区间照旧拒
    if lo and hi: r['wage_value']=float(lo); r['wage_unit']='JPY/小时' if hourly_unit else 'JPY/月'; r['wage_range']=False; r['wage_floor']=(lo!=hi); r['wage_hi']=float(hi)
    else: r['wage_value']=None; r['wage_unit']=None; r['wage_range']=False
    segs=re.findall(r'（(\d)）(\d{1,2})時(\d{2})分〜(\d{1,2})時(\d{2})分',d['hours'])
    hpd=None; hours=[]
    if segs:
        a=segs[0]; t1=int(a[1])+int(a[2])/60; t2=int(a[3])+int(a[4])/60; hpd=round((t2-t1) if t2>t1 else (t2+24-t1),1); hours.append(f'（{a[0]}）{a[1]}:{a[2]}〜{a[3]}:{a[4]}')
    flag=('多班可选 ' if len(segs)>1 else '')+('交替制 ' if '交替制' in d['hours'] else '')
    m=re.search(r'年間休日数：(\d+)日',d['holiday']); dpm=None
    if m: dpm=round((365-int(m.group(1)))/12)           # パート没写年間休日数的不猜天数：時給直接就是时薪，天数在求人票的「週所定労働日数」里
    # 就業時間没有时刻段（只写「交替制（シフト制）」等）时，hours_text 取就業時間原句而不是休日那行（maa 09-15：スシロー北加賀屋店/菜花野 抓成了休日）
    shift_only=re.sub(r'\s+',' ',d['hours']).strip() if not segs else ''
    core=hours or ([shift_only] if shift_only else [])
    r['hours_text']=' / '.join(core+([d['holiday']] if (d['holiday'] and core) else [])); r['hours_per_day']=hpd; r['days_per_month']=dpm; r['hours_flag']=flag.strip(); r['hours_month']=round(hpd*dpm) if (hpd and dpm) else None
    r['hourly']=r['wage_value'] if r['wage_unit']=='JPY/小时' else (round(r['wage_value']/r['hours_month']) if (r['wage_unit']=='JPY/月' and r['hours_month']) else None)
    # 就業時間为空（菜花野那种）：hours_text 留空 → judge 记 no_hours 进 rejected（「帖子写明工时/班次」门槛）；只有休日那行不算工时
    r['contact']='ハローワーク窓口/オンライン自主応募'
    r['via_agent']='派遣' in d['kind'] or '請負' in d['kind'] or bool(re.search(r'派遣|請負',d['company']))
    # 篮子：连锁按事業所名（日本マクドナルド 的「フロア担当」就是连锁锚点）；其余先看職種名，再看仕事の内容；搜索词不当篮子依据（搜「コンビニ」会带出办公室岗）
    r['basket']=None; r['title']=d['title'][:20]
    if CHAIN_CO.search(d['company']): r['basket']='chain'
    else:
        for hay in (d['title'], d['desc']):
            for k,kws in BASKET_KW.items():
                if k=='chain': continue
                for w in kws:
                    i=hay.find(w)
                    if i>=0 and (r['basket'] is None or i<r.get('_tpos',1e9)): r['basket']=k; r['_tpos']=i
            if r['basket']: break
        r.pop('_tpos',None)
    if re.search(r'事務|経理|営業|受付|管理者|店長候補|エンジニア|看護|薬剤|介護|保育|電話交換|ドライバー',d['title']): r['basket']=None      # 白领/专业岗不在篮子里
    r['temp']=bool(re.search(r'短期|単発|季節|臨時',d['title']+' '+d['desc']))
    return r
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('city'); ap.add_argument('--pages',type=int,default=3); ap.add_argument('--query',action='append'); ap.add_argument('--days',type=int,default=180); a=ap.parse_args()
    city=a.city; today=datetime.date.today(); outdir=os.path.join(os.path.dirname(__file__),'..','..','..','cost','data','raw',city,today.strftime('%Y%m%d')); os.makedirs(outdir,exist_ok=True)
    jar=os.path.join(outdir,'.hw.cookies'); open(jar,'a').close()
    subprocess.run(['curl','-s','-m','30','-A',UA,'-c',jar,'-b',jar,'-o','/dev/null',BASE+'?action=initDisp&screenId=GECA110010'])
    base=[('kjKbnRadioBtn','1'),('todohukenHidden',PREF[city]),('screenId','GECA110010'),('kyujinkensu','0'),('searchClear','0'),('summaryDisp','false'),('searchInitDisp','0'),('preCheckFlg','false'),('freeWordRadioBtn','1'),('ippanCKBox','2')]
    recs=[]; log=[]; seen=set(); raw_all=[]
    qs=[(None,q) for q in a.query] if a.query else (QUERIES[city] or QUERIES['osaka'])   # 东京用同一套 16 个篮子词
    for bk,q in qs:
        h=post(base+[('freeWordInput',q),('searchBtn',' 検索する'),('action','searchBtn')],jar); time.sleep(random.uniform(1.5,3))
        t=text(h); m=re.search(r'検索結果\|([\d,]+)件',t); total=m.group(1) if m else '?'
        items=parse_list(h); n_in=0
        for p in range(2,a.pages+1):
            if len(items)<30*(p-1): break
            hid=re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"',h)
            h=post([(k,html.unescape(v)) for k,v in hid]+[('kjKbnRadioBtn','1'),('fwListNaviBtnNext','次へ＞'),('ippanCKBox','2'),('freeWordInput',q),('freeWordRadioBtn','1')],jar); time.sleep(random.uniform(1.5,3))
            items+=parse_list(h)
        for d in items:
            if d['kjno'] in seen: continue
            seen.add(d['kjno']); raw_all.append(d)
            if not IN_CITY[city](d['place']): continue
            n_in+=1; recs.append(to_rec(d,city,bk,today))
        log.append(f'搜「{q}」（パート・{ {"osaka":"大阪府","tokyo":"東京都"}[city] }）：{total} 件，取 {len(items)} 条，其中就業場所在{ {"osaka":"大阪市","tokyo":"23 区"}[city] } {n_in} 条')
    with open(os.path.join(outdir,'hellowork_list.jsonl'),'w',encoding='utf-8') as f:
        for d in raw_all: f.write(mask(json.dumps(d,ensure_ascii=False))+'\n')
    write_outputs(outdir,'hellowork',recs,log,a.days)
if __name__=='__main__': main()

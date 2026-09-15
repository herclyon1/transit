#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""大阪「居住等级」三维度评分（草案，不写回 tiers.geojson）
   python3 pipeline/osaka/tiers_score.py            → osaka/data/tiers_scored.json
   python3 pipeline/osaka/tiers_score.py --md       → 顺带打印 README 用的对照表

三维度，每块（tiers.geojson 104 块）各出一个 S–D，再取三项平均当「拟合级」；来源、年份、原始值都写进输出。
  治安  刑法犯認知件数 ÷ 常住人口 ×1000（大阪府警 R7 表9 ÷ 令和7年国調速報），府内 72 市区町村五分位 → crime_rate_r07.json 已算，块继承所在区/市。
  便利  ① 门到枢纽分钟：块内 200 m 网格采样，每点 = 步行到最近站（直线×1.3 ÷ 80 m/分）+ 该站到最近枢纽（reach.json t_default，不含特急券），块取中位；
        ② 800 m 内超市数：OSM shop=supermarket（Overpass，ODbL），每采样点数 800 m 圈内家数，块取中位。两项各按 104 块五分位，再平均。
  环境  洪水浸水想定区域（想定最大規模）里浸水深 ≥0.5 m 的采样点占比（国土数値情報 A31a 河川単位 2025 年度版：近畿整備局 5 条国管理河川 + 大阪府管理/中小河川），0% S、<10% A、<30% B、<60% C、≥60% D。
不写回 geojson：等用户拍板阈值和维度后再落。"""
import json, os, sys, math, statistics, zipfile, urllib.request
from collections import defaultdict
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.join(HERE,'..','..')
D=os.path.join(ROOT,'osaka','data'); RAW=os.path.join(D,'raw')
STEP=200          # 采样网格 m
DETOUR=1.3        # 直线→道路距离系数（假设，无出处；不動産公正競争規約只规定 80 m/分 按道路距离）
WALK_M_PER_MIN=80 # 不動産の表示に関する公正競争規約施行規則 第9条(9)：道路距離80mにつき1分
SHOP_R=800        # 超市圈半径 m ≈ 10 分步行
NEAR_K=5          # 每采样点看最近 K 站，取 步行+乘车 最小
LAT0=34.65; KX=111320*math.cos(math.radians(LAT0)); KY=110574
GRADES=['D','C','B','A','S']
A31A='https://nlftp.mlit.go.jp/ksj/gml/data/A31a/A31a-25/'
FLOOD_ZIPS={'A31a-25_86_10_GEOJSON.zip':['8606030001','8606040001','8606040073','8606040167','8606040371'],  # 近畿地方整備局：大和川(含石川/曽我川/佐保川) 淀川(含宇治川/瀬田川) 猪名川(含藻川) 桂川 木津川——A31_R7_datalist 里対象メッシュ含 5135/5235 的国管理河川；紀の川/野洲川/由良川不到大阪府的块
            'A31a-25_27_10_GEOJSON.zip':None,   # 大阪府管理河川 全部
            'A31a-25_27_20_GEOJSON.zip':None}   # 大阪府 中小河川 全部
SRC={'safety':'大阪府警察「令和7年中の犯罪統計（確定値）」表9 刑法犯罪種及び手口別発生市区町村別認知件数 ÷ 令和7年国勢調査人口速報集計（2025-10-01）；osaka/data/crime_rate_r07.json',
     'hub':'osaka/data/reach.json（大阪地铁/JR/私铁官方所要時間建图，2026-09-16；t_default 不含特急券）+ 步行 80 m/分（不動産公正競争規約施行規則 §9(9)）× 直线 1.3 系数（假设）',
     'shop':'OpenStreetMap shop=supermarket（Overpass API，osm base 见 raw/osm/supermarkets_overpass.json 的 osm3s.timestamp_osm_base，ODbL）',
     'flood':'国土数値情報 A31a 洪水浸水想定区域（河川単位）2025 年度版 想定最大規模：近畿地方整備局 A31a-25_86（大和川・淀川・猪名川・桂川・木津川）+ 大阪府 A31a-25_27_10（府管理河川）+ A31a-25_27_20（中小河川）（国交省，CC BY 4.0；浸水深ランク A31a_205：2 = 0.5–3 m，3 = 3–5 m，4 = 5–10 m）https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A31a-2025.html ；一次メッシュ版 A31b-25 的 5235 缺淀川本川（十三/京橋/御幣島查无多边形），故不用'}

def xy(lon,lat): return ((lon-135.5)*KX,(lat-LAT0)*KY)
def pip(x,y,ring):
    inside=False; n=len(ring); j=n-1
    for i in range(n):
        xi,yi=ring[i]; xj,yj=ring[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: inside=not inside
        j=i
    return inside
def in_poly(x,y,poly):  # poly = [outer, hole, hole...] 已投影
    if not pip(x,y,poly[0]): return False
    return not any(pip(x,y,h) for h in poly[1:])
def project(geom):
    polys=geom['coordinates'] if geom['type']=='MultiPolygon' else [geom['coordinates']]
    return [[[xy(*c[:2]) for c in ring] for ring in p] for p in polys]
def bbox(polys):
    xs=[c[0] for p in polys for c in p[0]]; ys=[c[1] for p in polys for c in p[0]]
    return min(xs),min(ys),max(xs),max(ys)
def area_km2(polys):
    a=0
    for p in polys:
        for k,ring in enumerate(p):
            s=sum(ring[i][0]*ring[(i+1)%len(ring)][1]-ring[(i+1)%len(ring)][0]*ring[i][1] for i in range(len(ring)))/2
            a+=abs(s)*(-1 if k else 1)
    return a/1e6
def samples(polys,step=STEP):
    x0,y0,x1,y1=bbox(polys); pts=[]
    while True:
        xs=[x0+step/2+i*step for i in range(int((x1-x0)/step)+1)]; ys=[y0+step/2+i*step for i in range(int((y1-y0)/step)+1)]
        pts=[(x,y) for x in xs for y in ys if any(in_poly(x,y,p) for p in polys)]
        if len(pts)>=30 or step<=50: return pts,step
        step/=2
def quintile_grade(vals,v,low_is_good):
    qs=statistics.quantiles(vals,n=5)  # 4 个切点
    k=sum(v>q for q in qs)             # 0..4
    return GRADES[4-k] if low_is_good else GRADES[k], qs
def gnum(g):
    base={'S':5,'A':4,'B':3,'C':2,'D':1}[g[0]]; return base+(0.33 if g.endswith('+') else -0.33 if g.endswith('-') else 0)
def gletter(s): return GRADES[max(0,min(4,int(round(s))-1))]

class Grid:
    def __init__(s,cell): s.cell=cell; s.m=defaultdict(list)
    def key(s,x,y): return (int(x//s.cell),int(y//s.cell))
    def add_pt(s,x,y,obj): s.m[s.key(x,y)].append((x,y,obj))
    def add_box(s,x0,y0,x1,y1,obj):
        for i in range(int(x0//s.cell),int(x1//s.cell)+1):
            for j in range(int(y0//s.cell),int(y1//s.cell)+1): s.m[(i,j)].append(obj)
    def near(s,x,y,r=1):
        i,j=s.key(x,y); out=[]
        for a in range(i-r,i+r+1):
            for b in range(j-r,j+r+1): out.extend(s.m.get((a,b),()))
        return out

def load_flood(blocks_bbox):
    """A31a 河川単位 想定最大規模 GeoJSON → 只留 浸水深ランク≥2（≥0.5 m）且外接框碰到 104 块外接框的多边形，投影后进网格索引。zip 缺就下载进 raw/a31b/。多条河重叠时取深的（同 A31b 的做法）。"""
    g=Grid(500); n=0; bx0,by0,bx1,by1=blocks_bbox
    for z,codes in FLOOD_ZIPS.items():
        zp=os.path.join(RAW,'a31b',z); os.makedirs(os.path.dirname(zp),exist_ok=True)
        if not os.path.exists(zp):
            print('下载',A31A+z); urllib.request.urlretrieve(A31A+z,zp)
        zf=zipfile.ZipFile(zp)
        for i in zf.infolist():
            base=os.path.basename(i.filename.replace('\\','/'))
            if not base.startswith('A31a-20-'): continue
            if codes and not any(c in base for c in codes): continue
            fs=json.loads(zf.read(i).decode('utf-8'))['features']; kept=0
            for f in fs:
                if f['properties'].get('A31a_205',0)<2: continue
                for p in project(f['geometry']):
                    b=bbox([p])
                    if b[2]<bx0 or b[0]>bx1 or b[3]<by0 or b[1]>by1: continue
                    g.add_box(*b,(b,p,f['properties']['A31a_205'])); kept+=1
            n+=kept; print(f'  {base} {fs[0]["properties"].get("A31a_202","")}: {len(fs)} 多边形，留 {kept}')
    print('浸水多边形（≥0.5 m，碰到块）',n); return g

def main():
    tiers=json.load(open(os.path.join(D,'tiers.geojson'),encoding='utf-8'))
    crime=json.load(open(os.path.join(D,'crime_rate_r07.json'),encoding='utf-8'))
    reach=json.load(open(os.path.join(D,'reach.json'),encoding='utf-8'))
    osm=json.load(open(os.path.join(RAW,'osm','supermarkets_overpass.json'),encoding='utf-8'))
    # 治安：块 parent → 府警表里的市区町村名
    def ckey(parent):
        if parent in crime['rate']: return parent
        if '大阪市'+parent in crime['rate']: return '大阪市'+parent
        ks=[k for k in crime['rate'] if k.endswith(parent) and '郡' in k]
        if len(ks)==1: return ks[0]
        raise KeyError(parent)
    # 站
    sts=[]
    for s in reach['stations']:
        t=[v for v in s['t_default'] if v is not None]
        if not t: continue
        x,y=xy(s['lon'],s['lat']); k=min(range(4),key=lambda i:(s['t_default'][i] if s['t_default'][i] is not None else 1e9))
        sts.append((x,y,min(t),s['name'],reach['hubs'][k]))
    # 超市
    shops=Grid(SHOP_R)
    for e in osm['elements']:
        lat=e.get('lat') or e.get('center',{}).get('lat'); lon=e.get('lon') or e.get('center',{}).get('lon')
        if lat is None: continue
        x,y=xy(lon,lat); shops.add_pt(x,y,e['tags'].get('brand') or e['tags'].get('name') or '?')
    allpolys=[q for f in tiers['features'] for q in project(f['geometry'])]; flood=load_flood(bbox(allpolys))
    rows=[]
    for f in tiers['features']:
        p=f['properties']; polys=project(f['geometry']); pts,step=samples(polys)
        hubmin=[]; shopn=[]; wet=0; wet3=0
        for x,y in pts:
            near=sorted(sts,key=lambda s:(s[0]-x)**2+(s[1]-y)**2)[:NEAR_K]
            best=min(near,key=lambda s:math.hypot(s[0]-x,s[1]-y)*DETOUR/WALK_M_PER_MIN+s[2])
            hubmin.append((math.hypot(best[0]-x,best[1]-y)*DETOUR/WALK_M_PER_MIN+best[2],best[3],best[4]))
            shopn.append(sum(1 for sx,sy,_ in shops.near(x,y) if (sx-x)**2+(sy-y)**2<=SHOP_R**2))
            rank=0
            for (b,poly,r) in flood.near(x,y,0):
                if b[0]<=x<=b[2] and b[1]<=y<=b[3] and in_poly(x,y,poly): rank=max(rank,r)
            wet+=rank>=2; wet3+=rank>=3
        hm=statistics.median(h for h,_,_ in hubmin); typ=statistics.mode((st,hb) for _,st,hb in hubmin)
        ck=ckey(p['parent']); c=crime['rate'][ck]
        rows.append({'id':p['id'],'name':p['name'],'parent':p['parent'],'kind':p['kind'],'tier_now':p['tier'],'note_now':p.get('note',''),
            'n_samples':len(pts),'grid_m':step,'area_km2':round(area_km2(polys),2),
            'safety':{'muni':ck,'crime':c['crime'],'pop':c['pop'],'per1000':c['per1000'],'grade':c['grade_by_quintile']},
            'access':{'door_to_hub_min':round(hm,1),'typical_station':typ[0],'typical_hub':typ[1],'supermarkets_800m':statistics.median(shopn)},
            'hazard':{'flood_ge05_share':round(wet/len(pts),3),'flood_ge3_share':round(wet3/len(pts),3)}})
        print(f"{p['id']:34} {p['tier']:3} n={len(pts):4} hub {hm:5.1f} via {typ[0]} shop {statistics.median(shopn):4} flood {wet/len(pts):.0%} crime {c['per1000']}")
    # 五分位（104 块）
    hv=[r['access']['door_to_hub_min'] for r in rows]; sv=[r['access']['supermarkets_800m'] for r in rows]
    for r in rows:
        a=r['access']; a['grade_hub'],qh=quintile_grade(hv,a['door_to_hub_min'],True); a['grade_shop'],qs=quintile_grade(sv,a['supermarkets_800m'],False)
        a['grade']=gletter((gnum(a['grade_hub'])+gnum(a['grade_shop']))/2)
        w=r['hazard']['flood_ge05_share']; r['hazard']['grade']='S' if w==0 else 'A' if w<.1 else 'B' if w<.3 else 'C' if w<.6 else 'D'
        score=(gnum(r['safety']['grade'])+gnum(a['grade'])+gnum(r['hazard']['grade']))/3
        r['fit']={'score':round(score,2),'grade_abs':gletter(score)}
    sv2=[r['fit']['score'] for r in rows]
    for r in rows:
        r['fit']['grade'],qf=quintile_grade(sv2,r['fit']['score'],False); r['diff']=round(gnum(r['fit']['grade'])-gnum(r['tier_now']),2)
        # 备选 B：便利定级，治安 D / 环境 D 各扣一级（通勤工具的视角：先看到得了枢纽，再看住不住得安心）
        r['fit']['grade_rule']=gletter(gnum(r['access']['grade'])-(r['safety']['grade']=='D')-(r['hazard']['grade']=='D'))
    out={'meta':{'generated':__import__('datetime').date.today().isoformat(),'method':__doc__,'sources':SRC,
         'osm_base':osm['osm3s']['timestamp_osm_base'],'quintiles':{'door_to_hub_min':[round(q,1) for q in qh],'supermarkets_800m':qs,'crime_per1000':crime['quintiles'],'fit_score':[round(q,2) for q in qf]},
         'params':{'grid_m':STEP,'detour':DETOUR,'walk_m_per_min':WALK_M_PER_MIN,'shop_radius_m':SHOP_R,'near_k':NEAR_K},
         'fit':'score = 三维度 S=5…D=1 取平均；grade = score 在 104 块里的五分位（相对，前 20% 为 S），grade_abs = score 四舍五入（绝对，会挤在 B/C）；grade_rule = 备选 B：便利级为底，治安 D、环境 D 各扣一级；便利 = 门到枢纽五分位与超市五分位的平均；现 tier 的 +/- 记 ±0.33；diff = 拟合 grade − 现 tier',
         'not_done':['液状化：大阪府「液状化可能性判定図」只有 PDF，无 GIS 开放数据，未纳入','高潮・内水氾濫不在 A31a 里（A31a 只有河川外水），未纳入','商务区常住人口偏小使治安率偏高（北区 32.0、中央区 51.6），未改昼間人口——等用户定','兵庫県/京都府管理的小河川（府界附近）未加载']},
         'blocks':rows}
    json.dump(out,open(os.path.join(D,'tiers_scored.json'),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    print('写入 tiers_scored.json，',len(rows),'块；五分位 门到枢纽',[round(q,1) for q in qh],'超市',qs)
    if '--md' in sys.argv:
        print('\n| 块 | 区/市 | 现 | 治安 | 便利（门到枢纽·超市） | 环境（≥0.5 m 浸水占比） | 拟合A 平均·五分位（绝对） | 拟合B 便利扣分 | 差(A) |\n|---|---|---|---|---|---|---|---|---|')
        for r in sorted(rows,key=lambda r:(-abs(r['diff']),r['id'])):
            a=r['access']; print(f"| {r['name']} | {r['parent']} | {r['tier_now']} | {r['safety']['grade']} {r['safety']['per1000']} | {a['grade']} {a['door_to_hub_min']} 分·{a['supermarkets_800m']:g} 家 | {r['hazard']['grade']} {r['hazard']['flood_ge05_share']:.0%} | **{r['fit']['grade']}**（{r['fit']['grade_abs']}） | {r['fit']['grade_rule']} | {r['diff']:+.2f} |")
if __name__=='__main__': main()

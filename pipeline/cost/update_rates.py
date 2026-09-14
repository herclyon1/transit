#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新 cost/data/rates.json：汇率 + PPP 因子，带来源和日期。每天由 GitHub Actions 跑一次（.github/workflows/rates.yml），本地也能跑。

汇率口径：fx[货币] = 1 单位该货币兑多少日元（页面用日元做中转）。
- 官方主源：欧洲央行每日参考汇率 eurofxref-daily.xml（EUR 基准；含 USD/JPY/CNY/AUD 等，不含 VND/MMK/TWD）。
- 补充源：open.er-api.com（ExchangeRate-API 免费公开接口，汇总各央行日更；覆盖 VND/MMK/TWD）。ECB 有的货币一律用 ECB，只有 ECB 没有的才用它，并逐币标 source。
PPP：世界银行 PA.NUS.PPP（本币/国际元），台湾不在世行库里，留 null。
"""
import json, re, sys, time, urllib.request, xml.etree.ElementTree as ET

CURS = ['JPY', 'CNY', 'TWD', 'VND', 'MMK', 'EUR', 'USD', 'AUD']
def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'transit-cost-map/1.0 (+https://herclyon1.github.io/transit/)'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()

# ---- ECB
ecb_xml = get('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml').decode()
root = ET.fromstring(ecb_xml)
ns = {'e': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'}
day = root.find('.//e:Cube[@time]', ns)
ecb_date = day.get('time')
per_eur = {c.get('currency'): float(c.get('rate')) for c in day.findall('e:Cube', ns)}
per_eur['EUR'] = 1.0

# ---- er-api（补 ECB 没有的）
er = json.loads(get('https://open.er-api.com/v6/latest/EUR').decode())
er_date = time.strftime('%Y-%m-%d', time.gmtime(er['time_last_update_unix']))
er_rates = er['rates']

fx, src = {}, {}
jpy_per_eur = per_eur['JPY']
for c in CURS:
    if c in per_eur:
        fx[c] = round(jpy_per_eur / per_eur[c], 6); src[c] = {'name': '欧洲央行每日参考汇率', 'url': 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml', 'date': ecb_date}
    elif c in er_rates:
        fx[c] = round(jpy_per_eur / er_rates[c], 6); src[c] = {'name': 'ExchangeRate-API 公开接口（EUR 基准）', 'url': 'https://open.er-api.com/v6/latest/EUR', 'date': er_date}
    else:
        fx[c] = None; src[c] = None

# ---- PPP
wb = json.loads(get('https://api.worldbank.org/v2/country/JP;CN;VN;MM;DE;US;AU/indicator/PA.NUS.PPP?format=json&mrv=1&per_page=50').decode())
iso2cur = {'JP': 'JPY', 'CN': 'CNY', 'VN': 'VND', 'MM': 'MMK', 'DE': 'EUR', 'US': 'USD', 'AU': 'AUD'}
ppp, ppp_year = {}, {}
for row in wb[1]:
    cur = iso2cur.get(row['country']['id'])
    if cur and row['value'] is not None: ppp[cur] = round(row['value'], 6); ppp_year[cur] = row['date']
ppp['TWD'] = None; ppp_year['TWD'] = None

out = {
  'note': '汇率与购买力平价换算因子。fx 为 1 单位当地货币兑 JPY；ppp 为世界银行 PPP 换算因子（当地货币/国际元）。由 pipeline/cost/update_rates.py 每日自动更新，页面打开时还会再拉一次实时汇率，本文件是兜底。',
  'fetched_at': time.strftime('%Y-%m-%d'),
  'source_url': 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml',
  'fx': fx, 'fx_source': src,
  'ppp': ppp, 'ppp_year': ppp_year,
  'ppp_source': {'name': '世界银行 PA.NUS.PPP（本币/国际元）', 'url': 'https://api.worldbank.org/v2/country/JP;CN;VN;MM;DE;US;AU/indicator/PA.NUS.PPP?format=json&mrv=1'},
}
json.dump(out, open('cost/data/rates.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({'fx': fx, 'ecb': ecb_date, 'er': er_date, 'ppp': ppp}, ensure_ascii=False))

#!/usr/bin/env python3
"""Download Satellogic EarthView (CC-BY 4.0, 1 m) VISUAL patches over Bahrain from the AWS open-data bucket.
Usage: python3 tools/satl_fetch.py raw_satl/regions.json raw_satl
Phase 1 lists every region's captures; phase 2 picks, per region, the capture (satellite pass) that covers the
most regions overall (fewer seams / colour jumps; ties -> newest) and downloads only that VISUAL COG.
Writes raw_satl/index.json [{region,capture,date,n,file}]."""
import collections, json, os, re, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
B = 'https://satellogic-earthview.s3.us-west-2.amazonaws.com/'
regions = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out + '/tif', exist_ok=True)

def get(u, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'bahrain-map'}), timeout=60).read()
        except Exception:
            if i == tries - 1: raise
    return b''
def listing(prefix):
    try: return prefix, re.findall(r'<Key>([^<]*_VISUAL\.tif)</Key>', get(B + '?list-type=2&prefix=' + prefix).decode())
    except Exception as e: print('ERR list', prefix, e, flush=True); return prefix, []
lst_f = out + '/listing.json'
if os.path.exists(lst_f): lst = json.load(open(lst_f))
else:
    with ThreadPoolExecutor(16) as ex: lst = dict(ex.map(listing, regions))
    json.dump(lst, open(lst_f, 'w'))
def cap(k):
    b = os.path.basename(k).split('_'); return '_'.join(b[:3])  # e.g. 20221130_065256_SN11 = one satellite pass
count = collections.Counter(cap(k) for ks in lst.values() for k in ks)
print('regions with data', sum(1 for v in lst.values() if v), 'captures', len(count), count.most_common(10), flush=True)
def one(item):
    prefix, keys = item
    if not keys: return None
    k = max(keys, key=lambda s: (count[cap(s)], cap(s)))
    f = f'{out}/tif/{os.path.basename(k)}'
    try:
        if not os.path.exists(f):
            data = get(B + k); open(f + '.part', 'wb').write(data); os.replace(f + '.part', f)
    except Exception as e: print('ERR get', k, e, flush=True); return None
    return {'region': prefix, 'capture': cap(k), 'date': re.search(r'date=([\d-]+)', k).group(1), 'n': len(keys), 'file': f}
res = []
with ThreadPoolExecutor(12) as ex:
    for i, r in enumerate(ex.map(one, lst.items())):
        if r: res.append(r)
        if i % 500 == 0: print(i, len(res), flush=True)
json.dump(res, open(out + '/index.json', 'w'))
print('done', len(res))

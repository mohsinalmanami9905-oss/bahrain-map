#!/usr/bin/env python3
"""Warp Sentinel-2 L2A RGB bands (Element84 Earth Search COGs, AWS open data) onto the z14 Web-Mercator grid.
Usage: python3 tools/s2_warp.py raw_s2/plan3.json raw_s2   (sequential, low RAM)"""
import json, os, subprocess, sys
G = os.environ.get('GDAL_BIN', '/opt/data/cache/scratch/kafu_audit/pgenv/bin')
env = dict(os.environ, PROJ_DATA=G + '/../share/proj', GTIFF_SRS_SOURCE='EPSG', GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',
           CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MULTIRANGE='YES', GDAL_HTTP_MERGE_CONSECUTIVE_RANGES='YES',
           GDAL_CACHEMAX='256', GDAL_HTTP_MAX_RETRY='5', GDAL_HTTP_RETRY_DELAY='3')
plan = json.load(open(sys.argv[1])); out = sys.argv[2]
g = plan['grid']; te = [str(v) for v in g['te']]; res = str(g['res'])
dates = sorted({k.split('_')[2] for k in plan['items']}, reverse=True)
for d in dates:
    for b in ['red', 'green', 'blue']:
        f = f'{out}/{d}.{b}.tif'
        if os.path.exists(f) and os.path.getsize(f) > 0: continue
        srcs = ['/vsicurl/' + v[b] for k, v in sorted(plan['items'].items()) if k.split('_')[2] == d]
        cmd = [G + '/gdalwarp', '-overwrite', '-t_srs', 'EPSG:3857', '-te', *te, '-tr', res, res, '-r', 'cubic',
               '-srcnodata', '0', '-dstnodata', '0', '-ot', 'UInt16', '-of', 'GTiff', '-wm', '256', '-co', 'TILED=YES', '-co', 'COMPRESS=DEFLATE',
               *srcs, f + '.part']
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode: print('FAIL', d, b, r.returncode, r.stdout[-300:], r.stderr[-500:], flush=True); continue
        os.replace(f + '.part', f); print('done', d, b, flush=True)

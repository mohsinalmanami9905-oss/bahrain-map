# Offline satellite imagery — sources checked (Nov 2026)

Goal: satellite view that works with no internet, using only imagery whose licence allows download, storage and
redistribution. Esri / Google / Bing / Mapbox imagery is **not** cached (their terms forbid it); Esri stays as an
online-only option in the app.

| Source | Where | Coverage of Bahrain | Resolution / date | Licence | Used? |
|---|---|---|---|---|---|
| **Sentinel-2 L2A** (Copernicus) via Element 84 Earth Search | `https://earth-search.aws.element84.com/v1` → `s3://sentinel-cogs` (AWS Open Data) | All of Bahrain + Hawar, tiles 39RVJ/39RVK | 10 m; median of 3 cloud-free passes 25 Sep, 5 Oct, 4 Nov 2026 | Copernicus free & open (attribution: "Contains modified Copernicus Sentinel data 2026") | **Yes** – base layer, zoom 6–14, 4 MB (`docs/data/sat/s2.pmtiles`) |
| **Satellogic EarthView** | `s3://satellogic-earthview` (AWS Open Data registry), also `huggingface.co/datasets/satellogic/EarthView` | 8,143 patches (384 m × 384 m), checked point by point: **covered** Seef, Muharraq + airport, Amwaj, Diyar, Juffair, Adliya, Sitra, Isa Town, Riffa, Hamad Town, Awali, Saar, Zallaq, Sakhir, Hawar Islands. **Not covered**: a 1–3 km strip through central Manama (Bab al Bahrain, Bahrain Bay, Salmaniya), which falls in the gap between two satellite passes, plus Budaiya, Umm an Na'san, Askar, Durrat al Bahrain and the southern desert. Those areas show the 10 m layer | 1 m (Mark IV, RGB), Jul–Dec 2022 | **CC BY 4.0** (commercial use OK, attribution required) | **Yes** – high-res layer, zoom 12–17 (`docs/data/sat/hr-*.pmtiles`) |
| OpenAerialMap | `api.openaerialmap.org/meta?bbox=…` | 0 images in 49–52 °E, 24–27.5 °N | – | CC BY 4.0 | No: nothing there |
| Maxar Open Data Program | `maxar-opendata` STAC (55 events) / source.coop/maxar | No Gulf/Bahrain event | 30–50 cm | CC BY-NC 4.0 (non-commercial) | No: no coverage |
| Planet Disaster Data | `data.source.coop/planet/disasterdata` (9 events) | No Gulf/Bahrain event | 0.5–3 m | CC BY-NC 4.0 | No: no coverage |
| Planet NICFI basemaps | – | Tropics only (Bahrain excluded) | 4.7 m | NICFI terms | No |
| Hugging Face "TheFalcon360-Bahrain-HD-Google-Earth" | huggingface.co/datasets/TheFalcon360/… | Bahrain | Google Earth captures | Derived from Google Earth; Google's terms forbid redistribution, so a dataset licence can't make it legal | **Rejected** |
| Hugging Face "TheFalcon360-Bahrain-Sentinel2" | huggingface.co/datasets/TheFalcon360/… | Bahrain | 10 m | Sentinel-2 | Not needed: our own composite is newer |
| GitHub search ("bahrain satellite imagery", "bahrain orthophoto") | api.github.com | 0 repositories | – | – | No |
| National orthophotos (Survey & Land Registration Bureau) | – | Bahrain | high | No open licence published | No |
| Landsat 8/9 | USGS / AWS | All | 30 m (15 m pan) | Public domain | No: Sentinel-2 is sharper |
| SEN2SR (AI super-resolution of Sentinel-2, 10 m → 2.5 m) | huggingface.co/tacofoundation/SEN2SR | Could cover the whole country | 2.5 m (AI-generated detail) | CC0 model | Not shipped, see below |
| Esri World Imagery | server.arcgisonline.com | All | ~0.3–0.5 m | Viewing only; offline caching/bulk download prohibited | Online-only option ("Esri (إنترنت)"), never cached |

## Why there's no AI super-resolution layer
SEN2SR (CC0) would make 2.5 m-looking imagery from Sentinel-2. It wasn't shipped because:
1. The populated north already has real 1 m imagery.
2. What's left (southern desert, oil field, coast) gains little from invented detail, and AI-hallucinated buildings and
   roads are a risk on a map people navigate with.
3. It needs PyTorch and a few GB of RAM/disk on a host that is short of memory.
If you want it later, run it for the south only and label it "محسّنة بالذكاء الاصطناعي" (AI-enhanced) in the layer picker.

## Rebuild
```
python3 tools/s2_warp.py raw_s2/plan3.json raw_s2            # 9 band rasters onto the z14 grid (~5 min)
python3 tools/s2_tiles.py raw_s2/plan3.json raw_s2 raw_s2/s2.mbtiles && bin/pmtiles convert raw_s2/s2.mbtiles docs/data/sat/s2.pmtiles
python3 tools/satl_fetch.py raw_satl/regions.json raw_satl   # 8,143 x 1 m patches (3.2 GB)
python3 tools/satl_balance.py raw_satl raw_s2/plan3.json raw_s2/s2_composite.png   # colour-match each pass to Sentinel-2
python3 tools/satl_tiles.py raw_satl raw_satl/hr.mbtiles
python3 tools/split_mbtiles.py raw_satl/hr.mbtiles docs/data/sat hr 90   # parts < 90 MB (GitHub limit 100 MB)
python3 tools/stamp.py
```
Run the heavy steps with `flock /opt/data/cache/scratch/icu_heavy.lock nice -n 10` on this host.

# خريطة البحرين — Offline Bahrain Map (PWA)

Open-source, installable web app with a detailed vector map of Bahrain that works **without internet** after the first open.

**Live:** https://mohsinalmanami9905-oss.github.io/bahrain-map/

- OpenStreetMap vector tiles for Bahrain only (Protomaps basemap, z0–15, overzoomed to z19): roads, buildings, POIs, Arabic + English names — ~9.2 MB.
- MapLibre GL JS 6 (Arabic shaping/BiDi is built in, no CDN RTL plugin needed), protomaps-basemaps light/dark style, all JS/CSS/fonts/glyphs/sprites served locally.
- Arabic labels by default, English toggle; light/dark theme.
- GPS "my location" (follow mode; second tap = compass mode, rotates the map with the phone's heading).
- Offline search (~21k places/streets, Arabic/English, Arabic normalisation أ/ا، ة/ه، ى/ي, optional «ال»).
- Long-press → pin with coordinates, copy, share, open in Google Maps / Apple Maps.
- **Offline satellite layer** built only from openly licensed imagery (see `SATELLITE_SOURCES.md`):
  - Sentinel-2 10 m cloud-free composite (Sep–Nov 2026) for all of Bahrain + Hawar, ~4 MB, downloaded automatically with the map;
  - Satellogic EarthView **1 m** imagery (2022, CC BY 4.0) for most of northern Bahrain (Seef, Muharraq, Juffair, Sitra, Isa Town, Riffa, Hamad Town, …) and Hawar. It's an optional download with a progress bar (menu → «تحميل صور القمر الصناعي عالية الدقة»), colour-matched to Sentinel-2 and split into parts under 90 MB.
  - Labels (Arabic/English) drawn on top of the imagery, with a show/hide toggle.
- Optional **online** Esri World Imagery (sharper, needs internet, never cached because Esri's terms forbid it).
- Service worker caches the app shell; the whole `.pmtiles` file is downloaded once into Cache Storage (auto on first open, or the "download" button with progress bar) and read locally from a Blob.

## Layout
- `docs/` — the deployed site (GitHub Pages serves this folder)
- `tools/build_poi_index.mjs` — builds `docs/data/poi.json` from the PMTiles
- `tools/stamp.py` — writes `docs/data/meta.json` and bumps the service-worker cache version
- `tools/serve.mjs` — local static server with HTTP Range support
- `tools/e2e.py` — Playwright test (iPhone 390×844, mocked GPS, offline reload)
- `tools/e2e_sat.py` — Playwright test of the offline satellite layer (download, go offline, render z9–z18)
- `tools/s2_warp.py`, `s2_tiles.py`, `satl_fetch.py`, `satl_balance.py`, `satl_tiles.py`, `split_mbtiles.py`, `tilekit.py` — satellite pipeline (see `SATELLITE_SOURCES.md`)

## Rebuild the data
```sh
pmtiles extract https://build.protomaps.com/<YYYYMMDD>.pmtiles docs/data/bahrain.pmtiles --bbox=50.20,25.50,50.90,26.40 --maxzoom=15
node tools/build_poi_index.mjs docs/data/bahrain.pmtiles docs/data/poi.json   # needs pmtiles, @mapbox/vector-tile, pbf
python3 tools/stamp.py
```

## Licences
Code: MIT. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0. Tiles schema/style: Protomaps (BSD-3-Clause). MapLibre GL JS (BSD-3-Clause). Noto Sans fonts (SIL OFL 1.1). Offline imagery: contains modified Copernicus Sentinel data 2026; Satellogic EarthView © Satellogic, CC BY 4.0. Online-only imagery © Esri, Maxar, Earthstar Geographics.

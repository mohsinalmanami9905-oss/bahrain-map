# خريطة البحرين — Offline Bahrain Map (PWA)

Open-source, installable web app with a detailed vector map of Bahrain that works **without internet** after the first open.

**Live:** https://mohsinalmanami9905-oss.github.io/bahrain-map/

- OpenStreetMap vector tiles for Bahrain only (Protomaps basemap, z0–15, overzoomed to z19): roads, buildings, POIs, Arabic + English names — ~9.2 MB.
- MapLibre GL JS 6 (Arabic shaping/BiDi is built in, no CDN RTL plugin needed), protomaps-basemaps light/dark style, all JS/CSS/fonts/glyphs/sprites served locally.
- Arabic labels by default, English toggle; light/dark theme.
- GPS "my location" (follow mode; second tap = compass mode, rotates the map with the phone's heading).
- Offline search (~21k places/streets, Arabic/English, Arabic normalisation أ/ا، ة/ه، ى/ي, optional «ال»).
- Long-press → pin with coordinates, copy, share, open in Google Maps / Apple Maps.
- Optional **online** satellite layer (Esri World Imagery) — clearly marked "needs internet".
- Service worker caches the app shell; the whole `.pmtiles` file is downloaded once into Cache Storage (auto on first open, or the "download" button with progress bar) and read locally from a Blob.

## Layout
- `docs/` — the deployed site (GitHub Pages serves this folder)
- `tools/build_poi_index.mjs` — builds `docs/data/poi.json` from the PMTiles
- `tools/stamp.py` — writes `docs/data/meta.json` and bumps the service-worker cache version
- `tools/serve.mjs` — local static server with HTTP Range support
- `tools/e2e.py` — Playwright test (iPhone 390×844, mocked GPS, offline reload)

## Rebuild the data
```sh
pmtiles extract https://build.protomaps.com/<YYYYMMDD>.pmtiles docs/data/bahrain.pmtiles --bbox=50.20,25.50,50.90,26.40 --maxzoom=15
node tools/build_poi_index.mjs docs/data/bahrain.pmtiles docs/data/poi.json   # needs pmtiles, @mapbox/vector-tile, pbf
python3 tools/stamp.py
```

## Licences
Code: MIT. Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0. Tiles schema/style: Protomaps (BSD-3-Clause). MapLibre GL JS (BSD-3-Clause). Noto Sans fonts (SIL OFL 1.1). Satellite imagery (online only) © Esri, Maxar, Earthstar Geographics.

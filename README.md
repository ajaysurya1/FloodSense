# FloodSense — Hyperlocal Flood Early-Warning System
**NDMA Hackathon Demo · Climate-Resilient Urban Flood Monitoring**

> ⚠️ **All risk outputs are heuristic, uncalibrated estimates.**  
> This system complements—and does NOT replace—official NDMA SACHET warnings.  
> Follow government-authorised alerts for life-safety decisions.

---

## What Is Real vs Simulated

| Component | Status | Notes |
|---|---|---|
| **Open-Meteo forecast** | **LIVE** | Real API call; 5-min cache; falls back to stale data |
| **SRTM Elevation** | **LIVE** (first run) → cached | Open-Meteo elevation API; saved to `terrain_cache.json` |
| **Flood hotspots** | **SEED** | ~15 illustrative points from public reports; NOT verified municipal GIS |
| **Drain network** | **SEED** | 7 seed points with capacity class; NOT verified CMDA/GWMB data |
| **Facilities** | **SEED** | 6 seed hospitals/schools/shelters; NOT verified official records |
| **IoT sensor readings** | **SIMULATED** | `simulate_sensors.py` streams 5 nodes; flags SIMULATED in API and UI |
| **Citizen report CLIP classification** | Real model (graceful fallback) | `openai/clip-vit-base-patch32`; falls back to "needs_manual_review" |
| **SMS / WhatsApp alerts** | **SIMULATED PREVIEW** | No real messages sent; pluggable Provider class |
| **CAP 1.2 XML** | **Format demo** | Labelled "not transmitted to SACHET" |
| **Risk score** | **Heuristic estimate** | Weighted sum; weights are ASSUMPTIONS, not calibrated |
| **Tamil alert copy** | Human-drafted | Needs review by native speaker before real use |
| **ESP32 firmware** | **Reference only** | Not deployed in demo; `node.ino` is documented but untested |

---

## Quick Start

### 1 — Backend
```powershell
cd app\backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2 — Frontend
```powershell
cd app\frontend
npm install
npm run dev
```
Open: http://localhost:5173

### 3 — Sensor Simulator (in a third terminal)
```powershell
cd app\backend
python -m scripts.simulate_sensors --url http://localhost:8000
```

### 4 — SCENARIO mode (no internet needed)
```powershell
# Backend terminal:
$env:FLOODSENSE_MODE="SCENARIO"
uvicorn main:app --reload --port 8000
```

---

## Architecture

```
FloodSense/
├── app/
│   ├── backend/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.yaml          # All ASSUMPTION-labelled constants
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   ├── config.py    # Pydantic settings
│   │   │   │   └── database.py  # SQLite init (WAL mode)
│   │   │   ├── risk/
│   │   │   │   └── engine.py    # D1: weighted risk grid
│   │   │   ├── routers/
│   │   │   │   ├── risk.py      # GET /api/risk
│   │   │   │   ├── sensors.py   # D2: POST/GET /api/sensors
│   │   │   │   ├── reports.py   # D4: POST/GET /api/reports
│   │   │   │   ├── alerts.py    # D6: POST /api/alerts/generate
│   │   │   │   ├── tasks.py     # D7: task board
│   │   │   │   └── dashboard.py # D7: summary
│   │   │   └── services/
│   │   │       ├── open_meteo.py      # Forecast + cache
│   │   │       ├── elevation_service.py # SRTM + file cache
│   │   │       ├── sensor_state.py    # In-memory sensor cache
│   │   │       └── clip_classifier.py # D4: CLIP zero-shot
│   │   └── scripts/
│   │       └── simulate_sensors.py    # D2: 5-node simulator
│   ├── frontend/
│   │   └── src/
│   │       ├── App.jsx
│   │       ├── api.js
│   │       └── components/
│   │           ├── MapView.jsx      # Leaflet map + risk layers
│   │           ├── CellPanel.jsx    # Click-to-explain panel
│   │           ├── Sidebar.jsx      # 6-tab sidebar
│   │           ├── Topbar.jsx       # Mode badge + disclaimer
│   │           └── tabs/
│   │               ├── RiskTab.jsx      # D1 risk list
│   │               ├── SensorsTab.jsx   # D2 sensor cards
│   │               ├── ReportsTab.jsx   # D4 citizen reports
│   │               ├── AlertsTab.jsx    # D6 alert previews
│   │               ├── TasksTab.jsx     # D7 task board
│   │               └── DashboardTab.jsx # D7 municipal view
│   ├── firmware/
│   │   └── node.ino   # ESP32 reference (not deployed)
│   └── data/
│       ├── ward.json             # Demo ward config
│       ├── hotspots.geojson      # SEED flood locations
│       ├── drains.geojson        # SEED drain points
│       ├── facilities.geojson    # SEED critical facilities
│       ├── terrain_cache.json    # Auto-populated elevation cache
│       ├── floodsense.db         # SQLite (auto-created)
│       └── templates/
│           └── alert_templates.yaml  # D6 bilingual templates
```

---

## Risk Engine (D1) — How It Works

```
score = 0.30 × rain_intensity_next_3h_norm   (Open-Meteo LIVE)
      + 0.20 × cumulative_rain_norm
      + 0.20 × terrain_lowness_norm           (SRTM elevation)
      + 0.15 × hotspot_proximity_score        (SEED)
      + 0.10 × drainage_penalty              (SEED)
      + 0.05 × sensor_rate_of_rise_norm      (SIMULATED in demo)
```

**All weights are ASSUMPTIONS** (in `config.yaml`). Not calibrated against historical flood data.

Severity thresholds: Watch ≥ 35, Warning ≥ 60, Severe ≥ 80 (ASSUMPTIONS).

---

## Honesty Checklist

- [x] Every risk output labelled "heuristic, uncalibrated estimate"
- [x] Every data source tagged LIVE / SIMULATED / SEED in API responses and UI
- [x] Citizen photo never treated as measured flood depth
- [x] Alert footer: "Complements NDMA SACHET; does not replace official warnings"
- [x] No invented statistics, metrics, costs or client names
- [x] Tamil copy flagged for native-speaker review
- [x] SCENARIO mode clearly badged in UI
- [x] No rainfall faked from water level in firmware

---

## What Was Cut for Time

| Feature | Status |
|---|---|
| D3 (why panel) | Merged into D1 cell-click panel |
| D5 (Prithvi/mmseg integration) | Deferred; app runs fully without it |
| D8 | Skipped per spec |
| Auth | Demo-only (no auth); noted in docs |
| Docker | Not added; startup is 2 commands |
| Real SMS/WhatsApp | Provider class stubbed; not wired |

---

## For Judges

- **All numbers on screen are computed, not hardcoded.**  
- The risk grid uses real Open-Meteo precipitation data in LIVE mode.  
- Sensor readings in the demo are SIMULATED and tagged as such.  
- The Tamil templates need native-speaker review — this is stated in the UI.  
- No paid APIs, no tokens required to run.

*FloodSense is a prototype built at a hackathon. Operational deployment requires domain-expert validation of weights, municipal GIS data integration, and independent security review.*

# FloodSense — Risk Calculation Reference for Judge Q&A
**Read time: ~60 seconds**

> ⚠️ **IMPORTANT HONESTY NOTICE**: All risk scores, severity categorisations, and depth proxies are **heuristic, uncalibrated estimates**. The component weights and thresholds below are based on **qualitative expert elicitation (ASSUMPTIONS)** and have not yet undergone replay-based calibration against historical gauge data or post-disaster flood inundation maps. FloodSense is designed to complement—and NEVER replace—official NDMA SACHET warnings.

---

## 1. Executive Summary in 60 Seconds

FloodSense computes a hyperlocal flood risk index between **0.0 and 100.0** for every **150 m × 150 m grid cell** across the active municipal ward.

The score combines:
1. **Forecast meteorology** (Open-Meteo live API / scenario storm)
2. **Topographic depression** (SRTM digital elevation model)
3. **Historical vulnerability** (Municipal flood hotspots seed layer)
4. **Drainage infrastructure** (Storm-water drain network capacity seed layer)
5. **Real-time hydrological rate-of-rise** (Physical IoT sensors + CCTV virtual sensors)

---

## 2. Input Data Sources & Provenance

| Input Component | Provenance & Source | Refresh Cadence | Data Classification |
|---|---|---|---|
| **Rainfall Intensity (next 3h)** | Open-Meteo precipitation forecast API | 5-minute cache | **LIVE** (or **SCENARIO** storm replay) |
| **Cumulative Rainfall** | Open-Meteo forecast cumulative total | 5-minute cache | **LIVE** (or **SCENARIO** storm replay) |
| **Terrain Lowness** | SRTM Digital Elevation Model (cached locally per lat/lon) | Static (cached on first fetch) | **LIVE** (via elevation API) / Cached |
| **Hotspot Proximity** | Public Chennai flood records & historical reports | Static per ward | **SEED** (Illustrative GIS points) |
| **Drainage Capacity / Penalty** | Canal & storm drain network points with capacity class | Static per ward | **SEED** (Illustrative infrastructure points) |
| **Sensor Rate-of-Rise (RoR)** | Ultrasonic water level sensors + CCTV virtual sensors | Real-time (10–15 s streams) | **SIMULATED** (ESP32 telemetry) / **CCTV** (Video feed + CLIP zero-shot classification) |

---

## 3. Normalisation & Component Formulas

Each component is mapped to an internal normalised range **[0.0, 1.0]**:

1. **Rain Intensity Normalisation ($R_{\text{norm}}$)**:
   $$R_{\text{norm}} = \min\left(\frac{\text{rain\_intensity\_mm\_3h}}{50.0}, 1.0\right)$$
   *(50 mm per 3 hours is treated as extreme cloudburst intensity).*

2. **Cumulative Rain Normalisation ($C_{\text{norm}}$)**:
   $$C_{\text{norm}} = \min\left(\frac{\text{cumulative\_rain\_mm}}{100.0}, 1.0\right)$$
   *(100 mm total rainfall treated as extreme saturation).*

3. **Terrain Lowness Normalisation ($T_{\text{norm}}$)**:
   - For cell $(r, c)$, let $\bar{E}_{\text{nbr}}$ be the mean elevation of all valid 8-connected neighbours.
   - Depression depth: $D_i = \max(0, \bar{E}_{\text{nbr}} - E_i)$.
   - Normalisation: $T_{\text{norm}} = D_i / \max_k(D_k)$ across the ward.
   - *Safety Rule*: If the elevation array dimension does not match $N_{\text{rows}} \times N_{\text{cols}}$, the engine explicitly logs a warning and sets $T_{\text{norm}} = 0.0$ to prevent distorted arithmetic.

4. **Hotspot Proximity Score ($H_{\text{score}}$)**:
   - For all hotspots $k$ within 1.0 km ($d_k < 1.0\text{ km}$):
     $$H_{\text{score}} = \max_k \left[ w_{\text{class}} \cdot \left(1.0 - \frac{d_k}{1.0}\right) \right]$$
     where $w_{\text{class}} = 1.0$ (High), $0.7$ (Medium), $0.4$ (Low).

5. **Drainage Penalty ($D_{\text{penalty}}$)**:
   - For all drain nodes $j$ within 0.8 km ($d_j < 0.8\text{ km}$):
     $$D_{\text{penalty}} = \max_j \left[ p_{\text{cap}} \cdot \left(1.0 - \frac{d_j}{0.8}\right) \right]$$
     where $p_{\text{cap}} = 1.0$ (Low capacity / high vulnerability), $0.5$ (Medium capacity), $0.2$ (High capacity).

6. **Hydrological Rate-of-Rise ($S_{\text{norm}}$)**:
   - Evaluated for all sensors within 1.0 km of the cell.
   - Rate of rise computed dynamically from actual observation timestamps:
     $$\Delta t = t_{\text{newest}} - t_{\text{oldest}} \quad (\text{seconds})$$
     $$\text{RoR} = \frac{\max(0, \text{level}_{\text{newest}} - \text{level}_{\text{oldest}})}{\Delta t} \times 300 \quad (\text{cm per 5 minutes})$$
     *(If $\Delta t \le 0$ or readings are falling, $\text{RoR} = 0.0$).*
   - Normalisation: $S_{\text{norm}} = \min(\text{RoR} / 10.0, 1.0)$ *(10 cm/5min = flash rise).*
   - **CCTV virtual sensors**: Frame classification mapped to uncalibrated depth proxies (e.g., *knee-deep* = 35 cm, *ankle-deep* = 15 cm) ingest into this exact pipeline tagged `data_source="CCTV"`.

---

## 4. The Weighted Risk Formula

The overall cell risk score $S \in [0, 100]$ is computed as:

$$\begin{aligned}
S = \min\Big(100.0, \quad & 0.30 \times R_{\text{norm}} \times 100 \\
& + 0.20 \times C_{\text{norm}} \times 100 \\
& + 0.20 \times T_{\text{norm}} \times 100 \\
& + 0.15 \times H_{\text{score}} \times 100 \\
& + 0.10 \times D_{\text{penalty}} \times 100 \\
& + 0.05 \times S_{\text{norm}} \times 100 \Big)
\end{aligned}$$

### Critical Ground-Sensor Override (D2)
If a physical IoT sensor or corroborated CCTV virtual sensor within 0.5 km registers:
- Rate of rise $> 4.0\text{ cm per 5 minutes}$, OR
- Absolute water level $> 60.0\text{ cm}$,

The cell risk is **immediately overridden to Severe ($\ge 80.0$)**, bypassing meteorological lag and protecting against localized drainage failures or culvert blockages.

---

## 5. Severity Thresholds

Configured in `app/backend/config.yaml` (ASSUMPTION constants):

| Severity Level | Score Range | Operational Meaning | Suggested Action |
|---|---|---|---|
| **Normal** | $0.0 \le S < 35.0$ | Baseline dry conditions | Routine monitoring |
| **Watch** | $35.0 \le S < 60.0$ | Elevated water logging potential | Pre-position desilting crews, inspect pumps |
| **Warning** | $60.0 \le S < 80.0$ | Inundation likely across roads | Stage motorized suction pumps, divert traffic |
| **Severe** | $80.0 \le S \le 100.0$ | Deep inundation / life hazard | Evacuation advisory, shelter activation, rapid alert dispatch |

---

## 6. Confidence Scoring Rule

A score's operational reliability is classified as **High**, **Medium**, or **Low**:

- **High Confidence**: Forecast data age $< 30$ minutes, active IoT/CCTV sensor within 1.0 km, fresh SRTM elevation data available.
- **Medium Confidence**: Fresh forecast and topography available, but no active ground sensor within 1.0 km (flagged: *"No ground sensor nearby — relying on meteorological forecast and elevation"*).
- **Low Confidence**: Forecast data older than 30 minutes, or conflicting multi-source readings ($> 20\%$ discrepancy).

---

## 7. Calibration Status & Roadmap

- **Status Today**: Expert-elicitation weights (ASSUMPTIONS).
- **Next Step**: Retrospective calibration against Chennai December 2015 and Cyclone Michaung (December 2023) hourly rainfall and flooding records using Bayesian optimization.

#!/usr/bin/env python3
# mapa_generator.py
# Versión corregida y completa: generate_map_compact_final_restructured v4 (todo en un archivo)
# - Corrige SyntaxError por JS fuera del template
# - Leyenda PM2.5: 0-10 Excelente, 10-13 Bueno, 13-35 Regular, 35-55 Malo, >55 Peligroso
# - Animaciones incluidas en la plantilla HTML/JS
# - Gráficas suavizadas (tension, pointRadius=0)
# - Añade 3 o 4 variables extra en detalles segun disponibilidad
# - No destruye la lógica original de procesamiento de datos

import pandas as pd
import json
import os, sys
from datetime import datetime
import bisect

CSV = "datos_consolidados_20251104_141743.csv"
OUT = "mapa_compacto_v4.html"

if not os.path.exists(CSV):
    print(f"ERROR: no se encuentra el CSV '{CSV}' en el directorio actual.", file=sys.stderr)
    sys.exit(1)

print("📥 Leyendo CSV (puede tardar unos segundos)...")
df = pd.read_csv(CSV, low_memory=False)

# columnas mínimas
for c in ['timestamp', 'latitud', 'longitud']:
    if c not in df.columns:
        print(f"ERROR: El CSV debe contener la columna '{c}'.", file=sys.stderr)
        sys.exit(1)

# normalizar y limpiar
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df['latitud'] = pd.to_numeric(df['latitud'], errors='coerce')
df['longitud'] = pd.to_numeric(df['longitud'], errors='coerce')
df = df.dropna(subset=['timestamp','latitud','longitud']).copy()
df = df.sort_values('timestamp')

# generar estacion_id si no existe
if 'estacion_id' not in df.columns:
    if 'nombre_estacion' in df.columns:
        df['estacion_id'] = df['nombre_estacion'].astype(str).fillna('').replace('', None)
        df.loc[df['estacion_id'].isna(), 'estacion_id'] = df.loc[df['estacion_id'].isna()].apply(
            lambda r: f"lat{r['latitud']}_lon{r['longitud']}", axis=1
        )
    else:
        df['estacion_id'] = df.apply(lambda r: f"lat{r['latitud']}_lon{r['longitud']}", axis=1)

# construir mapa lower->orig
cols_lower = {c.lower(): c for c in df.columns}

# función búsqueda por tokens preferenciales
def find_col_by_tokens(tokens):
    for t in tokens:
        if t in cols_lower:
            return cols_lower[t]
    return None

# tokens ampliados según tipos de equipo
mapping_tokens = {
    'temp': ['temp_ext_ult_c','temp_ext_media_c','temp_c','temperatura','temperature','temp'],
    'humidity': ['hum_ext_ult','humedad','hum','relative_humidity','rh'],
    'precip': ['lluvia_mm','lluvia','precipitation','precip','rain_mm','rain'],
    'pm25': ['pm_2p5_media_ugm3','pm25','pm2_5','pm_2_5_ugm3','pm_2_5'],
    'pm10': ['pm10','pm_10','pm_10_ugm3'],
    'pm1': ['pm1','pm_1'],
    'aqi': ['aqi','ica','aqi_media_val','indice_calidad_aire'],
    'wind_speed': ['viento_vel_media_kmh','wind_speed_kmh','wind_speed','wind_avg','viento_vel'],
    'wind_dir': ['viento_dir','wind_dir','wind_direction','direccion_viento'],
    'pressure': ['presion_hpa','pressure_hpa','pressure','barometer','barometric_pressure','presion']
}

col_map = {}
for var, tokens in mapping_tokens.items():
    col_map[var] = find_col_by_tokens(tokens)

print("ℹ️ Columnas mapeadas (None significa no encontrada):")
for k,v in col_map.items():
    print(f"  {k}: {v}")

# función simple para calcular AQI aproximado desde PM2.5 (US EPA breakpoints)
def pm25_to_aqi(pm):
    if pm is None:
        return None
    try:
        pm = float(pm)
    except:
        return None
    bps = [
        (0.0, 12.0, 0, 50),
        (12.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 150.4, 151, 200),
        (150.5, 250.4, 201, 300),
        (250.5, 350.4, 301, 400),
        (350.5, 500.4, 401, 500)
    ]
    for (clow, chigh, ilow, ihigh) in bps:
        if clow <= pm <= chigh:
            aqi = (ihigh - ilow) / (chigh - clow) * (pm - clow) + ilow
            return round(aqi, 0)
    return None

# última lectura por estación
last_by_station = df.groupby('estacion_id', as_index=False).last()
latest_records = []
for _, r in last_by_station.iterrows():
    rec = {
        'estacion_id': str(r.get('estacion_id')),
        'nombre_estacion': r.get('nombre_estacion') if 'nombre_estacion' in r else None,
        'latitud': float(r['latitud']),
        'longitud': float(r['longitud']),
        'timestamp': r['timestamp'].isoformat() if not pd.isna(r['timestamp']) else None
    }
    for key in mapping_tokens.keys():
        col = col_map.get(key)
        if col:
            val = r.get(col)
            try:
                rec[key] = None if pd.isna(val) else float(val)
            except Exception:
                rec[key] = None
        else:
            rec[key] = None
    if (rec.get('aqi') is None) and rec.get('pm25') not in (None,):
        rec['aqi'] = pm25_to_aqi(rec.get('pm25'))
    latest_records.append(rec)

# construir historiales: resample 1H para las variables canónicas
max_points = 168
station_histories = {}
all_times_set = set()
vars_canonical = ['timestamps','pm25','pm10','pm1','temp','humidity','precip','aqi','wind_speed','wind_dir','pressure']

for station_id, g in df.groupby('estacion_id'):
    g = g.set_index('timestamp').sort_index()
    rec = {k: [] for k in vars_canonical}
    needed_cols = [col_map[v] for v in col_map if col_map[v] is not None]
    if not needed_cols:
        station_histories[str(station_id)] = rec
        continue
    res = g[needed_cols].resample('1H').mean()
    res = res.dropna(how='all')
    if res.empty:
        station_histories[str(station_id)] = rec
        continue
    timestamps = [ts.isoformat() for ts in res.index]
    all_times_set.update(timestamps)
    for v in vars_canonical:
        if v == 'timestamps':
            continue
        col = col_map.get(v)
        if col:
            vals = []
            for val in res[col].tolist():
                vals.append(None if pd.isna(val) else float(val))
            rec[v] = vals
        else:
            if v == 'aqi':
                pmvals = []
                pmcol = col_map.get('pm25')
                if pmcol and pmcol in res:
                    for val in res[pmcol].tolist():
                        pmvals.append(None if pd.isna(val) else pm25_to_aqi(val))
                rec[v] = pmvals if pmvals else [None]*len(timestamps)
            else:
                rec[v] = [None]*len(timestamps)
    if len(timestamps) > max_points:
        timestamps = timestamps[-max_points:]
        for k in rec:
            if k == 'timestamps': continue
            if rec[k]:
                rec[k] = rec[k][-max_points:]
    rec['timestamps'] = timestamps
    station_histories[str(station_id)] = rec

# ordenar all times
all_times = sorted(all_times_set, key=lambda x: datetime.fromisoformat(x)) if all_times_set else []

# estadísticas por estación (mean de columnas numéricas, n, rango temporal)
numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
numeric_cols = [c for c in numeric_cols if c not in ('latitud','longitud')]
station_stats = {}
for station_id, g in df.groupby('estacion_id'):
    stats = {}
    gg = g.copy()
    stats['n_muestras'] = int(len(gg))
    stats['primera_lectura'] = gg['timestamp'].min().isoformat() if not gg['timestamp'].isna().all() else None
    stats['ultima_lectura'] = gg['timestamp'].max().isoformat() if not gg['timestamp'].isna().all() else None
    for col in numeric_cols:
        try:
            m = gg[col].dropna().mean()
            stats[col] = None if pd.isna(m) else round(float(m), 2)
        except Exception:
            stats[col] = None
    # asegurar que stats tenga canónicas (si no están calculadas, intentar promediar desde mapeos)
    for v in ['pm25','temp','humidity','precip','aqi','pm1','pm10','wind_speed','pressure']:
        if v not in stats or stats.get(v) is None:
            col = col_map.get(v)
            if col and col in gg:
                try:
                    mv = gg[col].dropna().mean()
                    stats[v] = None if pd.isna(mv) else round(float(mv), 2)
                except:
                    stats[v] = None
    # si no hay aqi en stats pero hay pm25 promedio, calcular
    if (stats.get('aqi') in (None,)) and stats.get('pm25') not in (None,):
        stats['aqi'] = pm25_to_aqi(stats.get('pm25'))
    station_stats[str(station_id)] = stats

# etiquetas legibles (mapeo manual para detalles: nombres más entendibles)
label_map = {
    'pm25': 'PM2.5 (µg/m³)',
    'pm10': 'PM10 (µg/m³)',
    'pm1': 'PM1 (µg/m³)',
    'temp': 'Temperatura (°C)',
    'humidity': 'Humedad (%)',
    'precip': 'Precipitación (mm)',
    'aqi': 'ICA / AQI',
    'wind_speed': 'Velocidad del viento (km/h)',
    'wind_dir': 'Dirección del viento',
    'pressure': 'Presión (hPa)'
}

# Selección de hasta 10 campos relevantes para Detalles: priorizo indispensables y opcionales
priority_order = ['pm25','temp','humidity','precip','aqi','wind_speed','wind_dir','pressure','pm1','pm10']
selected_keys = []
for key in priority_order:
    any_non_null = any((station_stats[sid].get(key) not in (None,) for sid in station_stats))
    if any_non_null:
        selected_keys.append(key)
# si quedaron menos de 10, añadir otras numeric cols (convertir a legible)
for col in numeric_cols:
    if len(selected_keys) >= 10: break
    if col.lower() in selected_keys:
        continue
    # tratar nombres no canónicos
    if col not in selected_keys:
        selected_keys.append(col)
selected_keys = selected_keys[:10]

print("ℹ️ Campos finales para Detalles (limitados, legibles):")
for k in selected_keys:
    lab = label_map.get(k, k.replace('_',' '))
    print("   -", k, "→", lab)

# centro del mapa
center_lat = float(df['latitud'].mean())
center_lon = float(df['longitud'].mean())

# --- CALCULAR PROMEDIOS GLOBALES POR TIEMPO (para visualizaciones globales) ---
global_vars = ['pm25','temp','humidity','precip']
station_time_index = {}
for sid, rec in station_histories.items():
    station_time_index[sid] = rec.get('timestamps', [])

def last_value_before(rec, times_list, t_iso, var):
    if not times_list:
        return None
    i = bisect.bisect_right(times_list, t_iso) - 1
    if i < 0:
        return None
    vals = rec.get(var, [])
    if i >= len(vals):
        return None
    return vals[i]

global_averages = []
for t in all_times:
    row = {'timestamp': t}
    for v in global_vars:
        vals = []
        for sid, rec in station_histories.items():
            ts_list = station_time_index.get(sid, [])
            val = last_value_before(rec, ts_list, t, v)
            if val is not None:
                try:
                    f = float(val)
                    if not pd.isna(f): vals.append(f)
                except:
                    pass
        row[v] = round(sum(vals)/len(vals), 2) if vals else None
    global_averages.append(row)

# leyenda semántica (PM2.5) actualizada para reemplazo en template
legend = [
    {'max':10, 'label':'Excelente', 'color':'#2ecc71'},
    {'max':13, 'label':'Bueno', 'color':'#9ae66a'},
    {'max':35, 'label':'Regular', 'color':'#f1c40f'},
    {'max':55, 'label':'Malo', 'color':'#e67e22'},
    {'max':9999, 'label':'Peligroso', 'color':'#e74c3c'}
]

# Template HTML (sidebar para Detalles). Mantengo Chart.js + adapter, parser seguro y formatos date-fns.
# IMPORTANTE: todo el JS queda dentro de esta cadena triple-quoted para evitar errores de sintaxis en Python.
template = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Mapa RACiMo — Visualización (v4.4)</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/MarkerCluster.css"/>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/MarkerCluster.Default.css"/>
<style>
  :root{--panel-bg:#ffffff;--muted:#6b7280;--accent:#2563eb}
  html,body{height:100%;margin:0;padding:0;font-family:Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;background:#f7fafc;color:#111}
  #map{position:absolute;left:0;top:0;bottom:0;right:0}
  .controls-panel{position:absolute;left:14px;top:14px;z-index:1500;background:var(--panel-bg);padding:10px;border-radius:10px;box-shadow:0 6px 18px rgba(15,23,42,0.08);min-width:240px}
  .controls-panel input[type=range]{width:100%}
  .controls-panel .btn{display:inline-block;margin-right:6px}
  .floating-panel{position:fixed;right:18px;top:70px;width:520px;background:var(--panel-bg);border-radius:12px;box-shadow:0 18px 40px rgba(2,6,23,0.12);z-index:1600;padding:12px;display:none;border-left:6px solid transparent}
  .floating-panel .inner{display:flex;gap:10px}
  .chart-box{flex:1;min-width:260px;height:280px;border-radius:8px;overflow:hidden;background:#fff;padding:6px}
  .details-box{width:200px;max-height:320px;overflow:auto;padding:6px;border-left:1px solid #f1f5f9}
  .station-title{font-size:15px;font-weight:700;margin-bottom:4px}
  .small{font-size:13px;color:var(--muted)}
  .detalles-table{width:100%;border-collapse:collapse;font-size:13px}
  .detalles-table td{padding:6px 4px;border-bottom:1px solid #f2f4f7}
  .btn{padding:6px 8px;border-radius:6px;border:1px solid #e6eef8;background:#fff;cursor:pointer}
  .btn.primary{background:var(--accent);color:#fff;border:0}
  .legend{position:fixed;bottom:14px;left:14px;background:var(--panel-bg);padding:12px;border-radius:10px;z-index:1400;font-size:13px;box-shadow:0 8px 26px rgba(2,6,23,0.06)}
  .legend strong{display:block}
  .muted{color:var(--muted);font-size:13px}
  .global-visual{margin-top:10px;display:flex;gap:8px;align-items:center}
  .vis-card{width:86px;height:110px;border-radius:12px;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 10px 30px rgba(2,6,23,0.06);padding:8px}
  .vis-label{font-size:12px;margin-top:8px;color:var(--muted);text-align:center}
  #vis-tooltip{position:fixed;background:rgba(0,0,0,0.85);color:#fff;padding:6px 8px;border-radius:6px;font-size:12px;pointer-events:none;z-index:9999;display:none}
  @media (max-width:700px){ .floating-panel{right:8px;left:8px;width:auto} .details-box{display:none} }
</style>
</head>
<body>
<div id="map"></div>

<!-- Controles compactos (izquierda superior) -->
<div class="controls-panel" id="controls-panel">
  <div style="margin-bottom:6px"><strong id="global-title">Indicadores</strong></div>
  <div style="margin-top:8px;display:flex;gap:6px;align-items:center">
    <button id="global-play" class="btn primary">Reproducir</button>
    <button id="global-pause" class="btn" disabled>Pausar</button>
    <div style="flex:1"></div>
  </div>
  <div style="margin-top:8px;">
    <input id="time-slider" type="range" min="0" max="0" value="0" />
    <div class="small">Tiempo: <span id="time-label">—</span></div>
  </div>
  <div class="global-visual" id="global-visual">
    <div class="vis-card" id="vis-pm25" title="PM2.5 — promedio global"><canvas id="cv-pm25" width="86" height="86"></canvas><div class="vis-label" id="vis-label-pm25">PM2.5 — Global</div></div>
    <div class="vis-card" id="vis-temp" title="Temperatura — promedio global"><canvas id="cv-temp" width="86" height="86"></canvas><div class="vis-label" id="vis-label-temp">Temperatura — Global</div></div>
    <div class="vis-card" id="vis-humidity" title="Humedad — promedio global"><canvas id="cv-humidity" width="86" height="86"></canvas><div class="vis-label" id="vis-label-humidity">Humedad — Global</div></div>
    <div class="vis-card" id="vis-precip" title="Precipitación — promedio global"><canvas id="cv-precip" width="86" height="86"></canvas><div class="vis-label" id="vis-label-precip">Precipitación — Global</div></div>
  </div>
  <div style="margin-top:6px;" class="muted">Fuente: Red ciudadana</div>
</div>

<!-- Panel flotante: gráfico (izq) + detalles (der) dentro del mismo panel -->
<div class="floating-panel" id="floating-panel">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <div>
      <div class="station-title" id="panel-title">Seleccione una estación</div>
      <div class="small" id="panel-sub">Haga clic en un marcador y luego en "Ver detalles"</div>
    </div>
    <div>
      <button id="close-panel" class="btn">Cerrar</button>
    </div>
  </div>
  <div class="inner">
    <div class="chart-box"><canvas id="sidebar-chart" style="width:100%;height:100%"></canvas></div>
    <div class="details-box" id="details-box">
      <table class="detalles-table" id="detalles-table"></table>
    </div>
  </div>
</div>

<div class="legend">
  <strong>Calidad del aire</strong>
  <div class="small" style="margin-top:4px;font-weight:600">Leyenda PM2.5</div>
  <div style="margin-top:8px">
    <div><span style="color:#2ecc71">●</span> 0–10 — Excelente</div>
    <div><span style="color:#9ae66a">●</span> 10–13 — Bueno</div>
    <div><span style="color:#f1c40f">●</span> 13–35 — Regular</div>
    <div><span style="color:#e67e22">●</span> 35–55 — Malo</div>
    <div><span style="color:#e74c3c">●</span> &gt;55 — Peligroso</div>
  </div>
</div>

<div id="vis-tooltip"></div>

<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.1.0/leaflet.markercluster.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3"></script>

<script>
// DATOS EMBEBIDOS
const LATEST = __LATEST_JSON__;
const HIST = __HIST_JSON__;
const STATS = __STATS_JSON__;
const ALL_TIMES = __ALL_TIMES_JSON__;
const GLOBAL_AVG = __GLOBAL_AVG_JSON__;
const CENTER = [__CENTER_LAT__, __CENTER_LON__];
const VAR_LABELS = __LABELS_JSON__;
const DETAIL_KEYS = __DETAIL_KEYS_JSON__;
const LEGEND = __LEGEND_JSON__;

// mapa y markers
const map = L.map('map', { center: CENTER, zoom: 11, preferCanvas:true });
L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{maxZoom:20}).addTo(map);
const markers = {};
const markerLayer = L.markerClusterGroup();

// color según umbrales pedidos (0-10,10-13,13-35,35-55,>55)
function colorForPM(pm){
  if (pm === null || pm === undefined || isNaN(pm)) return '#888';
  const v = Number(pm);
  if (v <= 10) return '#2ecc71';
  if (v <= 13) return '#9ae66a';
  if (v <= 35) return '#f1c40f';
  if (v <= 55) return '#e67e22';
  return '#e74c3c';
}

LATEST.forEach(st => {
  const lat = st.latitud; const lon = st.longitud;
  if (lat === null || lon === null) return;
  const clr = colorForPM(st.pm25);
  const m = L.circleMarker([lat,lon], { radius:7, color: clr, fillColor: clr, fillOpacity:0.9, weight:1 });
  const popup = `<div style="min-width:220px"><strong>${st.nombre_estacion || st.estacion_id}</strong><div class="small">⏱ ${st.timestamp || '—'}</div><div style="margin-top:6px"><button class="btn" onclick="openPanel('${encodeURIComponent(st.estacion_id)}')">Ver detalles</button></div></div>`;
  m.bindPopup(popup);
  markerLayer.addLayer(m);
  markers[st.estacion_id] = { marker: m, latest: st };
});
map.addLayer(markerLayer);
try {
  const bounds = L.latLngBounds(LATEST.filter(x=>x.latitud && x.longitud).map(x=>[x.latitud,x.longitud]));
  map.fitBounds(bounds.pad(0.15));
} catch(e){}

// Panel flotante (gráfico + detalles a la derecha)
const sidebarChartCtx = document.getElementById('sidebar-chart').getContext('2d');
let sidebarChart = null;
let focusedStation = null; // cuando está enfocado en una estación

function openPanel(encodedSid) {
  const sid = decodeURIComponent(encodedSid);
  const st = markers[sid] ? markers[sid].latest : null;
  if (!st) return;
  focusedStation = sid;
  const clr = colorForPM(st.pm25);
  const panel = document.getElementById('floating-panel');
  panel.style.display = 'block';
  panel.style.borderLeft = `6px solid ${clr}`;
  document.getElementById('panel-title').textContent = st.nombre_estacion || sid;
  document.getElementById('panel-sub').textContent = `${st.latitud.toFixed(5)}, ${st.longitud.toFixed(5)} — ⏱ ${st.timestamp || '—'}`;
  // cambiar etiquetas a Estación
  document.getElementById('global-title').textContent = st.nombre_estacion || sid;
  document.getElementById('vis-label-pm25').textContent = 'PM2.5 — Estación';
  document.getElementById('vis-label-temp').textContent = 'Temperatura — Estación';
  document.getElementById('vis-label-humidity').textContent = 'Humedad — Estación';
  document.getElementById('vis-label-precip').textContent = 'Precipitación — Estación';

  // tabla: reordenamiento silencioso según prioridad + agregar 3/4 campos extras según disponibilidad
  const stats = STATS[sid] || {};
  const table = document.getElementById('detalles-table');
  table.innerHTML = '';

  const indispensable = ['temp','humidity','precip','pm25','aqi'];
  const optional = ['wind_speed','wind_dir','pressure','pm1','pm10'];
  const used = new Set();

  function addRowKey(k, label) {
    const v = stats[k];
    if (v===null || v===undefined) return false;
    const tr = document.createElement('tr');
    const td1 = document.createElement('td'); td1.textContent = (label||VAR_LABELS[k]||k.replace(/_/g,' ')); td1.style.fontWeight='600';
    const td2 = document.createElement('td'); td2.textContent = v;
    tr.appendChild(td1); tr.appendChild(td2); table.appendChild(tr);
    used.add(k);
    return true;
  }

  // First pass: show indispensables where available
  indispensable.forEach(k => { addRowKey(k); });

  // Second pass: for any indispensable not present, fill from optional or other numeric stats
  indispensable.forEach(k => {
    if (used.has(k)) return;
    // try optional
    for (const ok of optional){ if (!used.has(ok) && stats[ok]!==null && stats[ok]!==undefined){ addRowKey(ok); break; }}
    // try other numeric columns
    for (const nc of Object.keys(stats)){
      if (used.has(nc)) continue;
      if (['n_muestras','primera_lectura','ultima_lectura'].includes(nc)) continue;
      const v = stats[nc]; if (v!==null && v!==undefined){ addRowKey(nc); break; }
    }
  });

  // After ensuring indispensable positions filled where possible, append remaining optionals
  optional.forEach(k => { if (!used.has(k)) addRowKey(k); });

  // --- AQUI: añadir 3 o 4 campos extras segun lo solicitado ---
  // criterio: si la estación ya tiene al menos 3 campos mostrados, añadimos 3 extras; si tiene menos (muy vacía), añadimos 4.
  const currentShown = used.size;
  const extrasToAdd = currentShown >= 3 ? 3 : 4;
  let addedExtra = 0;
  for (const nc of Object.keys(stats)){
    if (addedExtra >= extrasToAdd) break;
    if (used.has(nc)) continue;
    if (['n_muestras','primera_lectura','ultima_lectura'].includes(nc)) continue;
    const v = stats[nc]; if (v===null || v===undefined) continue;
    addRowKey(nc);
    addedExtra++;
  }

  // Finally, include analyzer ID / station ID (always)
  const idTr = document.createElement('tr');
  const idTd1 = document.createElement('td'); idTd1.textContent = 'ID del analizador'; idTd1.style.fontWeight='600';
  const idTd2 = document.createElement('td'); idTd2.textContent = sid;
  idTr.appendChild(idTd1); idTr.appendChild(idTd2); table.appendChild(idTr);

  // dibujar chart usando HIST[sid]
  const rec = HIST[sid];
  if (!rec || !rec.timestamps) {
    if (sidebarChart) { try { sidebarChart.destroy(); } catch(e){} sidebarChart = null; }
    return;
  }
  const labels = rec.timestamps;
  const ds1 = rec.pm25 || [];
  const ds2 = rec.temp || [];
  if (sidebarChart) { try { sidebarChart.destroy(); } catch(e){} sidebarChart = null; }
  sidebarChart = new Chart(sidebarChartCtx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        { label: VAR_LABELS['pm25'] || 'PM2.5', data: ds1, spanGaps:true, yAxisID:'y1', tension:0.3, pointRadius:0, borderWidth:1.5 },
        { label: VAR_LABELS['temp'] || 'Temperatura', data: ds2, spanGaps:true, yAxisID:'y2', tension:0.3, pointRadius:0, borderWidth:1.5 }
      ]
    },
    options: {
      maintainAspectRatio:false,
      responsive:true,
      animation:{ duration:250, easing:'easeOutCubic' },
      elements:{ line:{ tension:0.3 } },
      interaction:{mode:'index', intersect:false},
      plugins:{legend:{display:true}},
      scales: {
        x: { type:'time', time:{ parser: (v) => new Date(v), tooltipFormat:'yyyy-MM-dd HH:mm' } },
        y1: { type:'linear', position:'left', title:{display:true,text: VAR_LABELS['pm25'] || 'PM2.5'}, ticks:{ suggestedMin: 0 } },
        y2: { type:'linear', position:'right', title:{display:true,text: VAR_LABELS['temp'] || 'Temperatura'}, grid:{drawOnChartArea:false}, ticks:{ suggestedMin: 0 } }
      }
    }
  });
}

document.getElementById('close-panel').onclick = () => {
  try { if (sidebarChart) sidebarChart.destroy(); } catch(e){}
  document.getElementById('floating-panel').style.display = 'none';
  focusedStation = null;
  document.getElementById('global-title').textContent = 'Indicadores';
  document.getElementById('vis-label-pm25').textContent = 'PM2.5 — Global';
  document.getElementById('vis-label-temp').textContent = 'Temperatura — Global';
  document.getElementById('vis-label-humidity').textContent = 'Humedad — Global';
  document.getElementById('vis-label-precip').textContent = 'Precipitación — Global';
}

// helper: binary search inside rec.timestamps para obtener valores hasta t_iso
function getValuesForStationAtTime(sid, t_iso){
  const rec = HIST[sid];
  if (!rec || !rec.timestamps) return {pm25:null, temp:null, humidity:null, precip:null};
  const arr = rec.timestamps;
  let lo = 0, hi = arr.length - 1, j = -1;
  while (lo <= hi){
    const mid = Math.floor((lo+hi)/2);
    if (arr[mid] <= t_iso){ j = mid; lo = mid + 1; } else { hi = mid - 1; }
  }
  if (j < 0) return {pm25:null, temp:null, humidity:null, precip:null};
  const getVal = (k) => (rec[k] && rec[k].length>j) ? rec[k][j] : null;
  return { pm25: getVal('pm25'), temp: getVal('temp'), humidity: getVal('humidity'), precip: getVal('precip') };
}

// Global controls: slider y play (rápido)
const globalPlay = document.getElementById('global-play');
const globalPause = document.getElementById('global-pause');
const timeSlider = document.getElementById('time-slider');
const timeLabel = document.getElementById('time-label');
let playInterval = null;
let timeIndex = 0;
const times = ALL_TIMES.slice();
timeSlider.min = 0; timeSlider.max = Math.max(0, times.length - 1); timeSlider.value = 0;
timeLabel.textContent = times.length ? times[0].replace('T',' ') : '—';

function updateMarkersForTime(idx) {
  const t = times[idx];
  timeLabel.textContent = t ? t.replace('T',' ') : '—';
  // colorear marcadores siempre por PM2.5
  for (const sid in HIST) {
    const rec = HIST[sid];
    if (!rec || !rec.timestamps) continue;
    const arr = rec.timestamps;
    let j = -1; let lo=0, hi=arr.length-1;
    while (lo <= hi) {
      const mid = Math.floor((lo+hi)/2);
      if (arr[mid] <= t) { j = mid; lo = mid + 1; } else hi = mid - 1;
    }
    const val = j >= 0 ? (rec['pm25'] ? rec['pm25'][j] : null) : null;
    const mobj = markers[sid];
    if (!mobj) continue;
    try { const clr = colorForPM(val); mobj.marker.setStyle({ color: clr, fillColor: clr }); } catch(e){}
  }
}

timeSlider.addEventListener('input', (e) => {
  timeIndex = Number(e.target.value);
  updateMarkersForTime(timeIndex);
});

function startGlobalPlay() {
  if (playInterval) return;
  globalPlay.disabled = true; globalPause.disabled = false;
  // intervalo rápido (90ms)
  playInterval = setInterval(() => {
    updateMarkersForTime(timeIndex);
    timeSlider.value = timeIndex;
    timeIndex++;
    if (timeIndex >= times.length) { clearInterval(playInterval); playInterval = null; globalPlay.disabled=false; globalPause.disabled=true; timeIndex=0; }
  }, 90);
}
function stopGlobalPlay() {
  if (!playInterval) return;
  clearInterval(playInterval); playInterval = null;
  globalPlay.disabled = false; globalPause.disabled = true;
}
globalPlay.onclick = startGlobalPlay; globalPause.onclick = stopGlobalPlay;
if (times.length) updateMarkersForTime(0);

// --- DIBUJO DE ICONOS ANIMADOS (funciones definidas aquí dentro del template) ---
let animStart = Date.now();
function drawGlobalVisual(g){
  const phase = (Date.now() - animStart) / 700;
  drawPM25Icon(document.getElementById('cv-pm25'), g.pm25, phase);
  drawTempIcon(document.getElementById('cv-temp'), g.temp, phase);
  drawHumidityIcon(document.getElementById('cv-humidity'), g.humidity, phase);
  drawPrecipIcon(document.getElementById('cv-precip'), g.precip, phase);
}

function clearCanvas(cv){ const ctx = cv.getContext('2d'); ctx.clearRect(0,0,cv.width,cv.height); return ctx; }

// drawPM25Icon: usa los umbrales nuevos y asume limpio cuando null
function drawPM25Icon(cv, pmVal, phase){
  const ctx = clearCanvas(cv);
  const cx = cv.width/2, cy = cv.height/2;
  const isAssumedClean = (pmVal === null || pmVal === undefined);
  const displayVal = isAssumedClean ? 6 : pmVal;

  // base circular
  ctx.beginPath(); ctx.arc(cx,cy,36,0,Math.PI*2); ctx.fillStyle = '#ffffff'; ctx.fill();
  ctx.beginPath(); ctx.arc(cx,cy-4,15,0,Math.PI*2); ctx.fillStyle = '#fff9f1'; ctx.fill();

  // ojos
  ctx.fillStyle = '#222'; ctx.beginPath(); ctx.ellipse(cx-5, cy-7, 2.6, 3.2, 0,0,Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.ellipse(cx+5, cy-7, 2.6, 3.2, 0,0,Math.PI*2); ctx.fill();
  // brillo ojos
  ctx.fillStyle = 'rgba(255,255,255,0.95)'; ctx.beginPath(); ctx.arc(cx-6.2, cy-8.2, 0.8,0,Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.arc(cx+3.8, cy-8.2, 0.8,0,Math.PI*2); ctx.fill();

  // expresion segun rangos:
  // 0-10 muy feliz, 10-13 un poco feliz, 13-35 neutral, 35-55 mascarilla, >55 triste
  if (displayVal <= 10){
    ctx.strokeStyle = '#2ecc71'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx,cy+6,8,0.18*Math.PI,0.82*Math.PI); ctx.stroke();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(cx+11,cy-9,1.8,0,Math.PI*2); ctx.fill();
    ctx.beginPath(); ctx.arc(cx-13,cy-7,1.4,0,Math.PI*2); ctx.fill();
  } else if (displayVal <= 13){
    ctx.strokeStyle = '#9ae66a'; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.arc(cx,cy+6,7,0.25*Math.PI,0.75*Math.PI); ctx.stroke();
  } else if (displayVal <= 35){
    ctx.strokeStyle = '#f1c40f'; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(cx-4,cy+6); ctx.lineTo(cx+4,cy+6); ctx.stroke();
  } else if (displayVal <= 55){
    ctx.fillStyle = '#fff'; roundRect(ctx, cx-11, cy+2, 22, 10, 4, true, false);
    ctx.strokeStyle = '#c64b2a'; ctx.lineWidth = 1.1; ctx.beginPath(); ctx.moveTo(cx-7, cy+4); ctx.lineTo(cx+7, cy+4); ctx.stroke();
  } else {
    ctx.strokeStyle = '#e74c3c'; ctx.lineWidth = 1.8; ctx.beginPath(); ctx.moveTo(cx-6,cy+8); ctx.quadraticCurveTo(cx,cy+3, cx+6,cy+8); ctx.stroke();
    ctx.fillStyle = 'rgba(200,50,50,0.06)'; ctx.beginPath(); ctx.arc(cx, cy-4, 22, 0, Math.PI*2); ctx.fill();
  }

  // partículas si hay contaminación real
  const smogAlpha = isAssumedClean ? 0 : Math.max(0, Math.min(0.7, (displayVal-10)/140));
  if (smogAlpha > 0.02){
    const parts = Math.min(14, Math.floor(smogAlpha*50));
    for (let i=0;i<parts;i++){
      const rx = cx - 18 + Math.random()*36 + Math.sin(phase+i)*2;
      const ry = cy - 12 + Math.random()*18 + Math.cos(phase+i)*2;
      ctx.fillStyle = `rgba(150,150,150,${smogAlpha*0.08})`;
      ctx.beginPath(); ctx.arc(rx, ry, 1.2 + Math.random()*1.6, 0, Math.PI*2); ctx.fill();
    }
  }
}

function drawTempIcon(cv, tempVal, phase){
  const ctx = clearCanvas(cv);
  const cx = cv.width/2, cy = cv.height/2;
  const t = tempVal==null? 20 : tempVal;
  const p = Math.max(0, Math.min(1, (t + 10) / 50));
  const r = 9 + p*14;
  ctx.beginPath(); ctx.arc(cx,cy, r+10,0,Math.PI*2); ctx.fillStyle = `rgba(255,200,60,${0.06 + p*0.45})`; ctx.fill();
  const g = ctx.createRadialGradient(cx,cy,r*0.2,cx,cy,r); g.addColorStop(0,'#fffbe6'); g.addColorStop(1,colorForTemp(t));
  ctx.beginPath(); ctx.arc(cx,cy, r,0,Math.PI*2); ctx.fillStyle = g; ctx.fill();
  ctx.save(); ctx.translate(cx,cy);
  for (let i=0;i<10;i++){
    const ang = i*(Math.PI*2/10) + phase*0.6;
    const len = r + 6 + (i%2?2:0);
    ctx.beginPath(); ctx.moveTo(Math.cos(ang)*(r*0.6), Math.sin(ang)*(r*0.6)); ctx.lineTo(Math.cos(ang)*len, Math.sin(ang)*len);
    ctx.strokeStyle = `rgba(255,170,60,${0.25 + 0.6*p})`; ctx.lineWidth = 1.6; ctx.stroke();
  }
  ctx.restore();
  if (t < 8){ ctx.globalAlpha = 0.12; ctx.fillStyle = '#eaf3ff'; ctx.beginPath(); ctx.ellipse(cx+8,cy+6,10,6,0,0,Math.PI*2); ctx.fill(); ctx.globalAlpha = 1.0; }
}
function colorForTemp(v){ if (v<=0) return '#4ea3ff'; if (v<=15) return '#9fd1ff'; if (v<=25) return '#ffd86b'; if (v<=35) return '#ffb34d'; return '#ff6b4d'; }

function drawHumidityIcon(cv, humVal, phase){
  const ctx = clearCanvas(cv);
  const cx = cv.width/2, cy = cv.height/2;
  ctx.beginPath(); ctx.ellipse(cx, cy-4, 20, 22, 0, 0, Math.PI*2); ctx.fillStyle = '#f5fcff'; ctx.fill();
  if (humVal!=null){
    const p = Math.max(0, Math.min(1, humVal/100));
    const wave = Math.sin(phase*2 + p*6) * 1.2;
    const fy = cy + 16 - p*32 + wave;
    const hr = 12 + p*6;
    const grd = ctx.createLinearGradient(cx, fy-hr, cx, fy+hr);
    grd.addColorStop(0,'#cfeefe'); grd.addColorStop(1,'#5dade2');
    ctx.beginPath(); ctx.ellipse(cx, fy-4, 14, hr, 0, 0, Math.PI*2); ctx.fillStyle = grd; ctx.fill();
    ctx.beginPath(); ctx.ellipse(cx-4, cy-10, 6, 3, -0.6, 0, Math.PI*2); ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.fill();
    if (p > 0.7){ for (let i=0;i<3;i++){ ctx.fillStyle = 'rgba(93,173,226,0.12)'; ctx.beginPath(); ctx.arc(cx-14 + i*7, cy+10 + (i%2)*3, 2 + i*0.6,0,Math.PI*2); ctx.fill(); } }
  }
}

function drawPrecipIcon(cv, prVal, phase){
  const ctx = clearCanvas(cv);
  const cx = cv.width/2, cy = cv.height/2;
  ctx.beginPath(); ctx.ellipse(cx-12,cy-10,12,10,0,0,Math.PI*2); ctx.fillStyle='#f7f9fc'; ctx.fill();
  ctx.beginPath(); ctx.ellipse(cx+6,cy-10,14,12,0,0,Math.PI*2); ctx.fill();
  ctx.beginPath(); ctx.rect(cx-18,cy-4,36,16); ctx.fill();
  const intensity = prVal==null? 0 : Math.min(1, prVal/40);
  const drops = prVal==null? 1 : Math.min(18, 1 + Math.floor(intensity*17));
  for (let i=0;i<drops;i++){
    const t = ((phase*0.8) + i*0.12) % 1;
    const jitter = Math.sin(phase*2 + i) * 2;
    const x = cx - (drops*3)/2 + i*4 + jitter;
    const y = cy + 6 + (t*(32 + intensity*30));
    const h = 4 + intensity*8;
    ctx.beginPath(); ctx.ellipse(x,y,2.8, h, 0,0,Math.PI*2); ctx.fillStyle = intensity>0? '#2f78b5' : '#cbd5e1'; ctx.fill();
    if (t > 0.92 && intensity > 0.25){ ctx.beginPath(); ctx.fillStyle = `rgba(47,120,181,${0.5*intensity})`; ctx.ellipse(x, cy+32, 6 + intensity*6, 1 + intensity*2, 0, 0, Math.PI*2); ctx.fill(); }
  }
}

// utilidad: redondear rect
function roundRect(ctx, x, y, w, h, r, fill, stroke){ if (typeof r === 'undefined') r = 5; ctx.beginPath(); ctx.moveTo(x+r, y); ctx.arcTo(x+w, y, x+w, y+h, r); ctx.arcTo(x+w, y+h, x, y+h, r); ctx.arcTo(x, y+h, x, y, r); ctx.arcTo(x, y, x+w, y, r); ctx.closePath(); if (fill) ctx.fill(); if (stroke) ctx.stroke(); }

// --- TOOLTIP y anim loop ---
const tooltip = document.getElementById('vis-tooltip');
function showTooltip(text, x, y){ tooltip.style.left = (x + 12) + 'px'; tooltip.style.top = (y + 12) + 'px'; tooltip.innerText = text; tooltip.style.display = 'block'; }
function hideTooltip(){ tooltip.style.display = 'none'; }

function getCurrentParamValue(param){
  const idx = Math.max(0, Math.min(GLOBAL_AVG.length-1, timeIndex));
  if (focusedStation){
    const tIso = ALL_TIMES.length? ALL_TIMES[timeIndex] : null;
    if (!tIso) return null;
    const vals = getValuesForStationAtTime(focusedStation, tIso);
    return vals[param];
  } else {
    const g = GLOBAL_AVG[idx] || {};
    return g[param];
  }
}

[['cv-pm25','pm25','µg/m³'], ['cv-temp','temp','°C'], ['cv-humidity','humidity','%'], ['cv-precip','precip','mm']].forEach(([id,param,unit])=>{
  const c = document.getElementById(id);
  c.addEventListener('mousemove', (ev)=>{
    let v = getCurrentParamValue(param);
    let disp = (v===null||v===undefined)? '—' : v;
    if (param==='pm25' && (v===null||v===undefined)) disp = '— (asumido limpio)';
    const txt = `${(param==='pm25')? 'PM2.5': (param==='temp')? 'Temperatura': (param==='humidity')? 'Humedad': 'Precipitación'}: ${disp} ${unit}`;
    showTooltip(txt, ev.clientX, ev.clientY);
  });
  c.addEventListener('mouseleave', hideTooltip);
});

function animLoop(){
  const idx = Math.max(0, Math.min(GLOBAL_AVG.length-1, timeIndex));
  const g = focusedStation ? getValuesForStationAtTime(focusedStation, ALL_TIMES[timeIndex]) : GLOBAL_AVG[idx] || {};
  drawGlobalVisual(g);
  requestAnimationFrame(animLoop);
}
requestAnimationFrame(animLoop);

</script>
</body>
</html>
"""

# reemplazos JSON y guardado
html = template.replace("__LATEST_JSON__", json.dumps(latest_records, ensure_ascii=False))
html = html.replace("__HIST_JSON__", json.dumps(station_histories, ensure_ascii=False))
html = html.replace("__STATS_JSON__", json.dumps(station_stats, ensure_ascii=False))
html = html.replace("__ALL_TIMES_JSON__", json.dumps(all_times, ensure_ascii=False))
html = html.replace("__GLOBAL_AVG_JSON__", json.dumps(global_averages, ensure_ascii=False))
html = html.replace("__LABELS_JSON__", json.dumps(label_map, ensure_ascii=False))
html = html.replace("__DETAIL_KEYS_JSON__", json.dumps(selected_keys, ensure_ascii=False))
html = html.replace("__CENTER_LAT__", f"{center_lat:.6f}")
html = html.replace("__CENTER_LON__", f"{center_lon:.6f}")
html = html.replace("__LEGEND_JSON__", json.dumps(legend, ensure_ascii=False))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

size_kb = os.path.getsize(OUT)/1024
print(f"✅ HTML v4.4 generado: {OUT} ({size_kb:.1f} KB)")
print("Servir: python3 -m http.server 8000  y abrir http://localhost:8000/" + OUT)

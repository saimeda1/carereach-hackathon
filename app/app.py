"""
CareReach — AI-Powered Healthcare Access Planning for India
DAIS for Good 2026 · Track 2: AI Agents for Social Good

Sleek, modern Databricks App (Gradio) backed by the carereach_gold tables:
  • workspace.carereach_gold.gold_care_gap_analysis
  • workspace.carereach_gold.gold_facility_trust_aggregates
  • workspace.carereach_gold.gold_demand_supply_overlay

UI design: dark "command-center" analytics layout — KPI tiles, a coherent
chart system, and a hero India geospatial heatmap (state choropleth +
district demand-supply bubbles), inspired by modern dashboard best practices
(awesome-dashboard).
"""

import os
import json
import functools

import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from databricks import sql
from mlflow.deployments import get_deploy_client

# ============================================================================
# CONFIGURATION
# ============================================================================
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "carereach-planning-agent")
SQL_WAREHOUSE_ID = os.environ.get("SQL_WAREHOUSE_ID", "4997437721116114")
HOST = os.environ.get("DATABRICKS_HOST", "https://dbc-0ccb8f72-3364.cloud.databricks.com")

CATALOG = "workspace"
GOLD = f"{CATALOG}.carereach_gold"
T_GAP = f"{GOLD}.gold_care_gap_analysis"
T_TRUST = f"{GOLD}.gold_facility_trust_aggregates"
T_OVERLAY = f"{GOLD}.gold_demand_supply_overlay"

# ---- Design tokens (single source of truth for the whole UI) ----------------
INK = "#070b14"           # page background (near-black navy)
PANEL = "#0e1626"         # card / panel background
PANEL_2 = "#111d31"       # nested surfaces
STROKE = "rgba(148,163,184,0.14)"
TEXT = "#e6edf6"
MUTED = "#8a99ad"
ACCENT = "#38bdf8"        # cyan  — primary
ACCENT_2 = "#818cf8"      # indigo — secondary
TEAL = "#2dd4bf"
AMBER = "#f59e0b"
ROSE = "#fb7185"
GRID = "rgba(148,163,184,0.10)"

# Sequential scale used across all geo / heat visuals for visual consistency
SEQ_SCALE = [
    [0.0, "#0b2540"], [0.25, "#114e7a"], [0.5, "#1d7fb8"],
    [0.75, "#38bdf8"], [1.0, "#a5e8ff"],
]
GAP_SCALE = [
    [0.0, "#0e3a2e"], [0.35, "#3f7e4f"], [0.6, "#f59e0b"],
    [0.8, "#f4733b"], [1.0, "#fb3b5c"],
]


# ============================================================================
# DATA ACCESS
# ============================================================================
def _connection():
    """Databricks SQL connection via OAuth M2M (Databricks Apps service principal)."""
    return sql.connect(
        server_hostname=HOST.replace("https://", "").rstrip("/"),
        http_path=f"/sql/1.0/warehouses/{SQL_WAREHOUSE_ID}",
        credentials_provider=lambda: (
            os.environ.get("DATABRICKS_CLIENT_ID"),
            os.environ.get("DATABRICKS_CLIENT_SECRET"),
        ),
    )


def run_query(query: str) -> pd.DataFrame:
    """Execute SQL and return a DataFrame using the cursor (no pandas/SQLAlchemy dep)."""
    with _connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


def safe(default):
    """Decorator: never let a data hiccup crash the UI; return a default instead."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **k):
            try:
                return fn(*a, **k)
            except Exception as e:  # noqa: BLE001
                print(f"[CareReach] {fn.__name__} failed: {e}")
                return default() if callable(default) else default
        return wrap
    return deco


# ---- KPI metrics ------------------------------------------------------------
@safe(default=dict)
def fetch_metrics() -> dict:
    df = run_query(f"""
        SELECT
          COUNT(*)                                                      AS gap_regions,
          SUM(CASE WHEN intervention_priority IN ('P1_IMMEDIATE','P2_HIGH')
                   THEN 1 ELSE 0 END)                                   AS priority_gaps,
          SUM(CASE WHEN confidence_level = 'HIGH' THEN 1 ELSE 0 END)    AS high_conf_gaps,
          SUM(CASE WHEN gap_phantom_facilities THEN 1 ELSE 0 END)       AS phantom_regions,
          ROUND(AVG(avg_trust), 3)                                      AS avg_trust,
          SUM(facility_count)                                           AS facilities
        FROM {T_GAP}
    """)
    r = df.iloc[0]
    districts = run_query(
        f"SELECT COUNT(DISTINCT district) AS d FROM {T_GAP} WHERE district IS NOT NULL"
    ).iloc[0]["d"]
    return {
        "gap_regions": int(r["gap_regions"] or 0),
        "priority_gaps": int(r["priority_gaps"] or 0),
        "high_conf_gaps": int(r["high_conf_gaps"] or 0),
        "phantom_regions": int(r["phantom_regions"] or 0),
        "avg_trust": float(r["avg_trust"] or 0),
        "facilities": int(r["facilities"] or 0),
        "districts": int(districts or 0),
    }


# ---- Geospatial: state choropleth ------------------------------------------
@safe(default=pd.DataFrame)
def fetch_state_geo() -> pd.DataFrame:
    return run_query(f"""
        SELECT
          UPPER(TRIM(state)) AS state,
          COUNT(*)                       AS gap_regions,
          SUM(facility_count)            AS facilities,
          ROUND(AVG(composite_gap_score),4) AS avg_gap_score,
          ROUND(AVG(avg_trust),3)        AS avg_trust,
          SUM(CASE WHEN intervention_priority IN ('P1_IMMEDIATE','P2_HIGH')
                   THEN 1 ELSE 0 END)    AS priority_gaps
        FROM {T_GAP}
        WHERE state IS NOT NULL AND TRIM(state) <> ''
        GROUP BY UPPER(TRIM(state))
        ORDER BY avg_gap_score DESC
    """)


# ---- Geospatial: district demand-supply (lat/long bubbles) ------------------
@safe(default=pd.DataFrame)
def fetch_district_points() -> pd.DataFrame:
    """District-level points from the care-gap table (has lat/long)."""
    return run_query(f"""
        SELECT
          state, district, latitude, longitude,
          composite_gap_score, facility_count, avg_trust,
          confidence_level, gap_characterization, intervention_priority
        FROM {T_GAP}
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND latitude BETWEEN 6 AND 38 AND longitude BETWEEN 67 AND 98
        ORDER BY composite_gap_score DESC
        LIMIT 4000
    """)


# ---- Demand-supply overlay (NFHS-5) ----------------------------------------
@safe(default=pd.DataFrame)
def fetch_demand_supply() -> pd.DataFrame:
    return run_query(f"""
        SELECT
          state, district,
          demand_intensity_score,
          demand_supply_mismatch_index,
          avg_gap_score,
          stunting_under5_pct,
          anaemia_children_pct,
          full_immunization_pct,
          total_estimated_pop,
          demand_supply_priority
        FROM {T_OVERLAY}
        WHERE demand_supply_mismatch_index IS NOT NULL
        ORDER BY demand_supply_mismatch_index DESC
        LIMIT 200
    """)


@safe(default=pd.DataFrame)
def fetch_gap_distribution() -> pd.DataFrame:
    return run_query(f"""
        SELECT gap_characterization AS gap_type, COUNT(*) AS count
        FROM {T_GAP}
        WHERE gap_characterization IS NOT NULL
        GROUP BY gap_characterization
        ORDER BY count DESC
    """)


@safe(default=pd.DataFrame)
def fetch_priority_breakdown() -> pd.DataFrame:
    return run_query(f"""
        SELECT intervention_priority AS priority,
               confidence_level      AS confidence,
               COUNT(*)              AS count
        FROM {T_GAP}
        WHERE intervention_priority IS NOT NULL
        GROUP BY intervention_priority, confidence_level
        ORDER BY priority
    """)


@safe(default=pd.DataFrame)
def fetch_top_districts() -> pd.DataFrame:
    return run_query(f"""
        SELECT district, state,
               composite_gap_score, facility_count, avg_trust, gap_characterization
        FROM {T_GAP}
        WHERE district IS NOT NULL
        ORDER BY composite_gap_score DESC
        LIMIT 12
    """)


@safe(default=pd.DataFrame)
def fetch_trust_distribution() -> pd.DataFrame:
    return run_query(f"""
        SELECT
          CASE
            WHEN avg_trust_score >= 0.7 THEN 'High (0.70–1.00)'
            WHEN avg_trust_score >= 0.5 THEN 'Medium (0.50–0.70)'
            WHEN avg_trust_score >= 0.3 THEN 'Low (0.30–0.50)'
            ELSE 'Very Low (<0.30)'
          END AS trust_tier,
          COUNT(*) AS count
        FROM {T_TRUST}
        WHERE avg_trust_score IS NOT NULL AND aggregation_level = 'district'
        GROUP BY 1
        ORDER BY 1
    """)


# ============================================================================
# CHART HELPERS — one consistent theme everywhere
# ============================================================================
def _style(fig, height=360, title=None, legend=True):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, family="Inter, system-ui, sans-serif", size=13),
        margin=dict(l=10, r=10, t=46 if title else 12, b=10),
        height=height,
        title=dict(text=title, font=dict(size=15, color=TEXT), x=0.01, y=0.97) if title else None,
        showlegend=legend,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11)),
        hoverlabel=dict(bgcolor=PANEL_2, bordercolor=STROKE, font=dict(color=TEXT)),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, color=MUTED)
    return fig


def _empty(msg="No data available"):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=MUTED, size=14))
    return _style(fig, height=360, legend=False)


# ---- HERO: India geospatial heatmap ----------------------------------------
def create_india_map():
    """
    High-quality India geospatial visual:
      • Choropleth of state-level average care-gap score (GeoJSON states)
      • District bubbles sized by facility count, colored by gap severity
    """
    states = fetch_state_geo()
    points = fetch_district_points()

    fig = go.Figure()

    # Layer 1 — state choropleth via India states GeoJSON
    geojson_url = (
        "https://raw.githubusercontent.com/Subhash9325/"
        "GeoJson-Data-of-Indian-States/master/Indian_States"
    )
    if not states.empty:
        try:
            import urllib.request
            with urllib.request.urlopen(geojson_url, timeout=20) as resp:
                geojson = json.load(resp)
            # Map our UPPER-cased state names to the GeoJSON feature ids
            feat_names = {f["properties"].get("NAME_1", "").upper(): f
                          for f in geojson["features"]}
            states["match"] = states["state"].apply(
                lambda s: s if s in feat_names else None
            )
            fig.add_trace(go.Choropleth(
                geojson=geojson,
                locations=states["match"],
                z=states["avg_gap_score"],
                featureidkey="properties.NAME_1",
                colorscale=GAP_SCALE,
                marker_line_color="rgba(255,255,255,0.18)",
                marker_line_width=0.5,
                colorbar=dict(
                    title=dict(text="Avg gap<br>score", font=dict(color=MUTED, size=11)),
                    tickfont=dict(color=MUTED, size=10), thickness=12, len=0.55,
                    x=0.98, bgcolor="rgba(0,0,0,0)",
                ),
                hovertext=states["state"].str.title(),
                hovertemplate="<b>%{hovertext}</b><br>Avg gap score: %{z:.3f}<extra></extra>",
                name="State gap score",
            ))
        except Exception as e:  # GeoJSON unreachable in restricted nets -> bubbles only
            print(f"[CareReach] state choropleth skipped: {e}")

    # Layer 2 — district bubbles (lat/long) colored by gap severity
    if not points.empty:
        fig.add_trace(go.Scattergeo(
            lon=points["longitude"], lat=points["latitude"],
            mode="markers",
            marker=dict(
                size=(points["facility_count"].clip(lower=1) ** 0.5) * 3 + 4,
                color=points["composite_gap_score"],
                colorscale="YlOrRd",
                cmin=0, cmax=points["composite_gap_score"].max() or 1,
                line=dict(width=0.4, color="rgba(0,0,0,0.5)"),
                opacity=0.78, showscale=False,
            ),
            customdata=points[["district", "state", "facility_count",
                               "gap_characterization", "confidence_level"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b>, %{customdata[1]}<br>"
                "Gap score: %{marker.color:.3f}<br>"
                "Facilities: %{customdata[2]}<br>"
                "Type: %{customdata[3]} · %{customdata[4]} confidence<extra></extra>"
            ),
            name="District hotspots",
        ))

    fig.update_geos(
        projection_type="mercator",
        center=dict(lat=22.8, lon=82.5),
        lataxis_range=[6, 37], lonaxis_range=[67, 98],
        showcountries=True, countrycolor="rgba(148,163,184,0.30)", countrywidth=0.6,
        showcoastlines=True, coastlinecolor="rgba(148,163,184,0.35)", coastlinewidth=0.6,
        showland=True, landcolor="#0c1422",
        showocean=True, oceancolor="#060a12",
        showlakes=False, showframe=False, resolution=50,
        bgcolor="rgba(0,0,0,0)",
    )
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT, family="Inter"),
        margin=dict(l=0, r=0, t=10, b=0), height=560,
        legend=dict(orientation="h", y=0.02, x=0.01, bgcolor="rgba(14,22,38,0.6)",
                    font=dict(color=MUTED, size=11)),
    )
    if states.empty and points.empty:
        return _empty("Geospatial data unavailable — check warehouse connection")
    return fig


def create_demand_supply_map():
    """Demand-supply bubble matrix: NFHS-5 disease burden vs facility gap."""
    df = fetch_demand_supply()
    if df.empty:
        return _empty()
    fig = px.scatter(
        df, x="demand_intensity_score", y="avg_gap_score",
        size="total_estimated_pop", color="demand_supply_mismatch_index",
        hover_name="district",
        hover_data={"state": True, "stunting_under5_pct": ":.1f",
                    "anaemia_children_pct": ":.1f", "demand_supply_priority": True,
                    "total_estimated_pop": ":,.0f"},
        color_continuous_scale=GAP_SCALE, size_max=34,
        labels={"demand_intensity_score": "Health-burden (NFHS-5 demand)",
                "avg_gap_score": "Facility supply gap",
                "demand_supply_mismatch_index": "Mismatch"},
    )
    fig.update_traces(marker=dict(line=dict(width=0.5, color="rgba(255,255,255,0.25)")))
    fig.update_coloraxes(colorbar=dict(title="Mismatch", tickfont=dict(color=MUTED),
                                       thickness=12, len=0.7))
    return _style(fig, height=460, title="Demand vs Supply — where burden is high and care is thin")


def create_gap_chart():
    df = fetch_gap_distribution()
    if df.empty:
        return _empty()
    palette = [ROSE, AMBER, ACCENT, ACCENT_2, TEAL, "#94a3b8", "#c084fc"]
    fig = go.Figure(go.Bar(
        x=df["count"], y=df["gap_type"], orientation="h",
        marker=dict(color=palette[: len(df)], line=dict(width=0)),
        text=df["count"], textposition="outside",
        textfont=dict(color=MUTED, size=11),
        hovertemplate="<b>%{y}</b><br>%{x} regions<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    return _style(fig, height=360, title="Gap characterization", legend=False)


def create_priority_chart():
    df = fetch_priority_breakdown()
    if df.empty:
        return _empty()
    pivot = df.pivot_table(index="priority", columns="confidence",
                           values="count", aggfunc="sum", fill_value=0)
    order = ["P1_IMMEDIATE", "P2_HIGH", "P3_MODERATE",
             "P4_NEEDS_VERIFICATION", "P5_MONITOR"]
    pivot = pivot.reindex([p for p in order if p in pivot.index])
    colors = {"HIGH": TEAL, "MEDIUM": ACCENT, "LOW": "#475569"}
    fig = go.Figure()
    for conf in [c for c in ["HIGH", "MEDIUM", "LOW"] if c in pivot.columns]:
        fig.add_trace(go.Bar(
            x=pivot.index, y=pivot[conf], name=conf,
            marker_color=colors.get(conf, MUTED),
            hovertemplate="<b>%{x}</b><br>" + conf + ": %{y}<extra></extra>",
        ))
    fig.update_layout(barmode="stack")
    return _style(fig, height=360, title="Intervention priority × data confidence")


def create_district_chart():
    df = fetch_top_districts()
    if df.empty:
        return _empty()
    fig = go.Figure(go.Bar(
        x=df["composite_gap_score"], y=df["district"], orientation="h",
        marker=dict(color=df["composite_gap_score"], colorscale=GAP_SCALE,
                    line=dict(width=0)),
        customdata=df[["state", "gap_characterization", "facility_count"]].values,
        hovertemplate=("<b>%{y}</b>, %{customdata[0]}<br>Gap: %{x:.3f}<br>"
                       "Type: %{customdata[1]}<br>Facilities: %{customdata[2]}<extra></extra>"),
    ))
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    return _style(fig, height=400, title="Top 12 districts by gap severity", legend=False)


def create_trust_chart():
    df = fetch_trust_distribution()
    if df.empty:
        return _empty()
    order = ["High (0.70–1.00)", "Medium (0.50–0.70)",
             "Low (0.30–0.50)", "Very Low (<0.30)"]
    df["trust_tier"] = pd.Categorical(df["trust_tier"], order, ordered=True)
    df = df.sort_values("trust_tier")
    fig = go.Figure(go.Bar(
        x=df["trust_tier"], y=df["count"],
        marker=dict(color=[TEAL, ACCENT, AMBER, ROSE][: len(df)], line=dict(width=0)),
        text=df["count"], textposition="outside", textfont=dict(color=MUTED, size=11),
        hovertemplate="<b>%{x}</b><br>%{y} districts<extra></extra>",
    ))
    return _style(fig, height=360, title="District trust-score distribution", legend=False)


# ============================================================================
# AI AGENT CHAT
# ============================================================================
def chat_with_agent(message, history):
    try:
        messages = []
        for turn in history or []:
            # supports both tuple and OpenAI-style message history
            if isinstance(turn, dict):
                messages.append({"role": turn.get("role", "user"),
                                 "content": turn.get("content", "")})
            else:
                u, a = turn
                if u:
                    messages.append({"role": "user", "content": u})
                if a:
                    messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": message})

        dc = get_deploy_client("databricks")
        resp = dc.predict(endpoint=ENDPOINT_NAME, inputs={"messages": messages})
        if isinstance(resp, dict) and "choices" in resp:
            return resp["choices"][0]["message"]["content"]
        if isinstance(resp, dict) and "messages" in resp:
            return resp["messages"][-1].get("content", str(resp))
        return str(resp)[:1200]
    except Exception as e:  # noqa: BLE001
        return (f"⚠️ The planning agent is unavailable right now ({str(e)[:120]}). "
                "The dashboard tabs still work from the gold tables.")


# ============================================================================
# UI — sleek dark "command center"
# ============================================================================
CSS = f"""
:root {{
  --ink: {INK}; --panel: {PANEL}; --panel2: {PANEL_2};
  --stroke: {STROKE}; --text: {TEXT}; --muted: {MUTED};
  --accent: {ACCENT}; --accent2: {ACCENT_2};
}}
.gradio-container {{
  max-width: 1340px !important; margin: 0 auto !important;
  background: {INK} !important;
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
}}
body, .gradio-container {{ background:
  radial-gradient(1200px 600px at 80% -10%, rgba(56,189,248,0.10), transparent 60%),
  radial-gradient(1000px 500px at -10% 10%, rgba(129,140,248,0.10), transparent 55%),
  {INK} !important; color: {TEXT} !important; }}
footer {{ display: none !important; }}

/* Header */
.cr-header {{ padding: 26px 4px 10px; }}
.cr-title {{ font-size: 30px; font-weight: 800; letter-spacing: -0.02em;
  background: linear-gradient(92deg, {ACCENT}, {ACCENT_2} 60%, {TEAL});
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin: 0; }}
.cr-sub {{ color: {MUTED}; font-size: 14px; margin-top: 4px; }}
.cr-badge {{ display:inline-block; margin-top:10px; padding:4px 12px;
  border:1px solid {STROKE}; border-radius:999px; color:{ACCENT};
  font-size:12px; font-weight:600; background:rgba(56,189,248,0.06); }}

/* KPI cards */
.kpi-row {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(150px,1fr));
  gap:14px; margin:8px 4px 14px; }}
.kpi {{ background: linear-gradient(180deg, {PANEL} 0%, {PANEL_2} 100%);
  border:1px solid {STROKE}; border-radius:18px; padding:18px 18px 16px;
  position:relative; overflow:hidden;
  transition: transform .18s ease, border-color .18s ease; }}
.kpi:hover {{ transform: translateY(-3px); border-color: rgba(56,189,248,0.35); }}
.kpi::after {{ content:''; position:absolute; inset:0 0 auto 0; height:3px;
  background: linear-gradient(90deg, {ACCENT}, {ACCENT_2}); opacity:.85; }}
.kpi .k-label {{ color:{MUTED}; font-size:12px; font-weight:600;
  text-transform:uppercase; letter-spacing:.06em; }}
.kpi .k-value {{ color:{TEXT}; font-size:30px; font-weight:800;
  margin-top:8px; letter-spacing:-0.02em; line-height:1; }}
.kpi .k-note {{ color:{MUTED}; font-size:12px; margin-top:6px; }}
.kpi.alert::after {{ background: linear-gradient(90deg, {AMBER}, {ROSE}); }}
.kpi.alert .k-value {{ color:#ffd9a8; }}
.kpi.good::after {{ background: linear-gradient(90deg, {TEAL}, {ACCENT}); }}

/* Panels around plots */
.panel-card {{ background:{PANEL}; border:1px solid {STROKE};
  border-radius:18px; padding:8px 10px 4px; }}

/* Tabs */
.tab-nav {{ border:none !important; gap:6px !important; }}
.tab-nav button {{ background:transparent !important; color:{MUTED} !important;
  border:1px solid transparent !important; border-radius:12px !important;
  font-weight:600 !important; padding:9px 16px !important; }}
.tab-nav button.selected {{ background:{PANEL} !important; color:{TEXT} !important;
  border:1px solid {STROKE} !important; }}

/* Buttons */
button.primary, .cr-btn {{
  background: linear-gradient(92deg, {ACCENT}, {ACCENT_2}) !important;
  color:#06121f !important; border:none !important; border-radius:12px !important;
  font-weight:700 !important; }}
button.primary:hover {{ filter: brightness(1.08); }}

/* Section labels */
.section-h {{ color:{TEXT}; font-size:16px; font-weight:700; margin:10px 4px 2px; }}
.section-s {{ color:{MUTED}; font-size:13px; margin:0 4px 8px; }}
.legend-chip {{ display:inline-flex; align-items:center; gap:6px; margin-right:14px;
  color:{MUTED}; font-size:12px; }}
.dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
"""

THEME = gr.themes.Base(
    primary_hue="sky", neutral_hue="slate",
    font=[gr.themes.GoogleFont("Inter"), "system-ui", "sans-serif"],
).set(
    body_background_fill=INK, block_background_fill=PANEL,
    block_border_color=STROKE, block_label_text_color=MUTED,
    input_background_fill=PANEL_2, body_text_color=TEXT,
)


def kpi_html(m: dict) -> str:
    def fmt(v):
        return f"{v:,}" if isinstance(v, int) else v
    return f"""
    <div class="kpi-row">
      <div class="kpi alert">
        <div class="k-label">Care-gap regions</div>
        <div class="k-value">{fmt(m.get('gap_regions', 0))}</div>
        <div class="k-note">flagged across {fmt(m.get('districts', 0))} districts</div>
      </div>
      <div class="kpi alert">
        <div class="k-label">Priority gaps (P1–P2)</div>
        <div class="k-value">{fmt(m.get('priority_gaps', 0))}</div>
        <div class="k-note">need urgent intervention</div>
      </div>
      <div class="kpi good">
        <div class="k-label">High-confidence gaps</div>
        <div class="k-value">{fmt(m.get('high_conf_gaps', 0))}</div>
        <div class="k-note">verified, not data-poor</div>
      </div>
      <div class="kpi">
        <div class="k-label">Phantom-facility regions</div>
        <div class="k-value">{fmt(m.get('phantom_regions', 0))}</div>
        <div class="k-note">exist on paper, non-functional</div>
      </div>
      <div class="kpi good">
        <div class="k-label">Avg trust score</div>
        <div class="k-value">{m.get('avg_trust', 0):.2f}</div>
        <div class="k-note">trust-weighted evidence</div>
      </div>
      <div class="kpi">
        <div class="k-label">Facilities analyzed</div>
        <div class="k-value">{fmt(m.get('facilities', 0))}</div>
        <div class="k-note">across the gold layer</div>
      </div>
    </div>"""


with gr.Blocks(css=CSS, theme=THEME, title="CareReach · Healthcare Access Planning") as demo:

    gr.HTML("""
    <div class="cr-header">
      <h1 class="cr-title">CareReach</h1>
      <div class="cr-sub">AI-powered healthcare access planning for India ·
        trust-weighted evidence across 10,000+ facilities</div>
      <span class="cr-badge">DAIS for Good 2026 · Track 2 — AI Agents for Social Good</span>
    </div>
    """)

    kpis = gr.HTML(kpi_html({}))

    with gr.Tabs():
        # ---------------- OVERVIEW (hero geo) ----------------
        with gr.Tab("🗺️  Geospatial Command Center"):
            gr.HTML('<div class="section-h">Where are India\'s real care gaps?</div>'
                    '<div class="section-s">State choropleth shows average gap severity; '
                    'bubbles are district hotspots sized by facility count and colored by gap score.</div>')
            with gr.Group(elem_classes="panel-card"):
                india_map = gr.Plot(show_label=False)
            gr.HTML('<div class="section-h">Demand vs supply</div>'
                    '<div class="section-s">NFHS-5 disease burden against facility supply gaps — '
                    'the top-right quadrant is where intervention matters most.</div>')
            with gr.Group(elem_classes="panel-card"):
                ds_map = gr.Plot(show_label=False)
            refresh_geo = gr.Button("↻ Refresh maps", variant="primary", elem_classes="cr-btn")

        # ---------------- ANALYTICS ----------------
        with gr.Tab("📊  Analytics"):
            with gr.Row():
                with gr.Group(elem_classes="panel-card"):
                    gap_plot = gr.Plot(show_label=False)
                with gr.Group(elem_classes="panel-card"):
                    priority_plot = gr.Plot(show_label=False)
            with gr.Row():
                with gr.Group(elem_classes="panel-card"):
                    district_plot = gr.Plot(show_label=False)
                with gr.Group(elem_classes="panel-card"):
                    trust_plot = gr.Plot(show_label=False)
            refresh_charts = gr.Button("↻ Refresh analytics", variant="primary", elem_classes="cr-btn")

        # ---------------- AI ASSISTANT ----------------
        with gr.Tab("💬  Planning Assistant"):
            gr.HTML('<div class="section-h">Ask CareReach about healthcare gaps</div>'
                    '<div class="section-s">The agent reasons over the gold tables with '
                    'trust-weighted evidence and returns confidence levels with every answer.</div>')
            gr.ChatInterface(
                fn=chat_with_agent,
                examples=[
                    "Which districts have the worst emergency care gaps?",
                    "Show me regions where facilities exist on paper but are non-functional",
                    "Which districts have high child malnutrition AND inadequate healthcare?",
                    "What is the average trust score for facilities in Maharashtra?",
                    "Find facilities with critical data reliability problems",
                ],
            )

    gr.HTML(f"""
    <div style="text-align:center; color:{MUTED}; font-size:12px; padding:22px 0 10px;">
      Built on Databricks Lakehouse · Lakebase continuous sync · Llama 3.3 70B agent —
      for healthcare planners working toward equitable access.
    </div>""")

    # ---- load + refresh wiring ----
    def _load_metrics():
        return kpi_html(fetch_metrics())

    demo.load(_load_metrics, outputs=kpis)
    demo.load(create_india_map, outputs=india_map)
    demo.load(create_demand_supply_map, outputs=ds_map)
    demo.load(create_gap_chart, outputs=gap_plot)
    demo.load(create_priority_chart, outputs=priority_plot)
    demo.load(create_district_chart, outputs=district_plot)
    demo.load(create_trust_chart, outputs=trust_plot)

    refresh_geo.click(create_india_map, outputs=india_map)
    refresh_geo.click(create_demand_supply_map, outputs=ds_map)
    refresh_geo.click(_load_metrics, outputs=kpis)

    refresh_charts.click(create_gap_chart, outputs=gap_plot)
    refresh_charts.click(create_priority_chart, outputs=priority_plot)
    refresh_charts.click(create_district_chart, outputs=district_plot)
    refresh_charts.click(create_trust_chart, outputs=trust_plot)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 8080)))

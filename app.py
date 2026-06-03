"""
Two-Phase Data-Center Cooling — Interactive Engineering App
===========================================================
A multi-tab Streamlit front-end over the validated thermodynamic / control /
economic model in `core/`.

Run:  streamlit run app.py
"""
import time
import io
import base64
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import streamlit as st
from dataclasses import asdict
from html import escape

import core
from core import Assumptions, UI_RANGES, FLUID_CHOICES

st.set_page_config(page_title="ADAMS — Two-Phase Cooling",
                   page_icon="🧊", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------------------------------------------------------- #
#  Unified visual system — light engineering dashboard theme
# --------------------------------------------------------------------------- #
THEME = {
    "bg": "#F6F8FB",
    "panel": "#FFFFFF",
    "panel_2": "#F8FAFC",
    "panel_3": "#EEF2F7",
    "line": "#D8E0EA",
    "text": "#0F172A",
    "muted": "#64748B",
    "muted_2": "#94A3B8",
    "accent": "#0EA5E9",
    "accent_2": "#38BDF8",
    "safe": "#16A34A",
    "warn": "#D97706",
    "danger": "#DC2626",
    "purple": "#7C3AED",
}

# Backward-compatible aliases used by the existing plotting functions.
PALETTE = dict(red=THEME["danger"], blue=THEME["accent"], green=THEME["safe"],
               purple=THEME["purple"], orange=THEME["warn"], grey=THEME["muted"],
               dark=THEME["panel_3"], bg=THEME["bg"], panel=THEME["panel"],
               text=THEME["text"], muted=THEME["muted"])

ICONS = {
    "load": "<svg viewBox='0 0 24 24'><path d='M13 2 3 14h8l-1 8 11-14h-8l0-6Z'/></svg>",
    "fluid": "<svg viewBox='0 0 24 24'><path d='M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11Z'/></svg>",
    "eff": "<svg viewBox='0 0 24 24'><path d='M4 14a8 8 0 1 1 16 0'/><path d='m12 14 4-4'/><path d='M4 20h16'/></svg>",
    "pump": "<svg viewBox='0 0 24 24'><circle cx='12' cy='12' r='7'/><path d='M12 5v14M5 12h14'/></svg>",
    "temp": "<svg viewBox='0 0 24 24'><path d='M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0Z'/></svg>",
    "shield": "<svg viewBox='0 0 24 24'><path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z'/></svg>",
    "water": "<svg viewBox='0 0 24 24'><path d='M3 14c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2'/><path d='M3 19c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2'/></svg>",
    "cash": "<svg viewBox='0 0 24 24'><path d='M12 1v22'/><path d='M17 5H9.5a3.5 3.5 0 0 0 0 7H14a3.5 3.5 0 0 1 0 7H6'/></svg>",
    "compare": "<svg viewBox='0 0 24 24'><path d='M7 3v18'/><path d='M17 3v18'/><path d='M3 7h8'/><path d='M13 17h8'/></svg>",
    "report": "<svg viewBox='0 0 24 24'><path d='M6 2h9l5 5v15H6Z'/><path d='M14 2v6h6'/><path d='M9 13h6M9 17h8'/></svg>",
}


def svg_icon(name: str) -> str:
    raw = ICONS.get(name, ICONS["eff"])
    return raw.replace("<svg ", "<svg class='kpi-icon' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' ")




# Streamlit 1.50+ can raise StreamlitDuplicateElementId when the same Plotly
# figure is rendered in more than one journey tab (for example process flow in
# Command Center and Report Mode). Route every chart through one helper that
# assigns a unique, stable-per-run key.
_PLOTLY_COUNTER = 0

def safe_plotly_chart(fig, *args, key=None, **kwargs):
    global _PLOTLY_COUNTER
    if key is None:
        _PLOTLY_COUNTER += 1
        key = f"plotly_chart_{_PLOTLY_COUNTER}"
    return st.plotly_chart(fig, *args, key=key, **kwargs)


def apply_theme():
    """Single CSS block for the full app. Keep visual language in one place."""
    css = f"""
<style>
:root {{
  --bg:{THEME['bg']}; --panel:{THEME['panel']}; --panel2:{THEME['panel_2']};
  --panel3:{THEME['panel_3']}; --line:{THEME['line']}; --text:{THEME['text']};
  --muted:{THEME['muted']}; --muted2:{THEME['muted_2']}; --accent:{THEME['accent']};
  --accent2:{THEME['accent_2']}; --safe:{THEME['safe']}; --warn:{THEME['warn']};
  --danger:{THEME['danger']}; --purple:{THEME['purple']};
  --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --mono: "SFMono-Regular", "Roboto Mono", "Cascadia Code", "Liberation Mono", Menlo, monospace;
}}
.stApp {{
  background:
    radial-gradient(circle at 12% 0%, rgba(14,165,233,0.13), transparent 34rem),
    radial-gradient(circle at 88% 8%, rgba(124,58,237,0.08), transparent 30rem),
    linear-gradient(180deg, #F8FAFC 0%, #F1F5F9 48%, #F8FAFC 100%);
  color: var(--text); font-family: var(--sans);
}}
.block-container {{padding-top: 1.1rem; padding-bottom: 3rem; max-width: 1500px;}}
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(255,255,255,.98), rgba(248,250,252,.98));
  border-right: 1px solid var(--line);
}}
[data-testid="stSidebar"] * {{color: var(--text);}}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {{color: var(--muted);}}
h1, h2, h3, h4, h5 {{color: var(--text); letter-spacing: -0.02em;}}
p, li, div, span {{font-family: var(--sans);}}
hr {{border-color: var(--line);}}
.small-note, .muted {{font-size:.84rem; color:var(--muted);}}
.mono {{font-family: var(--mono); font-variant-numeric: tabular-nums;}}
[data-testid="stTabs"] button {{
  color: var(--muted); background: transparent; border-radius: 999px; padding:.72rem 1.08rem;
  font-size:1.02rem; font-weight:800;
}}
[data-testid="stTabs"] button p {{font-size:1.02rem; font-weight:800;}}
[data-testid="stTabs"] button[aria-selected="true"] {{
  color: var(--accent); background: rgba(14,165,233,.09); border: 1px solid rgba(14,165,233,.28);
}}
[data-testid="stRadio"] > div {{gap:.75rem; flex-wrap:wrap;}}
[data-testid="stRadio"] label {{
  background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:999px;
  padding:.70rem 1.0rem; box-shadow:0 8px 18px rgba(15,23,42,.05);
}}
[data-testid="stRadio"] label p, [data-testid="stRadio"] label span {{
  font-size:1.02rem; font-weight:750; color:var(--text);
}}
.stButton>button, .stDownloadButton>button {{
  background: linear-gradient(135deg, rgba(14,165,233,.96), rgba(2,132,199,.90));
  color: #FFFFFF; border: 0; border-radius: 12px; font-weight: 800;
  box-shadow: 0 10px 24px rgba(14,165,233,.20);
}}
.stButton>button:hover, .stDownloadButton>button:hover {{border:0; filter: brightness(1.04); color:#FFFFFF;}}
[data-testid="stMetric"] {{
  background: rgba(255,255,255,.90); border: 1px solid var(--line); border-radius: 16px; padding: 1rem;
  box-shadow: 0 12px 28px rgba(15,23,42,.06);
}}
[data-testid="stMetricLabel"] {{color:var(--muted);}}
[data-testid="stMetricValue"] {{font-family: var(--mono); font-size:1.55rem; color:var(--text);}}
.stDataFrame, [data-testid="stTable"] {{border:1px solid var(--line); border-radius:16px; overflow:hidden;}}
.kicker {{color: var(--accent); font-size:.78rem; font-weight:800; letter-spacing:.16em; text-transform:uppercase;}}
.app-title {{
  display:flex; align-items:center; gap:14px; padding: 1.1rem 1.2rem 1rem;
  background: linear-gradient(135deg, rgba(255,255,255,.96), rgba(248,250,252,.88));
  border: 1px solid var(--line); border-radius: 22px; margin-bottom: 1rem;
  box-shadow: 0 18px 50px rgba(15,23,42,.08);
}}
.app-title h1 {{font-size:2.15rem; margin:0;}}
.app-title p {{margin:.15rem 0 0; color:var(--muted);}}
.logo-mark {{width:46px; height:46px; border-radius:14px; display:grid; place-items:center;
  color:#FFFFFF; background:linear-gradient(135deg, var(--accent), var(--accent2));}}
.kpi-card {{
  background: rgba(255,255,255,.94); border: 1px solid var(--line); border-radius: 18px; padding: 1rem 1.1rem;
  min-height: 126px; box-shadow: 0 14px 32px rgba(15,23,42,.07);
}}
.kpi-head {{display:flex; justify-content:space-between; align-items:center; gap:.6rem; color:var(--muted); font-size:.78rem; text-transform:uppercase; letter-spacing:.08em;}}
.kpi-icon {{width:22px; height:22px; color: var(--accent); flex: 0 0 22px;}}
.kpi-value {{font-family:var(--mono); font-variant-numeric:tabular-nums; font-size:2.0rem; font-weight:850; line-height:1.1; color:var(--text); margin-top:.5rem;}}
.kpi-unit {{font-family:var(--sans); font-size:.95rem; color:var(--muted); font-weight:650; margin-left:.2rem;}}
.kpi-sub {{color:var(--muted); font-size:.86rem; margin-top:.55rem;}}
.kpi-card.safe .kpi-icon, .kpi-card.safe .kpi-value {{color:var(--safe);}}
.kpi-card.warn .kpi-icon, .kpi-card.warn .kpi-value {{color:var(--warn);}}
.kpi-card.danger .kpi-icon, .kpi-card.danger .kpi-value {{color:var(--danger);}}
.status-pill {{display:inline-flex; align-items:center; gap:.45rem; padding:.35rem .7rem; border-radius:999px; font-size:.78rem; font-weight:800; letter-spacing:.04em; text-transform:uppercase;}}
.status-pill.safe {{color:var(--safe); background:rgba(22,163,74,.10); border:1px solid rgba(22,163,74,.30);}}
.status-pill.warn {{color:var(--warn); background:rgba(217,119,6,.10); border:1px solid rgba(217,119,6,.32);}}
.status-pill.danger {{color:var(--danger); background:rgba(220,38,38,.10); border:1px solid rgba(220,38,38,.32);}}
.section-card {{background: rgba(255,255,255,.92); border:1px solid var(--line); border-radius:20px; padding:1.05rem 1.15rem; margin:.5rem 0 1rem; box-shadow:0 12px 28px rgba(15,23,42,.06);}}
.journey-card {{background:rgba(255,255,255,.94); border:1px solid var(--line); border-radius:18px; padding:1rem 1.1rem; height:100%; box-shadow:0 10px 24px rgba(15,23,42,.05);}}
.journey-card b {{color:var(--text);}}
.report-sheet {{background:#FFFFFF; color:#0F172A; border-radius:18px; padding:1.35rem; border:1px solid #CBD5E1; box-shadow:0 16px 42px rgba(15,23,42,.08);}}
.report-sheet * {{color:#0F172A;}}
.report-sheet .muted-report {{color:#64748B;}}
.report-grid {{display:grid; grid-template-columns:repeat(4,1fr); gap:.75rem;}}
.report-metric {{border:1px solid #CBD5E1; border-radius:12px; padding:.75rem; background:white;}}
.report-metric .value {{font-family:var(--mono); font-size:1.45rem; font-weight:850;}}
.report-metric .label {{font-size:.72rem; color:#64748B; text-transform:uppercase; letter-spacing:.08em;}}
.report-image-grid {{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:.75rem; margin-top:1rem;}}
.report-image-grid img {{width:100%; border-radius:12px; border:1px solid #CBD5E1; background:white;}}
@media print {{.stApp {{background:white;}} .report-sheet {{box-shadow:none; border:0;}}}}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)


def build_plotly_template():
    tpl = go.layout.Template()
    tpl.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=THEME["panel_2"],
        font=dict(family="Inter, Segoe UI, sans-serif", color=THEME["text"]),
        colorway=[THEME["accent"], THEME["safe"], THEME["warn"], THEME["danger"], THEME["purple"], THEME["muted"]],
        xaxis=dict(gridcolor=THEME["line"], zerolinecolor=THEME["line"], linecolor=THEME["line"], tickcolor=THEME["muted"], title_font=dict(color=THEME["muted"])),
        yaxis=dict(gridcolor=THEME["line"], zerolinecolor=THEME["line"], linecolor=THEME["line"], tickcolor=THEME["muted"], title_font=dict(color=THEME["muted"])),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=THEME["line"]),
        margin=dict(l=42, r=26, t=56, b=36),
    )
    pio.templates["adams_light"] = tpl
    pio.templates.default = "adams_light"


build_plotly_template()
apply_theme()


def severity(value, safe_max=None, warn_max=None, invert=False):
    """Return safe/warn/danger class. Set invert=True when higher is better."""
    if invert:
        if value >= safe_max:
            return "safe"
        if value >= warn_max:
            return "warn"
        return "danger"
    if value <= safe_max:
        return "safe"
    if value <= warn_max:
        return "warn"
    return "danger"


def status_pill(label, cls="safe"):
    return f"<span class='status-pill {cls}'>● {escape(str(label))}</span>"


def kpi_card(col, label, value, unit="", sub="", icon="eff", cls="", help_text=""):
    title = f" title='{escape(help_text)}'" if help_text else ""
    col.markdown(
        f"<div class='kpi-card {cls}'{title}>"
        f"<div class='kpi-head'><span>{escape(label)}</span>{svg_icon(icon)}</div>"
        f"<div class='kpi-value'>{escape(str(value))}<span class='kpi-unit'>{escape(unit)}</span></div>"
        f"<div class='kpi-sub'>{sub}</div></div>", unsafe_allow_html=True)


def section_intro(kicker, title, body=""):
    # Headline-only section intro. Explanatory subtitles were intentionally removed
    # to keep the interface compact and less text-heavy.
    st.markdown(f"<div class='section-card'><div class='kicker'>{escape(kicker)}</div>"
                f"<h2 style='margin:.25rem 0 0'>{escape(title)}</h2></div>",
                unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
#  Sidebar — assumptions (single source of truth)
# --------------------------------------------------------------------------- #
def sidebar_assumptions() -> Assumptions:
    st.sidebar.title("Design Inputs")
    st.sidebar.caption("Drives every tab.")

    presets = {
        "Base case (80 kW)": {},
        "High density (130 kW)": {"Q_rack_kW": 130.0, "n_chips": 16},
        "Conservative (60 kW)": {"Q_rack_kW": 60.0, "T_chip_target_C": 65.0},
        "Hot climate (warm water)": {"Tw_in_free_C": 35.0, "T_cond_C": 62.0,
                                     "Tw_out_target_C": 52.0},
    }
    pname = st.sidebar.selectbox("Preset", list(presets.keys()))
    base = Assumptions().copy(**presets[pname])

    fluid = st.sidebar.selectbox("Refrigerant", FLUID_CHOICES,
                                 index=FLUID_CHOICES.index(base.fluid))
    vals = {"fluid": fluid}

    groups = {
        "IT load": ["Q_rack_kW", "n_chips"],
        "Temperatures": ["T_chip_target_C", "T_chip_trip_C", "T_evap_C",
                         "T_cond_C", "superheat_K", "subcool_K"],
        "Water loop": ["Tw_in_free_C", "Tw_out_target_C"],
        "Equipment": ["eta_pump", "UA_cond_W_K", "dP_coldplate_kPa", "dP_pipe_kPa"],
        "Inventory": ["V_reservoir_L", "charge_total_kg"],
        "Facility overheads": ["fan_frac_of_reject", "ups_loss_frac",
                               "misc_facility_frac"],
        "Dynamic sim": ["dt_s", "t_end_s"],
    }
    for gname, keys in groups.items():
        with st.sidebar.expander(gname, expanded=(gname == "IT load")):
            for k in keys:
                label, lo, hi, step = UI_RANGES[k]
                hlp = core.UI_HELP.get(k)
                cur = getattr(base, k)
                if k == "n_chips":
                    vals[k] = st.slider(label, int(lo), int(hi), int(cur),
                                        int(step), help=hlp)
                elif k == "Tw_out_target_C":
                    supply = vals.get("Tw_in_free_C", base.Tw_in_free_C)
                    lo2 = max(float(lo), float(supply) + 2.0)
                    cur2 = max(float(cur), lo2)
                    vals[k] = st.slider(label, lo2, float(hi), cur2, float(step),
                                        help=hlp)
                else:
                    vals[k] = st.slider(label, float(lo), float(hi),
                                        float(cur), float(step), help=hlp)
    return base.copy(**vals)


# --------------------------------------------------------------------------- #
#  Caching wrappers
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def cached_steady(adict):
    A = Assumptions(**adict)
    return core.steady_state(A)


@st.cache_data(show_spinner=False)
def cached_refrig(adict):
    A = Assumptions(**adict)
    return core.refrigerant_comparison(A)


@st.cache_data(show_spinner=False)
def cached_sizing(adict):
    A = Assumptions(**adict)
    return core.sizing(A)


def adict_of(A):
    from dataclasses import asdict
    return asdict(A)


# --------------------------------------------------------------------------- #
#  TAB 1 — Overview
# --------------------------------------------------------------------------- #
def tab_overview(A, ss):
    # styled hero cards
    st.markdown("""
    <style>
    .hero-card {background:linear-gradient(135deg,#1a3a5c 0%,#2a6098 100%);
        border-radius:14px; padding:18px 20px; color:#fff; height:100%;}
    .hero-card.green {background:linear-gradient(135deg,#1f6e44 0%,#2e8b57 100%);}
    .hero-card.red {background:linear-gradient(135deg,#9c3434 0%,#d94545 100%);}
    .hero-card.purple {background:linear-gradient(135deg,#5b3f7a 0%,#9b6fb5 100%);}
    .hero-lab {font-size:0.78rem; opacity:0.85; text-transform:uppercase;
        letter-spacing:0.06em;}
    .hero-val {font-size:1.9rem; font-weight:700; line-height:1.15;}
    .hero-sub {font-size:0.8rem; opacity:0.8;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("### System at a glance")
    st.write("Pumped two-phase, direct-to-chip cooling: refrigerant boils in a "
             "microchannel cold plate, rejects heat in a condenser to a water "
             "loop, and is pumped back. Adjust inputs in the sidebar.")

    def hero(col, label, val, sub="", cls=""):
        col.markdown(
            f"<div class='hero-card {cls}'><div class='hero-lab'>{label}</div>"
            f"<div class='hero-val'>{val}</div>"
            f"<div class='hero-sub'>{sub}</div></div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    hero(c1, "IT load", f"{A.Q_rack_kW:.0f} kW",
         f"{A.Q_rack_kW/A.n_chips:.1f} kW/chip · {A.n_chips} chips")
    hero(c2, "Refrigerant", A.fluid,
         f"{ss['Pevap_bar']:.1f}/{ss['Pcond_bar']:.1f} bar evap/cond", "purple")
    hero(c3, "Full-facility PUE", f"{ss['PUE_full']:.3f}",
         f"loop-only {ss['pPUE_loop']:.3f}", "green")
    hero(c4, "Pump power", f"{ss['Wpump_W']/1000:.2f} kW",
         f"{ss['Vdot_Lmin']:.0f} L/min flow", "red")

    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.markdown("##### Process flow diagram")
        safe_plotly_chart(process_flow_figure(A, ss), use_container_width=True)
    with right:
        st.markdown("##### Cooling efficiency")
        safe_plotly_chart(pue_gauge(ss), use_container_width=True)


def pue_gauge(ss):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=ss["PUE_full"],
        number=dict(valueformat=".3f", font=dict(size=40, color=THEME["text"])),
        delta=dict(reference=1.0, increasing=dict(color=THEME["danger"]),
                   valueformat=".3f"),
        title=dict(text="Full-facility PUE (1.0 = ideal)", font=dict(size=13)),
        gauge=dict(axis=dict(range=[1.0, 1.7]),
                   bar=dict(color=THEME["safe"]),
                   bgcolor=THEME["panel"], bordercolor=THEME["line"],
                   steps=[dict(range=[1.0, 1.15], color="rgba(34,197,94,.16)"),
                          dict(range=[1.15, 1.35], color="rgba(245,158,11,.18)"),
                          dict(range=[1.35, 1.7], color="rgba(239,68,68,.18)")],
                   threshold=dict(line=dict(color=THEME["accent"], width=3),
                                  value=ss["PUE_full"]))))
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20), template="adams_light")
    return fig



def process_flow_figure(A, ss):
    """Annotated process-flow schematic built with Plotly shapes."""
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 13])
    fig.update_yaxes(visible=False, range=[0, 8])

    def box(x, y, w, h, text, color):
        fig.add_shape(type="rect", x0=x, y0=y, x1=x + w, y1=y + h,
                      line=dict(color=THEME["line"], width=1.8), fillcolor=color,
                      opacity=0.96)
        fig.add_annotation(x=x + w / 2, y=y + h / 2, text=text, showarrow=False,
                           font=dict(size=16, color=THEME["text"]))

    def arrow(x1, y1, x2, y2, color, label=None):
        fig.add_annotation(x=x2, y=y2, ax=x1, ay=y1, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=1.6, arrowwidth=3.0, arrowcolor=color)
        if label:
            fig.add_annotation(x=(x1 + x2) / 2, y=(y1 + y2) / 2 + 0.28,
                               text=label, showarrow=False,
                               font=dict(size=13, color=THEME["text"]),
                               bgcolor="rgba(255,255,255,0.94)", bordercolor=THEME["line"])

    box(0.4, 3.0, 2.0, 3.0, "Server Rack<br>+ Cold Plate", THEME["panel_3"])
    box(5.2, 5.0, 2.6, 1.7, "Condenser /<br>Heat Exchanger", "#FEE2E2")
    box(9.6, 4.8, 3.0, 1.9, "External Water<br>/ Heat Reuse", "#E0F2FE")
    box(9.9, 2.0, 2.0, 1.4, "Liquid<br>Reservoir", "#E0F2FE")
    box(5.9, 1.1, 1.3, 1.0, "Pump", "#DCFCE7")

    arrow(2.4, 5.4, 5.2, 5.8, PALETTE["red"],
          f"Vapor {ss['mdot']:.2f} kg/s<br>{A.T_evap_C:.0f}°C · "
          f"{ss['Pevap_bar']:.1f} bar")
    arrow(6.5, 5.0, 10.6, 3.4, PALETTE["blue"],
          f"Liquid {A.T_cond_C:.0f}°C · {ss['Pcond_bar']:.1f} bar")
    arrow(9.9, 2.5, 7.2, 1.7, PALETTE["blue"], "Liquid in")
    arrow(5.9, 1.6, 1.4, 1.6, PALETTE["blue"], f"{ss['Vdot_Lmin']:.0f} L/min")
    arrow(1.4, 1.6, 1.4, 3.0, PALETTE["blue"], None)
    arrow(1.4, 7.0, 1.4, 6.1, PALETTE["red"], f"IT {A.Q_rack_kW:.0f} kW")
    arrow(7.8, 6.1, 9.6, 6.1, PALETTE["red"], "warm water")
    arrow(9.6, 5.2, 7.8, 5.2, PALETTE["blue"],
          f"{ss['Vdot_w_Lmin']:.0f} L/min {ss['Tw_in']:.0f}→{ss['Tw_out']:.0f}°C")

    fig.add_annotation(x=6.55, y=0.5, text=f"Pump {ss['Wpump_W']/1000:.2f} kW",
                       showarrow=False, font=dict(size=13, color=THEME["warn"]))
    info = (f"Evap {A.T_evap_C:.0f}°C/{ss['Pevap_bar']:.1f} bar · "
            f"Cond {A.T_cond_C:.0f}°C/{ss['Pcond_bar']:.1f} bar · "
            f"Cond duty {ss['Qcond_kW']:.0f} kW · PUE-full {ss['PUE_full']:.3f}")
    fig.update_layout(title=dict(text=f"Process Flow — {A.fluid}, "
                                 f"{A.Q_rack_kW:.0f} kW rack",
                                 font=dict(size=18)),
                      height=480, margin=dict(l=10, r=10, t=46, b=10), template="adams_light",
                      annotations=list(fig.layout.annotations) + [dict(
                          x=6.5, y=7.6, text=info, showarrow=False,
                          font=dict(size=14, color=THEME["accent"]))])
    return fig


# --------------------------------------------------------------------------- #
#  TAB 2 — Steady state
# --------------------------------------------------------------------------- #
def tab_steady(A, ss):
    st.header("Steady-State Performance")
    sub = st.radio("steady_nav", ["⚡ Energy & PUE", "🌡️ Thermal & chip"],
                   horizontal=True, label_visibility="collapsed")

    if sub.startswith("⚡"):
        _steady_energy(A, ss)
    else:
        _steady_thermal(A, ss)


def _steady_energy(A, ss):
    # power breakdown
    par = {"Refrig pump": ss["Wpump_W"], "Water pump": ss["W_waterpump_W"],
           "Chiller": ss["W_chiller_W"], "Reject fans": ss["W_fans_W"],
           "UPS+distrib": ss["W_ups_W"], "Misc facility": ss["W_misc_W"]}
    colL, colR = st.columns(2)
    with colL:
        fig = go.Figure(go.Bar(x=list(par.keys()),
                               y=[v / 1000 for v in par.values()],
                               marker_color=[PALETTE["red"], PALETTE["blue"],
                                             PALETTE["purple"], PALETTE["orange"],
                                             PALETTE["grey"], "#cfd4da"]))
        fig.update_layout(title="Parasitic power breakdown (IT excluded)",
                          yaxis_title="kW", height=360,
                          margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)
    with colR:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=["Loop-only", "Full facility"],
                             y=[ss["pPUE_loop"], ss["PUE_full"]],
                             marker_color=[PALETTE["green"], PALETTE["red"]],
                             text=[f"{ss['pPUE_loop']:.3f}", f"{ss['PUE_full']:.3f}"],
                             textposition="outside"))
        fig.add_hline(y=1.0, line_dash="dash", line_color="green")
        fig.update_layout(title="Partial vs full-facility PUE",
                          yaxis_title="PUE", yaxis_range=[1.0, ss["PUE_full"] + 0.05],
                          height=360, margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)

    st.info("**Why two PUEs?** The loop-only number (~1.04) counts just the "
            "cooling-loop parasitics. The honest facility number (~1.15) adds "
            "UPS/distribution (~8% of IT) and misc load (~3%). 1.04 is "
            "'almost no cooling overhead', *not* 'almost perfect facility'.")

    with st.expander("How does the water-loop temperature affect PUE?"):
        st.markdown(
            "- **Warmer water supply → lower PUE (better), up to a point.** "
            "Warmer supply water can be made by an outdoor dry cooler for more "
            "of the year, so the chiller stays off → less parasitic power. But "
            "if the supply gets too warm for the condenser to reject heat at "
            "the chosen condensing temperature, the **chiller switches on and "
            "PUE jumps up sharply** — a chiller is the most power-hungry part of "
            "the loop.\n"
            "- **Higher water return target → slightly lower PUE.** A wider "
            "supply→return ΔT carries the same heat with less water flow, so the "
            "water pump draws less power. Smaller effect than the chiller, but "
            "real — and a high return is also what makes the heat *reusable*.\n"
            "- **Bottom line:** push the water as warm as the condenser can "
            "tolerate without forcing the chiller; that minimises PUE and "
            "maximises free-cooling hours and heat-reuse value.")

    st.subheader("Mode comparison")
    rows = []
    for mode in ["free", "hot", "reuse"]:
        r = core.steady_state(A, mode=mode)
        rows.append({"Mode": mode, "pPUE_loop": r["pPUE_loop"],
                     "PUE_full": r["PUE_full"], "Chiller kW": r["Qchiller_kW"],
                     "Reuse kW": r["Q_reuse_kW"], "Water L/min": r["Vdot_w_Lmin"]})
    st.dataframe(pd.DataFrame(rows).round(3), use_container_width=True,
                 hide_index=True)

    st.subheader("Condenser behavior")
    mws = np.linspace(0.4, 2.5, 40)
    fig = go.Figure()
    for Twin in [25, 30, 35]:
        Tc = [core.condenser_solve(ss["Qcond_kW"] * 1e3, A.UA_cond_W_K, m, Twin)["Tcond_C"]
              for m in mws]
        fig.add_trace(go.Scatter(x=mws, y=Tc, mode="lines",
                                 name=f"Tw_in={Twin}°C"))
    fig.add_hline(y=A.T_cond_C, line_dash="dash", line_color="black",
                  annotation_text="design Tcond")
    fig.update_layout(title="Condensing temperature vs water flow",
                      xaxis_title="water flow [kg/s]", yaxis_title="Tcond [°C]",
                      height=360, margin=dict(t=40, b=10))
    safe_plotly_chart(fig, use_container_width=True)


def _steady_thermal(A, ss):
    # operating point pressures (saturation pressures at evap/cond temps)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evap temp", f"{A.T_evap_C:.0f} °C")
    c2.metric("Evap pressure", f"{ss['Pevap_bar']:.2f} bar",
              help="Saturation pressure of the fluid at the evaporation temp")
    c3.metric("Cond temp", f"{A.T_cond_C:.0f} °C")
    c4.metric("Cond pressure", f"{ss['Pcond_bar']:.2f} bar",
              help="Saturation pressure at the condensing temp")
    st.caption("Evap/cond temperature and pressure are tied by the "
               "refrigerant's saturation curve — change a temperature and its "
               "pressure moves with it.")

    # chip-target consistency: evap temp + cold-plate ΔT -> chip temp
    ev = core.sat_props(A.fluid, A.T_evap_C, 0.5)
    if ev.get("ok"):
        cp = core.ColdPlate()
        rcp = core.coldplate_solve(cp, A.Q_rack_kW * 1e3 / A.n_chips,
                                   ss["mdot"] / A.n_chips, ev, A)
        chip = rcp["Tchip_C"]
        st.subheader("Chip temperature vs target")
        c1, c2, c3 = st.columns(3)
        c1.metric("Chip temp (from design)", f"{chip:.1f} °C")
        c2.metric("Chip target", f"{A.T_chip_target_C:.0f} °C")
        margin = A.T_chip_target_C - chip
        c3.metric("Margin to target", f"{margin:+.1f} °C")
        if chip > A.T_chip_trip_C:
            st.error(f"Design chip temp {chip:.1f} °C exceeds the trip limit "
                     f"{A.T_chip_trip_C:.0f} °C — lower the evaporation "
                     f"temperature or improve the cold plate.")
        elif chip > A.T_chip_target_C:
            st.warning(f"Design chip temp {chip:.1f} °C is above your target "
                       f"{A.T_chip_target_C:.0f} °C. To hit the target, lower "
                       f"the **evaporation temperature** (chip ≈ evaporation "
                       f"temp + cold-plate ΔT) — note this raises flow/pressure "
                       f"and can reduce free-cooling headroom, which is how the "
                       f"chip target indirectly affects PUE.")
        else:
            st.success(f"Design meets the chip target with {margin:.1f} °C to "
                       f"spare.")
        st.caption("Uses the default cold-plate geometry; the Cold Plate tab "
                   "lets you vary it and see the exact chip temperature.")

    st.subheader("All steady-state outputs")
    show = {k: round(v, 4) if isinstance(v, float) else v
            for k, v in ss.items() if k not in ("ok", "note")}
    st.dataframe(pd.DataFrame([show]).T.rename(columns={0: "value"}),
                 use_container_width=True)


# --------------------------------------------------------------------------- #
#  TAB 3 — Cold plate
# --------------------------------------------------------------------------- #
def tab_coldplate(A, ss):
    st.header("Microchannel Cold Plate")
    st.write("The component that sits directly on the chip and carries heat "
             "into the boiling refrigerant.")

    with st.expander("What it is & how the model works", expanded=False):
        st.markdown(
            "**What it is.** A copper block on top of the chip with hundreds of "
            "sub-millimeter parallel channels — that's what *microchannel* "
            "means. The huge wetted area and short thermal path let it remove "
            "very high heat flux. The refrigerant **boils** inside the "
            "channels, absorbing large **latent heat** at near-constant "
            "temperature, so a small flow holds a uniform, low chip "
            "temperature — the core advantage over single-phase water cooling. "
            "The **oblique airfoil-shaped fins** repeatedly restart the "
            "boundary layer and induce secondary cross-flow, keeping the "
            "heat-transfer coefficient high along the whole plate with only a "
            "modest pressure-drop penalty.\n\n"
            "**Methodology (what the sliders feed).**\n"
            "- **Chip temperature** = evaporation temp + heat × (wall/TIM "
            "resistance + 1/(HTC × area × fin factor)). More channels or higher "
            "HTC → lower resistance → cooler chip.\n"
            "- **Exit vapor quality** = heat ÷ (flow × latent heat): the "
            "fraction of refrigerant boiled off. Kept well below 1.0 to avoid "
            "dry-out.\n"
            "- **Pressure drop** = single-phase Darcy friction × a two-phase "
            "multiplier that grows with quality.\n"
            "- **CHF margin** = critical-heat-flux correlation ÷ applied flux: "
            "how far the surface is from drying out (>2× is healthy).\n\n"
            "These are screening correlations calibrated for realistic chip "
            "temperatures — not a CFD model or a specific vendor's plate.")

    c1, c2, c3 = st.columns(3)
    n_ch = c1.slider("Channels", 200, 2000, 1000, 50)
    d_h = c2.slider("Channel hydraulic dia [mm]", 0.2, 1.5, 0.5, 0.05)
    h_nom = c3.slider("Nominal HTC [W/m²K]", 8000, 40000, 25000, 1000)

    cp = core.ColdPlate(n_ch=n_ch, d_h_mm=d_h, h_tp_nom=float(h_nom))
    ev = core.sat_props(A.fluid, A.T_evap_C, 0.5)
    Qchip = A.Q_rack_kW * 1e3 / A.n_chips
    r = core.coldplate_solve(cp, Qchip, ss["mdot"] / A.n_chips, ev, A)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chip temp", f"{r['Tchip_C']:.1f} °C",
              delta=f"{r['Tchip_C']-A.T_chip_target_C:+.1f} vs target")
    c2.metric("Exit vapor quality", f"{r['x_out']:.2f}")
    c3.metric("Pressure drop", f"{r['dP_kPa']:.1f} kPa")
    c4.metric("CHF margin", f"{r['CHF_margin']:.1f}×",
              help="Margin to dry-out (critical heat flux). >2 is healthy.")

    # sweep mass flux
    mdots = np.linspace(0.3 * ss["mdot"], 1.6 * ss["mdot"], 40)
    Tchips, qual, chf = [], [], []
    for md in mdots:
        rr = core.coldplate_solve(cp, Qchip, md / A.n_chips, ev, A)
        Tchips.append(rr["Tchip_C"]); qual.append(rr["x_out"])
        chf.append(rr["CHF_margin"])
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Scatter(x=mdots, y=Tchips, name="Chip temp [°C]",
                             line=dict(color=PALETTE["red"])), secondary_y=False)
    fig.add_trace(go.Scatter(x=mdots, y=chf, name="CHF margin [×]",
                             line=dict(color=PALETTE["green"])), secondary_y=True)
    fig.add_hline(y=A.T_chip_trip_C, line_dash="dot", line_color="red")
    fig.add_vline(x=ss["mdot"], line_dash="dash", line_color="grey",
                  annotation_text="design flow")
    fig.update_xaxes(title_text="refrigerant mass flow [kg/s]")
    fig.update_yaxes(title_text="chip temp [°C]", secondary_y=False)
    fig.update_yaxes(title_text="CHF margin [×]", secondary_y=True)
    fig.update_layout(title="Sensitivity to mass flow", height=420,
                      margin=dict(t=40, b=10))
    safe_plotly_chart(fig, use_container_width=True)
    st.caption("Lower flow → higher chip temp and lower dry-out margin. The "
               "design flow keeps the chip cool with a large CHF margin.")


# --------------------------------------------------------------------------- #
#  TAB 4 — Dynamic simulation (interactive)
# --------------------------------------------------------------------------- #
def tab_dynamic(A):
    st.header("Dynamic Simulation")
    st.write("Closed-loop simulator (lumped plant + PLC + supervisor). Pick a "
             "preset or build a custom case, then read the response.")

    mode = st.radio("Scenario source", ["Preset", "Custom builder"],
                    horizontal=True)

    if mode == "Preset":
        scns = core.canonical_scenarios()
        names = st.multiselect("Scenarios to run", list(scns.keys()),
                               default=[list(scns.keys())[0]])
        chosen = {n: scns[n] for n in names}
    else:
        chosen = custom_scenario_builder()

    if not chosen:
        st.warning("Select or build at least one scenario.")
        return

    if st.button("▶ Run simulation", type="primary"):
        results = {}
        prog = st.progress(0.0, text="Simulating…")
        total = len(chosen)
        for i, (name, scn) in enumerate(chosen.items()):
            df = core.simulate_scn(A, scn,
                                   progress=lambda f, i=i: prog.progress(
                                       (i + f) / total,
                                       text=f"Simulating {name}…"))
            results[name] = df
        prog.empty()
        st.session_state["dyn_results"] = results

    results = st.session_state.get("dyn_results", {})
    if not results:
        st.info("Configure a scenario and press **Run simulation**.")
        return

    # outcome summary
    rows = []
    for name, df in results.items():
        o = core.scenario_outcome(df)
        rows.append({"Scenario": name, "End state": o["end_state"],
                     "Peak chip °C": round(o["peak_Tchip"], 1),
                     "Min level %": round(o["min_level"], 1),
                     "Trips": o["total_trips"], "Alarms": o["total_alarms"]})
    st.subheader("Outcome summary")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for name, df in results.items():
        st.subheader(name)
        safe_plotly_chart(dynamic_figure(A, df), use_container_width=True)
        advice = remediation_advice(name, df)
        if advice:
            with st.expander("⚠️ What went wrong & how to fix it", expanded=True):
                st.markdown(advice)

    with st.expander("How to read these plots"):
        st.markdown(
            "- **Temperatures**: chip should stay below the red trip line.\n"
            "- **Actuator commands**: shows the controller working (pump speed, "
            "valves, chiller) — violent oscillation would signal bad tuning.\n"
            "- **Inventory / flow / quality**: reservoir level stays above the "
            "low-level trip; vapor quality stays below 1.0 (no dry-out).\n"
            "- **PLC state / alarms / trips**: the state-machine path and any "
            "trips. Normal cases end in a NORMAL state with zero trips; fault "
            "cases should TRIP safely.")


def remediation_advice(name, df):
    """Return markdown advice if a scenario tripped or misbehaved, else ''."""
    o = core.scenario_outcome(df)
    trips = set(t for s in df.trips for t in s.split(";") if t)
    msgs = []
    if "pump_fault" in trips or "pumpfail" in name.lower():
        msgs.append(
            "**Pump failure detected → system tripped (correct, safe response).**\n\n"
            "The plant cannot move heat with a dead pump, so the PLC trips to "
            "protect the chips. To keep *running through* a pump failure rather "
            "than tripping, design in:\n"
            "- **N+1 (or 2N) redundant pumps** on a common header with automatic "
            "changeover — a standby pump starts on low-flow/low-ΔP detection.\n"
            "- **VFDs with auto-restart** and a fast (<1 s) flow-loss interlock "
            "that commands the standby before chip temperature rises.\n"
            "- **A thermal-inertia buffer** (larger reservoir / accumulator) to "
            "ride out the changeover transient.\n"
            "- Periodic **alternation** of duty/standby pumps so both stay "
            "healthy.")
    if "LoLevel" in trips or "lowlevel" in name.lower():
        msgs.append(
            "**Low reservoir level → system tripped.**\n\n"
            "Inventory loss (leak or maldistribution) starves the pump and risks "
            "cavitation, so the trip is correct. To improve resilience:\n"
            "- **Increase reservoir volume / charge margin** so brief losses "
            "don't reach the trip threshold.\n"
            "- **Automatic make-up** from a small charge cylinder via valve V2 on "
            "low-level warning, before the trip point.\n"
            "- **Leak detection + isolation** (the LSH_leak interlock) to stop "
            "the loss at source and alarm early.\n"
            "- **Two-stage level logic**: warning (open make-up) well above the "
            "trip, giving the operator time to react.")
    if o["peak_Tchip"] >= 89 and "chiptrip" in name.lower().replace(" ", ""):
        msgs.append(
            "**Chip over-temperature trip under overload.**\n\n"
            "The load exceeded what the loop can reject at this pressure. "
            "Options:\n"
            "- **Open V1** to lower HPZ pressure and saturation temperature "
            "(more sub-cooling headroom) before load peaks.\n"
            "- **Cap or throttle the IT load** (power-capping handshake with the "
            "servers) when cooling approaches its limit.\n"
            "- **Engage chiller assist** earlier so the condenser can reject the "
            "higher duty.\n"
            "- Right-size the cold plate / condenser for the true peak, not the "
            "nominal, load.")
    if any(t.startswith("sensor:") for t in trips) or "sensorfail" in name.lower():
        msgs.append(
            "**Sensor fault handled by validation/fallback (no false trip).**\n\n"
            "The PLC rejected the invalid reading and held a safe default. For "
            "production robustness add **2-out-of-3 voting** on critical "
            "sensors (chip temp, pressure, level) so a single bad transmitter "
            "neither trips the plant nor hides a real excursion.")
    if "HiPress" in trips or "highpress" in name.lower():
        msgs.append(
            "**High-pressure trip (blocked condenser / overcharge / lost heat "
            "sink).**\n\n"
            "Condensing pressure crossed the safety limit and the PLC isolated "
            "the loop — correct, since over-pressure risks seals and joints. "
            "To prevent and ride through:\n"
            "- **Relief valve + rupture disk** sized to the condenser MAWP as "
            "the hardware backstop (independent of the PLC).\n"
            "- **Head-pressure control**: modulate water flow / fan speed and "
            "open V1 to drop condensing pressure before the trip point.\n"
            "- **Condenser fouling monitoring** and redundant heat-rejection "
            "(N+1 dry coolers) so one blocked unit doesn't spike pressure.\n"
            "- **Correct charge management** to avoid overcharge, which raises "
            "condensing pressure.")
    if "water_flow_fail" in trips or "waterfail" in name.lower():
        msgs.append(
            "**Secondary water-loop failure → loss of heat sink → trip.**\n\n"
            "With no water flow the condenser can't reject heat, pressure and "
            "temperature climb, and the plant trips. Mitigations:\n"
            "- **N+1 redundant water pumps** with automatic changeover on "
            "low-flow detection (FT_w / FSL interlock).\n"
            "- **A backup heat-rejection path** (e.g. emergency dry cooler or "
            "city-water economizer) that engages on primary-loop loss.\n"
            "- **Thermal buffer / chilled-water storage** to ride out the "
            "seconds-to-minutes needed for changeover.\n"
            "- **Load shedding / power-capping** of the IT as a last-resort "
            "interlock if no heat sink is available.")
    if not msgs and o["total_trips"] == 0:
        return ("✅ Ran to a normal operating state with no trips — controller "
                "held the chip temperature and managed the loop correctly.")
    return "\n\n".join(msgs)


def custom_scenario_builder():
    st.markdown("##### Build a custom case")
    c1, c2, c3 = st.columns(3)
    with c1:
        load_mode = st.selectbox("Load profile", ["constant", "step", "ramp"])
        Q0 = st.slider("Initial load [kW]", 20.0, 200.0, 80.0, 5.0)
        Q1 = st.slider("Final load [kW]", 20.0, 200.0, 120.0, 5.0,
                       disabled=(load_mode == "constant"))
    with c2:
        water_mode = st.selectbox("Water inlet", ["constant", "step"])
        Tw0 = st.slider("Initial water [°C]", 18.0, 40.0, 30.0, 1.0)
        Tw1 = st.slider("Final water [°C]", 18.0, 45.0, 38.0, 1.0,
                        disabled=(water_mode == "constant"))
    with c3:
        fault = st.selectbox("Inject fault",
                             ["none", "lowlevel", "pumpfail", "sensorfail",
                              "highpress", "waterfail"])
        t_change = st.slider("Event time [s]", 30.0, 500.0, 150.0, 10.0)
        t_end = st.slider("Duration [s]", 120.0, 1000.0, 420.0, 30.0)
    reuse = st.checkbox("Heat-reuse demand present")

    scn = core.build_scenario(
        load_mode=load_mode, Q0=Q0, Q1=Q1, t_change=t_change,
        ramp_end=t_change + 120, water_mode=water_mode, Tw0=Tw0, Tw1=Tw1,
        tw_change=t_change, fault=(None if fault == "none" else fault),
        fault_start=t_change, fault_end=t_change + 60,
        reuse_demand=reuse, t_end=t_end)
    label = f"Custom ({load_mode} load, {fault} fault)"
    return {label: scn}


def dynamic_figure(A, df):
    fig = make_subplots(rows=2, cols=2, subplot_titles=(
        "Temperatures", "Actuator commands",
        "Inventory / flow / quality", "PLC state / alarms / trips"))
    # temps
    for col, color in [("Tchip", PALETTE["red"]), ("Tcond", PALETTE["orange"]),
                       ("Tevap", PALETTE["blue"]), ("Tw_out", PALETTE["green"])]:
        fig.add_trace(go.Scatter(x=df.t, y=df[col], name=col,
                                 line=dict(color=color)), row=1, col=1)
    fig.add_hline(y=A.T_chip_trip_C, line_dash="dot", line_color="red",
                  row=1, col=1)
    # actuators
    for col in ["cmd_pump", "cmd_V1", "cmd_V2", "cmd_water", "cmd_chiller"]:
        fig.add_trace(go.Scatter(x=df.t, y=df[col], name=col.replace("cmd_", "")),
                      row=1, col=2)
    # inventory
    fig.add_trace(go.Scatter(x=df.t, y=df.level, name="level %"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.t, y=df.mdot * 20, name="mdot×20"), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.t, y=df.x_out * 100, name="quality×100"),
                  row=2, col=1)
    # state
    fig.add_trace(go.Scatter(x=df.t, y=[core.STATE_ORDER[s] for s in df.state],
                             name="state", line_shape="hv"), row=2, col=2)
    fig.add_trace(go.Scatter(x=df.t, y=df.n_trips, name="#trips"), row=2, col=2)
    fig.update_yaxes(tickvals=list(core.STATE_ORDER.values()),
                     ticktext=list(core.STATE_ORDER.keys()), row=2, col=2,
                     tickfont=dict(size=8))
    fig.update_layout(height=620, margin=dict(t=40, b=10), showlegend=True,
                      legend=dict(font=dict(size=9)))
    return fig


# --------------------------------------------------------------------------- #
#  TAB 5 — Comparison (BAU)
# --------------------------------------------------------------------------- #
def tab_comparison(A, ss):
    st.header("Comparison vs Business-as-Usual")
    st.write("Two-phase vs the alternatives an operator would otherwise "
             "deploy: air cooling and single-phase liquid. Adjust the "
             "comparison assumptions below.")
    c1, c2, c3 = st.columns(3)
    elec = c1.slider("Electricity price [$/kWh]", 0.05, 0.30, 0.12, 0.01)
    pue_air = c2.slider("Air cooling PUE", 1.30, 1.90, 1.55, 0.01,
                        help="Full-facility PUE for traditional air cooling")
    pue_sp = c3.slider("Single-phase DLC PUE", 1.05, 1.40, 1.20, 0.01,
                       help="Full-facility PUE for single-phase direct liquid")
    df = core.bau_comparison(A, ss, elec=elec, pue_air=pue_air, pue_sp=pue_sp)

    c1, c2, c3 = st.columns(3)
    colors = [PALETTE["grey"], PALETTE["blue"], PALETTE["red"]]
    with c1:
        fig = go.Figure(go.Bar(x=df.Technology, y=df.PUE, marker_color=colors,
                               text=df.PUE.round(2), textposition="outside"))
        fig.add_hline(y=1.0, line_dash="dash", line_color="green")
        fig.update_layout(title="Full-facility PUE", height=330,
                          margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure(go.Bar(x=df.Technology, y=df.MaxDensity_kW,
                               marker_color=colors, text=df.MaxDensity_kW,
                               textposition="outside"))
        fig.update_layout(title="Max rack density [kW]", height=330,
                          margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)
    with c3:
        fig = go.Figure(go.Bar(x=df.Technology, y=df.CoolingCost_kUSD_yr,
                               marker_color=colors,
                               text=df.CoolingCost_kUSD_yr.round(1),
                               textposition="outside"))
        fig.update_layout(title=f"Cooling cost/rack/yr @ ${elec}/kWh [k$]",
                          height=330, margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)

    st.dataframe(df.round(3), use_container_width=True, hide_index=True)
    sav = df.iloc[0].CoolingCost_kUSD_yr - df.iloc[2].CoolingCost_kUSD_yr
    st.success(f"Two-phase saves ≈ **${sav:.1f}k/rack/yr** in cooling energy "
               f"vs air at this load and tariff.")
    st.caption("Two-phase uses the model's full-facility PUE; air and "
               "single-phase PUE are your inputs above.")


# --------------------------------------------------------------------------- #
#  TAB 6 — Economics
# --------------------------------------------------------------------------- #
def tab_economics(A, ss):
    st.header("Economics Dashboard")
    st.write("CAPEX, payback, NPV, IRR and total cost of ownership vs an "
             "air-cooled baseline — at single-rack and 100 MW campus scale.")

    # ---- parameters hidden behind a collapsed expander ----
    with st.expander("⚙️ Edit cost & finance assumptions", expanded=False):
        c1, c2, c3 = st.columns(3)
        elec = c1.slider("Electricity [$/kWh]", 0.05, 0.30, 0.12, 0.01)
        disc = c2.slider("Discount rate", 0.03, 0.15, 0.08, 0.01)
        years = c3.slider("Project life [yr]", 5, 20, 10, 1)
        c1, c2, c3 = st.columns(3)
        capex_2ph = c1.slider("Two-phase CAPEX [$/kW]", 2500, 6000, 4200, 100)
        capex_air = c2.slider("Air CAPEX [$/kW]", 1200, 3500, 2500, 100)
        redund = c3.slider("Redundancy factor (N+1)", 1.0, 1.5, 1.20, 0.05)
        c1, c2, c3 = st.columns(3)
        heat_price = c1.slider("Heat sale [$/MWh_th]", 0.0, 80.0, 25.0, 5.0)
        reuse_frac = c2.slider("Heat reuse fraction", 0.0, 1.0, 0.5, 0.05)
        om = c3.slider("O&M [% capex/yr]", 0.0, 0.10, 0.04, 0.01)
        pue_air_econ = c1.slider("Air PUE (for savings)", 1.30, 1.90, 1.55, 0.01)

    E = core.Econ(elec_price=elec, discount_rate=disc, project_years=years,
                  capex_2ph_perkW=float(capex_2ph), capex_air_perkW=float(capex_air),
                  redundancy_factor=redund, heat_price_perMWh=heat_price,
                  heat_reuse_frac=reuse_frac, om_frac=om)

    r_rack = core.economics(A.Q_rack_kW, E, ss["PUE_full"], pPUE_air=pue_air_econ,
                            label="rack")
    campus_MW = 100.0
    Q_rec = campus_MW * ss["PUE_full"] * 0.65
    r_camp = core.economics(campus_MW * 1000, E, ss["PUE_full"],
                            pPUE_air=pue_air_econ, reuse_MW_th=Q_rec, label="campus")
    irr_camp = core.irr(r_camp["cfs"])

    # ---- KPI hero strip ----
    st.markdown("""
    <style>
    .econ-card{background:#FFFFFF;border:1px solid #D8E0EA;border-radius:12px;
        padding:14px 16px;text-align:center;box-shadow:0 10px 24px rgba(15,23,42,.05);}
    .econ-lab{font-size:0.75rem;color:#64748B;text-transform:uppercase;
        letter-spacing:0.05em;}
    .econ-val{font-size:1.7rem;font-weight:700;color:#0F172A;}
    .econ-pos{color:#16A34A;} .econ-neg{color:#DC2626;}
    </style>""", unsafe_allow_html=True)

    def ecard(col, lab, val, cls=""):
        col.markdown(f"<div class='econ-card'><div class='econ-lab'>{lab}</div>"
                     f"<div class='econ-val {cls}'>{val}</div></div>",
                     unsafe_allow_html=True)

    st.markdown("##### Campus (100 MW) headline")
    c1, c2, c3, c4 = st.columns(4)
    ecard(c1, "Payback", f"{r_camp['pbp']:.1f} yr")
    ecard(c2, f"NPV ({years} yr)", f"${r_camp['npv']/1e6:,.0f} M",
          "econ-pos" if r_camp["npv"] > 0 else "econ-neg")
    ecard(c3, "IRR", f"{irr_camp*100:.0f}%" if irr_camp else "n/a",
          "econ-pos" if (irr_camp or 0) > disc else "econ-neg")
    ecard(c4, "Incremental CAPEX", f"${r_camp['capex_delta']/1e6:,.0f} M")

    st.markdown("##### Single rack")
    c1, c2, c3, c4 = st.columns(4)
    ecard(c1, "Payback", f"{r_rack['pbp']:.1f} yr")
    ecard(c2, f"NPV ({years} yr)", f"${r_rack['npv']/1e3:,.0f} k",
          "econ-pos" if r_rack["npv"] > 0 else "econ-neg")
    ecard(c3, "Annual saving", f"${r_rack['annual_net']/1e3:,.0f} k")
    ecard(c4, "Incremental CAPEX", f"${r_rack['capex_delta']/1e3:,.0f} k")

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        # TCO stacked comparison (campus)
        t = core.tco(r_camp, E, campus_MW * 1000, ss["PUE_full"], pue_air_econ)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=["Air cooling", "Two-phase"],
                             y=[t["tco_air"] / 1e6, t["tco_2ph"] / 1e6],
                             marker_color=[PALETTE["grey"], PALETTE["red"]],
                             text=[f"${t['tco_air']/1e6:,.0f}M",
                                   f"${t['tco_2ph']/1e6:,.0f}M"],
                             textposition="outside"))
        fig.update_layout(title=f"{years}-yr Total Cost of Ownership (campus)",
                          yaxis_title="$M", height=360, margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        for r, color, nm in [(r_rack, PALETTE["blue"], "rack"),
                             (r_camp, PALETTE["red"], "campus")]:
            cum = core.cumulative_cashflow(r, E)
            fig.add_trace(go.Scatter(x=list(range(len(cum))),
                                     y=np.array(cum) / 1e6, mode="lines+markers",
                                     name=nm, line=dict(color=color)))
        fig.add_hline(y=0, line_dash="dash", line_color="black")
        fig.update_layout(title="Cumulative discounted cash flow [$M]",
                          xaxis_title="year", height=360, margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        base, tor = core.npv_tornado(campus_MW * 1000, E, ss["PUE_full"], Q_rec)
        fig = go.Figure()
        for nm, lo, hi in tor:
            fig.add_trace(go.Bar(y=[nm], x=[hi - lo], base=min(lo, hi),
                                 orientation="h", marker_color=PALETTE["purple"],
                                 showlegend=False))
        fig.add_vline(x=base, line_dash="dash", line_color="black",
                      annotation_text="base")
        fig.update_layout(title="Campus NPV sensitivity (±30%) [$M]",
                          height=360, margin=dict(t=40, b=10))
        safe_plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown("**Campus year-by-year cash flow**")
        yt = core.yearly_table(r_camp, E)
        yt_disp = yt.copy()
        for col in ["Cash flow $", "Discounted $", "Cumulative $",
                    "Cumulative disc. $"]:
            yt_disp[col] = (yt_disp[col] / 1e6).round(1)
        yt_disp.columns = ["Year", "CF $M", "Disc $M", "Cum $M", "Cum disc $M"]
        st.dataframe(yt_disp, use_container_width=True, hide_index=True,
                     height=340)

    st.caption("CAPEX from 2026 industry analysis (D2C liquid ~$3.5–5k/kW, air "
               "~$1.8–3.2k/kW); two-phase includes an N+1 redundancy uplift. "
               "Screening economics — not a board-level investment case.")


# --------------------------------------------------------------------------- #
#  TAB 7 — Scale-up
# --------------------------------------------------------------------------- #
def tab_scaleup(A, ss):
    st.header("Holistic Scale-Up & Waste Heat")
    campus_MW = st.slider("Campus IT load [MW]", 10.0, 500.0, 100.0, 10.0)
    tbl, info = core.campus_scaleup(A, ss, campus_MW=campus_MW)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Racks", f"{info['n_racks']:,.0f}")
    c2.metric("Heat rejected", f"{info['Q_reject_MW']:.0f} MW",
              help="> IT load: pump/fan/UPS power also becomes heat")
    c3.metric("Recoverable heat", f"{info['Q_recover_MW']:.0f} MW",
              help=info["grade"])
    c4.metric("CO₂ avoided", f"{info['co2_avoided_kt']:,.0f} kt/yr")

    st.warning(f"**Why does {campus_MW:.0f} MW IT reject "
               f"{info['Q_reject_MW']:.0f} MW?** Energy is conserved — ~100% of "
               f"the electricity (IT + pumps + fans + UPS) becomes heat, so "
               f"heat rejected = IT × full-PUE.")

    # colored clickable sub-section selector
    sub_choice = st.radio(
        "scaleup_nav",
        ["🟢 Energy & reuse", "🔵 Climate & heat off-take",
         "🟣 Build-out, carbon & water"],
        horizontal=True, label_visibility="collapsed")

    # ---- Energy & reuse ----
    if sub_choice.startswith("🟢"):
        c1, c2 = st.columns(2)
        with c1:
            labels = ["IT electricity", "Heat rejected", "Recoverable",
                      "Lost (low grade)"]
            vals = [campus_MW, info["Q_reject_MW"], info["Q_recover_MW"],
                    info["Q_reject_MW"] - info["Q_recover_MW"]]
            fig = go.Figure(go.Bar(x=labels, y=vals,
                                   marker_color=["#444", PALETTE["red"],
                                                 PALETTE["green"], "#bbb"],
                                   text=[f"{v:.0f}" for v in vals],
                                   textposition="outside"))
            fig.update_layout(title="Energy cascade [MW]", height=380,
                              margin=dict(t=40, b=10))
            safe_plotly_chart(fig, use_container_width=True)
        with c2:
            uses = ["District heating", "Industrial pre-heat",
                    "Absorption cooling", "Greenhouse/agri"]
            share = [0.45, 0.25, 0.20, 0.10]
            fig = go.Figure(go.Pie(labels=uses,
                                   values=[info["Q_recover_MW"] * s for s in share],
                                   marker_colors=[PALETTE["green"], PALETTE["blue"],
                                                  PALETTE["purple"], PALETTE["orange"]]))
            fig.update_layout(title=f"Reuse allocation ({info['Q_recover_MW']:.0f} MW_th)",
                              height=380, margin=dict(t=40, b=10))
            safe_plotly_chart(fig, use_container_width=True)
        st.dataframe(tbl.round(1), use_container_width=True, hide_index=True)
        st.markdown(
            "**Where the heat can go** (temperature-grade dependent): district "
            "heating (direct ≥60 °C, or heat-pump-boosted from 40–55 °C), "
            "industrial/process pre-heat, absorption chilling, "
            "greenhouses/aquaculture, and low-temperature desalination. "
            "Two-phase keeps more heat at a *usable* grade thanks to its "
            "stable, higher condensing temperature.")

    # ---- Climate & heat off-take ----
    elif sub_choice.startswith("🔵"):
        climate = st.selectbox("Site climate", list(core.CLIMATE_PROFILES.keys()))
        ca = core.climate_analysis(A, ss, campus_MW, climate)
        c1, c2, c3 = st.columns(3)
        c1.metric("Free-cooling fraction", f"{ca['free_frac']*100:.0f}%",
                  help="Share of the year heat rejects without a chiller")
        c2.metric("Chiller energy", f"{ca['chiller_MWh']/1000:,.0f} GWh/yr")
        c3.metric("Heat off-take feasible", f"{ca['Q_offtake_MW']:.0f} MW",
                  help="Recoverable × local district-heat demand uptake")
        c1, c2 = st.columns(2)
        with c1:
            fracs = {k: v["free_frac"] for k, v in core.CLIMATE_PROFILES.items()}
            fig = go.Figure(go.Bar(x=list(fracs.keys()),
                                   y=[v * 100 for v in fracs.values()],
                                   marker_color=[PALETTE["green"] if k == climate
                                                 else PALETTE["grey"]
                                                 for k in fracs]))
            fig.update_layout(title="Free-cooling fraction by climate [%]",
                              height=360, margin=dict(t=40, b=40),
                              xaxis_tickangle=-25)
            safe_plotly_chart(fig, use_container_width=True)
        with c2:
            offt = {k: core.climate_analysis(A, ss, campus_MW, k)["Q_offtake_MW"]
                    for k in core.CLIMATE_PROFILES}
            fig = go.Figure(go.Bar(x=list(offt.keys()), y=list(offt.values()),
                                   marker_color=[PALETTE["purple"] if k == climate
                                                 else PALETTE["grey"]
                                                 for k in offt]))
            fig.update_layout(title="Feasible heat off-take by climate [MW]",
                              height=360, margin=dict(t=40, b=40),
                              xaxis_tickangle=-25)
            safe_plotly_chart(fig, use_container_width=True)
        st.info(f"In a **{climate}** climate this campus runs on free cooling "
                f"~{ca['free_frac']*100:.0f}% of the year, and local heat demand "
                f"can absorb about {ca['Q_offtake_MW']:.0f} MW of the recoverable "
                f"heat. Cold climates favour both free cooling and district-heat "
                f"reuse; hot-humid sites lean on the chiller and have little "
                f"heat off-take.")
        with st.expander("Where do these climate numbers come from?"):
            st.markdown(
                "These are **representative planning estimates**, not "
                "site-measured data, and all are editable in "
                "`core/economics.py → CLIMATE_PROFILES`:\n"
                "- **Free-cooling fraction** — the share of the year outdoor "
                "air/water is cool enough to reject heat at the design "
                "condensing temperature without a chiller. Anchored to typical "
                "wet-bulb/dry-bulb climate bins: cold climates (Nordic) reach "
                "~90%+, hot-humid (tropical) only ~20%. Order-of-magnitude "
                "consistent with published free-cooling-hours maps.\n"
                "- **District-heat demand uptake** — a 0–1 factor for how much "
                "of the recoverable heat a local network could actually absorb, "
                "reflecting whether district heating exists and is sized for it "
                "(high in Nordic/continental Europe, near zero in hot climates "
                "without heat networks).\n"
                "- **Chiller energy** — computed from (1 − free fraction) × heat "
                "rejected ÷ assumed chiller COP (~4.5).\n\n"
                "For a real project these should be replaced with site TMY "
                "weather data, the actual condensing temperature, and a signed "
                "heat-offtake agreement.")

    # ---- Build-out, carbon & water ----
    elif sub_choice.startswith("🟣"):
        c1, c2 = st.columns(2)
        years = c1.slider("Build-out period [yr]", 2, 8, 5, 1)
        grid = c2.slider("Grid carbon intensity [kgCO₂/kWh]", 0.0, 0.8, 0.35, 0.05)
        bo = core.buildout_analysis(A, ss, campus_MW, years=years,
                                    grid_kgco2_kwh=grid)
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=bo.Year, y=bo["CAPEX $M"], name="CAPEX $M",
                                 marker_color=PALETTE["blue"]))
            fig.add_trace(go.Scatter(x=bo.Year, y=bo["Cumulative MW"],
                                     name="Cumulative MW", yaxis="y2",
                                     line=dict(color=PALETTE["red"])))
            fig.update_layout(title="Phased build: CAPEX & capacity",
                              yaxis=dict(title="CAPEX $M"),
                              yaxis2=dict(title="MW", overlaying="y", side="right"),
                              height=370, margin=dict(t=40, b=10),
                              legend=dict(orientation="h"))
            safe_plotly_chart(fig, use_container_width=True)
        with c2:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=bo.Year, y=bo["Grid CO₂ kt/yr"],
                                     name="CO₂ kt/yr",
                                     line=dict(color=PALETTE["grey"])),
                          secondary_y=False)
            fig.add_trace(go.Scatter(x=bo.Year, y=bo["Water Mm³/yr"],
                                     name="Water Mm³/yr",
                                     line=dict(color=PALETTE["blue"])),
                          secondary_y=True)
            fig.update_yaxes(title_text="CO₂ kt/yr", secondary_y=False)
            fig.update_yaxes(title_text="Water Mm³/yr", secondary_y=True)
            fig.update_layout(title="Annual carbon & water footprint",
                              height=370, margin=dict(t=40, b=10),
                              legend=dict(orientation="h"))
            safe_plotly_chart(fig, use_container_width=True)
        disp = bo.copy()
        for c in ["Added MW", "Cumulative MW", "CAPEX $M", "Facility GWh/yr",
                  "Water Mm³/yr", "Grid CO₂ kt/yr"]:
            disp[c] = disp[c].round(2)
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.caption("Two-phase loops are closed and largely water-free; the small "
                   "water figure is evaporative make-up on the reject side during "
                   "chiller-assisted hours. Grid CO₂ is the operational footprint "
                   "of facility electricity at the chosen grid intensity.")


# --------------------------------------------------------------------------- #
#  TAB 8 — Refrigerants & sizing
# --------------------------------------------------------------------------- #
def tab_refrig_sizing(A):
    st.header("Refrigerants & Component Sizing")
    st.subheader("Refrigerant comparison")
    df = core.refrigerant_comparison(A)
    st.dataframe(df.round(3), use_container_width=True, hide_index=True)
    ok = df[df.Status == "OK"]
    if len(ok):
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=ok.Fluid, y=ok.Pevap_bar, name="P_evap"))
            fig.add_trace(go.Bar(x=ok.Fluid, y=ok.Pcond_bar, name="P_cond"))
            fig.update_layout(title="Operating pressures [bar]", barmode="group",
                              height=350, margin=dict(t=40, b=10))
            safe_plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure(go.Bar(x=ok.Fluid, y=ok.hfg_kJ_kg,
                                   marker_color=PALETTE["green"]))
            fig.update_layout(title="Latent heat h_fg [kJ/kg]", height=350,
                              margin=dict(t=40, b=10))
            safe_plotly_chart(fig, use_container_width=True)
    st.caption("CO₂ is transcritical at these temperatures (critical point "
               "≈31 °C) so it has no subcritical two-phase regime here.")

    st.subheader("Component sizing")
    sz = core.sizing(A)
    st.dataframe(sz.round(3), use_container_width=True, hide_index=True)

    csv = sz.to_csv(index=False).encode()
    st.download_button("⬇ Download sizing CSV", csv, "sizing.csv", "text/csv")


# --------------------------------------------------------------------------- #
#  TAB 9 — ADAMS interactive dashboard (V1-driven HPZ pressure model)
# --------------------------------------------------------------------------- #
def _sat_T_from_P(fluid, P_bar):
    """Saturation temperature [°C] at pressure P_bar for any fluid."""
    if fluid == "R1336mzz(Z)":
        return core._r1336_tsat_C(P_bar)
    # CoolProp inverse: find Tsat at this pressure
    try:
        from CoolProp.CoolProp import PropsSI
        from core.fluids import FLUID_ALIAS
        return PropsSI("T", "P", P_bar * 1e5, "Q", 1, FLUID_ALIAS[fluid]) - 273.15
    except Exception:
        return core._r1336_tsat_C(P_bar)


def _adams_pressure_range(fluid):
    """Min/max HPZ pressure for the fluid: saturation P at 35°C and 75°C."""
    if fluid == "R1336mzz(Z)":
        return 1.3, 5.8
    lo = core.sat_props(fluid, 35.0, 1.0)
    hi = core.sat_props(fluid, 75.0, 1.0)
    p_lo = lo["P"] / 1e5 if lo.get("ok") else 1.3
    p_hi = hi["P"] / 1e5 if hi.get("ok") else 5.8
    return p_lo, p_hi


def adams_compute(v1_pct, q_chip_W, t_amb_C, fluid="R1336mzz(Z)", q_nom_W=1000.0):
    """ADAMS two-phase model. V1 sets HPZ pressure; chip load and ambient
    propagate through a small physical heat balance so all KPIs respond.
    Fluid-aware: R1336mzz(Z) uses its vendor curve, others use CoolProp.
    """
    P_min, P_max = _adams_pressure_range(fluid)
    dP_cp = 0.48          # bar across 4 Venturi stages
    Q_NOM = q_nom_W       # nominal heat load per plate [W]

    load_factor = q_chip_W / Q_NOM

    # Free-cooling offset: how far above ambient the external heat sink can run.
    # Cold ambient gives headroom; warm ambient raises the minimum condensing
    # temperature and therefore the loop back-pressure.
    pts = [(10, 18.0), (28, 15.0), (30, 10.0), (50, 4.0)]
    if t_amb_C <= pts[0][0]:
        offset = pts[0][1]
    elif t_amb_C >= pts[-1][0]:
        offset = pts[-1][1]
    else:
        for (t0, o0), (t1, o1) in zip(pts, pts[1:]):
            if t0 <= t_amb_C <= t1:
                offset = o0 + (o1 - o0) * (t_amb_C - t0) / (t1 - t0)
                break

    cond_approach = 3.0 * load_factor
    sink_limited_T = t_amb_C + offset + cond_approach
    try:
        P_sink = core._r1336_psat_bar(sink_limited_T) if fluid == "R1336mzz(Z)" else core.sat_props(fluid, sink_limited_T, 1.0).get("P", P_min * 1e5) / 1e5
    except Exception:
        P_sink = P_min

    # V1 imposes a pressure target; condenser/ambient imposes a lower bound.
    # The actual HPZ pressure is the controlling back-pressure plus a load term.
    P_v1 = P_min + (P_max - P_min) * (v1_pct / 100.0)
    P_load = 0.25 * (load_factor - 1.0) * (P_max - P_min) / 4.5
    hpz_bar = max(P_v1 + P_load, P_sink)
    hpz_bar = float(np.clip(hpz_bar, P_min, P_max + 1.0))

    t_sat_out = _sat_T_from_P(fluid, hpz_bar)
    t_sat_in = _sat_T_from_P(fluid, hpz_bar + dP_cp)

    # cold-plate ΔT scales with heat flux (finite conductance): 18 K at nominal
    dT_cp = 18.0 * load_factor
    t_junc_in = t_sat_in + dT_cp          # hottest point
    t_junc_out = t_sat_out + dT_cp

    # The condenser must be above both the ambient-driven sink limit and the
    # refrigerant saturation temperature.
    t_cond = max(sink_limited_T, t_sat_out + 1.0)
    t_water_out = t_cond - 5.0
    t_water_in = t_water_out - 8.0 * load_factor

    if t_sat_out >= 60:
        mode = "Circular"
    elif t_sat_out <= t_amb_C + offset:
        mode = "Performance"
    else:
        mode = "Standby Thermal"

    return dict(hpz_bar=hpz_bar, t_sat_out=t_sat_out, t_sat_in=t_sat_in,
                t_junc_in=t_junc_in, t_junc_out=t_junc_out, t_cond=t_cond,
                t_water_out=t_water_out, t_water_in=t_water_in, mode=mode,
                offset=offset, dT_cp=dT_cp, load_factor=load_factor,
                sink_limited_T=sink_limited_T, P_sink=P_sink)


def _gauge(value, vmin, vmax, title, unit, danger=None, warning=None):
    """Plotly gauge with optional warning/danger zones."""
    steps = []
    if warning is not None and danger is not None:
        steps = [dict(range=[vmin, warning], color="#DCFCE7"),
                 dict(range=[warning, danger], color="#FEF3C7"),
                 dict(range=[danger, vmax], color="#FEE2E2")]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(suffix=f" {unit}", font=dict(size=34, color=THEME["text"])),
        title=dict(text=title, font=dict(size=14, color=THEME["muted"])),
        gauge=dict(axis=dict(range=[vmin, vmax], tickcolor="#888"),
                   bar=dict(color=THEME["accent"]), bgcolor=THEME["panel"],
                   borderwidth=1, bordercolor=THEME["line"], steps=steps,
                   threshold=dict(line=dict(color="red", width=3),
                                  value=danger) if danger else None)))
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=50, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color=THEME["text"]))
    return fig


def _temp_bar(value, label):
    """Horizontal temperature bar with yellow (>85) / red (>95) zones."""
    color = THEME["accent"]
    if value >= 95:
        color = THEME["danger"]
    elif value >= 85:
        color = THEME["warn"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[value], y=[label], orientation="h",
                         marker_color=color, width=0.5,
                         text=[f"{value:.1f} °C"], textposition="outside",
                         textfont=dict(size=18, color=THEME["text"])))
    # zone shading
    fig.add_vrect(x0=85, x1=95, fillcolor=THEME["warn"], opacity=0.18, line_width=0)
    fig.add_vrect(x0=95, x1=130, fillcolor=THEME["danger"], opacity=0.18, line_width=0)
    fig.add_vline(x=85, line_dash="dot", line_color=THEME["warn"])
    fig.add_vline(x=95, line_dash="dot", line_color=THEME["danger"])
    fig.update_layout(height=130, margin=dict(l=10, r=60, t=10, b=10),
                      xaxis=dict(range=[20, 130], title="°C",
                                 color=THEME["muted"], gridcolor=THEME["line"]),
                      yaxis=dict(color=THEME["muted"]),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig


def tab_adams(A):
    # Light dashboard card styling scoped to this tab
    st.markdown("""
    <style>
    .adams-card {background:#FFFFFF; border:1px solid #D8E0EA; border-radius:12px;
                 padding:14px 18px; margin-bottom:10px; box-shadow:0 10px 24px rgba(15,23,42,.05);}
    .adams-val {font-size:2.0rem; font-weight:700; color:#0F172A; line-height:1.1;}
    .adams-lab {font-size:0.8rem; color:#64748B; text-transform:uppercase;
                letter-spacing:0.05em;}
    .adams-unit {font-size:1.0rem; color:#64748B;}
    </style>
    """, unsafe_allow_html=True)

    st.header("ADAMS Live Dashboard")
    # per-chip nominal load comes from the sidebar (rack load / chip count)
    q_nom = A.Q_rack_kW * 1000.0 / A.n_chips

    c1, c2, c3 = st.columns(3)
    v1 = c1.slider("V1 valve position [% closed]", 0, 100, 30, 1,
                   help="0% = fully open (min pressure), 100% = fully closed (max)")
    q_lo, q_hi = max(100, int(q_nom * 0.3)), int(q_nom * 2.5)
    q_chip = c2.slider("Chip heat load [W]", q_lo, q_hi, int(q_nom), 50,
                       help="Defaults to the sidebar per-chip load; adjust to "
                            "explore off-design")
    t_amb = c3.slider("Ambient temperature [°C]", 10, 50, 25, 1)

    r = adams_compute(v1, q_chip, t_amb, fluid=A.fluid, q_nom_W=q_nom)

    # ---- mode indicator ----
    mode_color = {"Performance": THEME["safe"], "Standby Thermal": THEME["warn"],
                  "Circular": THEME["danger"]}[r["mode"]]
    st.markdown(
        f"<div class='adams-card' style='background:{mode_color};"
        f"text-align:center;'><span class='adams-lab' style='color:#fff;'>"
        f"Operating Mode</span><div class='adams-val' style='color:#fff;'>"
        f"{r['mode']}</div></div>", unsafe_allow_html=True)

    # ---- top row: gauges ----
    g1, g2 = st.columns(2)
    with g1:
        safe_plotly_chart(_gauge(r["hpz_bar"], 1.0, 6.0, "HPZ Pressure", "bar"),
                        use_container_width=True)
    with g2:
        peak = max(r["t_junc_in"], r["t_junc_out"])
        safe_plotly_chart(_gauge(peak, 20, 130, "Peak Junction Temp", "°C",
                               danger=95, warning=85), use_container_width=True)

    # ---- junction temperature bars ----
    st.markdown("##### Chip junction temperature (yellow >85°C, red >95°C)")
    b1, b2 = st.columns(2)
    with b1:
        safe_plotly_chart(_temp_bar(r["t_junc_in"], "T_junc inlet (hottest)"),
                        use_container_width=True)
    with b2:
        safe_plotly_chart(_temp_bar(r["t_junc_out"], "T_junc outlet"),
                        use_container_width=True)

    # ---- numeric dashboard ----
    def card(col, label, value, unit=""):
        col.markdown(
            f"<div class='adams-card'><span class='adams-lab'>{label}</span>"
            f"<div class='adams-val'>{value}<span class='adams-unit'> {unit}"
            f"</span></div></div>", unsafe_allow_html=True)

    st.markdown("##### Saturation & loop temperatures")
    d1, d2, d3, d4 = st.columns(4)
    card(d1, "T_sat inlet", f"{r['t_sat_in']:.1f}", "°C")
    card(d2, "T_sat outlet", f"{r['t_sat_out']:.1f}", "°C")
    card(d3, "T_condensation", f"{r['t_cond']:.1f}", "°C")
    card(d4, "T_water out", f"{r['t_water_out']:.1f}", "°C")

    d1, d2, d3, d4 = st.columns(4)
    card(d1, "HPZ pressure", f"{r['hpz_bar']:.2f}", "bar")
    card(d2, "T_junction inlet", f"{r['t_junc_in']:.1f}", "°C")
    card(d3, "T_junction outlet", f"{r['t_junc_out']:.1f}", "°C")
    card(d4, "Cold-plate ΔT", f"{r['dT_cp']:.1f}", "°C")

    d1, d2, d3, d4 = st.columns(4)
    card(d1, "T_water in", f"{r['t_water_in']:.1f}", "°C")
    card(d2, "Heat-sink limit", f"{r['sink_limited_T']:.1f}", "°C")
    card(d3, "Heat load", f"{q_chip:.0f}", "W")
    card(d4, "Load factor", f"{r['load_factor']:.2f}", "×nom")

    if max(r["t_junc_in"], r["t_junc_out"]) >= 95:
        st.error("⚠️ Junction temperature in DANGER zone (>95 °C) — open V1 "
                 "to drop HPZ pressure and lower saturation temperature.")
    elif max(r["t_junc_in"], r["t_junc_out"]) >= 85:
        st.warning("Junction temperature in warning zone (>85 °C).")

    with st.expander("How the model responds to each input"):
        st.markdown(f"""
- **V1 → HPZ pressure**: linear 1.3 bar (open) to 5.8 bar (closed), plus a
  vapor-load term so heavier chip load raises back-pressure → now
  **{r['hpz_bar']:.2f} bar**.
- **Chip heat load** ({q_chip:.0f} W = {r['load_factor']:.2f}× nominal): scales
  the cold-plate ΔT (now **{r['dT_cp']:.1f} °C**, 18 °C at nominal load), nudges
  HPZ
  pressure, and widens the condenser approach and water ΔT. So raising load
  pushes every junction and loop temperature up.
- **Ambient** ({t_amb:.0f} °C): sets the heat-sink limit
  (**{r['sink_limited_T']:.1f} °C**, offset +{r['offset']:.1f} °C). Warm ambient
  now raises the condenser floor and, when that floor is higher than the V1 target,
  it also raises HPZ pressure and junction temperature. If V1 is nearly closed,
  V1 can still dominate the pressure.
- **T_junction = T_sat + cold-plate ΔT**; inlet uses HPZ + 0.48 bar
  (4 Venturi × 0.12 bar).
- **Mode**: Performance if T_sat_out ≤ ambient+offset; Circular if
  T_sat_out ≥ 60 °C; else Standby Thermal.
        """)



# --------------------------------------------------------------------------- #
#  Journey-oriented pages: polished product shell over existing model modules
# --------------------------------------------------------------------------- #
def coldplate_snapshot(A, ss):
    """Best-effort cold-plate KPI bundle used by the command center/report."""
    try:
        ev = core.sat_props(A.fluid, A.T_evap_C, 0.5)
        if not ev.get("ok"):
            return {}
        cp = core.ColdPlate()
        return core.coldplate_solve(cp, A.Q_rack_kW * 1e3 / A.n_chips,
                                    ss["mdot"] / A.n_chips, ev, A)
    except Exception:
        return {}


def operating_verdict(A, ss):
    cp = coldplate_snapshot(A, ss)
    chip = cp.get("Tchip_C", A.T_chip_target_C)
    chip_cls = severity(chip, A.T_chip_target_C, A.T_chip_trip_C)
    pue_cls = severity(ss["PUE_full"], 1.18, 1.35)
    chf_cls = severity(cp.get("CHF_margin", 3.0), 2.0, 1.25, invert=True)
    if "danger" in (chip_cls, pue_cls, chf_cls):
        return "Attention required", "danger", cp
    if "warn" in (chip_cls, pue_cls, chf_cls) or ss.get("Qchiller_kW", 0) > 0:
        return "Watch operating margin", "warn", cp
    return "Healthy design window", "safe", cp


def tab_command_center(A, ss):
    verdict, cls, cp = operating_verdict(A, ss)
    section_intro(
        "Command center",
        "One clean engineering view for the live design",
        "The first screen now prioritizes the operating decision: load, safety margin, efficiency, flow, and heat-sink status. "
        "Green, amber, and red keep the same meaning everywhere."
    )
    st.markdown(status_pill(verdict, cls), unsafe_allow_html=True)
    st.write("")

    chip = cp.get("Tchip_C", A.T_chip_target_C)
    chip_cls = severity(chip, A.T_chip_target_C, A.T_chip_trip_C)
    pue_cls = severity(ss["PUE_full"], 1.18, 1.35)
    chiller_cls = "safe" if ss.get("Qchiller_kW", 0) <= 0.1 else "warn"
    flow_cls = "safe" if ss["Vdot_Lmin"] > 0 else "danger"

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "IT load", f"{A.Q_rack_kW:.0f}", "kW",
             f"<span class='mono'>{A.Q_rack_kW/A.n_chips:.1f}</span> kW/chip · {A.n_chips} cold plates",
             "load", "safe")
    kpi_card(c2, "Peak chip", f"{chip:.1f}", "°C",
             f"target <span class='mono'>{A.T_chip_target_C:.0f}°C</span> · trip <span class='mono'>{A.T_chip_trip_C:.0f}°C</span>",
             "temp", chip_cls)
    kpi_card(c3, "Full PUE", f"{ss['PUE_full']:.3f}", "",
             f"loop-only <span class='mono'>{ss['pPUE_loop']:.3f}</span>",
             "eff", pue_cls)
    kpi_card(c4, "Pump flow", f"{ss['Vdot_Lmin']:.0f}", "L/min",
             f"pump <span class='mono'>{ss['Wpump_W']/1000:.2f}</span> kW",
             "pump", flow_cls)

    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "Refrigerant", A.fluid, "",
             f"evap/cond <span class='mono'>{ss['Pevap_bar']:.1f}/{ss['Pcond_bar']:.1f}</span> bar",
             "fluid", "")
    kpi_card(c2, "CHF margin", f"{cp.get('CHF_margin', float('nan')):.1f}", "×",
             "dry-out margin; >2× is preferred", "shield",
             severity(cp.get("CHF_margin", 3.0), 2.0, 1.25, invert=True))
    kpi_card(c3, "Water loop", f"{ss['Vdot_w_Lmin']:.0f}", "L/min",
             f"<span class='mono'>{ss['Tw_in']:.0f}→{ss['Tw_out']:.0f}°C</span>",
             "water", "safe")
    kpi_card(c4, "Chiller assist", f"{ss.get('Qchiller_kW', 0):.0f}", "kW",
             "green means no chiller duty", "eff", chiller_cls)

    left, right = st.columns([3, 2])
    with left:
        st.markdown("##### System flow")
        safe_plotly_chart(process_flow_figure(A, ss), use_container_width=True)
    with right:
        st.markdown("##### Efficiency quality")
        safe_plotly_chart(pue_gauge(ss), use_container_width=True)

    st.markdown("### ADAMS Live Dashboard")
    tab_adams(A)


def tab_design_system(A, ss):
    section_intro(
        "Design a system",
        "Size the thermal loop, cold plate, fluid, and components",
        "This journey groups the engineering design decisions together instead of exposing the internal code structure."
    )
    view = st.radio("design_journey", ["Thermal balance", "Cold plate geometry", "Fluids & sizing"],
                    horizontal=True, label_visibility="collapsed")
    if view == "Thermal balance":
        tab_steady(A, ss)
    elif view == "Cold plate geometry":
        tab_coldplate(A, ss)
    else:
        tab_refrig_sizing(A)


def plc_architecture_figure():
    """Visualize how the stress-test page uses the PLC and plant model."""
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 12])
    fig.update_yaxes(visible=False, range=[0, 7])

    def box(x, y, w, h, label, color, border=None):
        fig.add_shape(type="rect", x0=x, y0=y, x1=x+w, y1=y+h,
                      line=dict(color=border or color, width=2), fillcolor=color,
                      opacity=.96, layer="below")
        fig.add_annotation(x=x+w/2, y=y+h/2, text=label, showarrow=False,
                           font=dict(size=15, color=THEME["text"]))

    def arrow(x1, y1, x2, y2, label=""):
        fig.add_annotation(x=x2, y=y2, ax=x1, ay=y1, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=1.3, arrowwidth=2.6, arrowcolor=THEME["accent"])
        if label:
            fig.add_annotation(x=(x1+x2)/2, y=(y1+y2)/2+.25, text=label,
                               showarrow=False, font=dict(size=12, color=THEME["muted"]),
                               bgcolor="rgba(255,255,255,.86)")

    box(.4, 4.8, 2.3, 1.1, "Supervisor<br>optimizer", "#E0F2FE", THEME["accent"])
    box(4.0, 4.8, 2.4, 1.1, "PLC<br>state machine", "#ECFDF5", THEME["safe"])
    box(7.6, 4.8, 2.3, 1.1, "Actuators<br>pump · V1 · V2", "#FEF3C7", THEME["warn"])
    box(7.6, 2.4, 2.3, 1.1, "Two-phase<br>plant model", "#F1F5F9", THEME["muted"])
    box(4.0, 2.4, 2.4, 1.1, "Sensors<br>P/T/flow/level", "#EDE9FE", THEME["purple"])
    box(.4, 2.4, 2.3, 1.1, "Alarms & trips<br>safe override", "#FEE2E2", THEME["danger"])

    arrow(2.7, 5.35, 4.0, 5.35, "setpoints")
    arrow(6.4, 5.35, 7.6, 5.35, "validated commands")
    arrow(8.75, 4.8, 8.75, 3.5, "physical response")
    arrow(7.6, 2.95, 6.4, 2.95, "measurements")
    arrow(4.0, 2.95, 2.7, 2.95, "limits")
    arrow(1.55, 3.5, 1.55, 4.8, "override")
    arrow(5.2, 3.5, 5.2, 4.8, "feedback")

    fig.update_layout(title="Closed-loop stress-test architecture", height=330,
                      margin=dict(l=10, r=10, t=55, b=10))
    return fig


def plc_state_machine_figure():
    states = [
        ("OFF", .5, 4.8, THEME["muted"]), ("PRECHECK", 2.5, 4.8, THEME["accent"]),
        ("STARTUP", 4.7, 4.8, THEME["accent"]), ("FREE COOLING", 7.0, 5.5, THEME["safe"]),
        ("HEAT REUSE", 9.3, 4.8, THEME["safe"]), ("CHILLER ASSIST", 7.0, 3.8, THEME["warn"]),
        ("TRIP", 4.7, 2.0, THEME["danger"]), ("SHUTDOWN", 2.5, 2.0, THEME["muted"]),
    ]
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 12])
    fig.update_yaxes(visible=False, range=[0, 7])
    for name, x, y, color in states:
        fig.add_shape(type="rect", x0=x, y0=y, x1=x+1.6, y1=y+.7,
                      line=dict(color=color, width=2), fillcolor="white", layer="below")
        fig.add_annotation(x=x+.8, y=y+.35, text=name, showarrow=False,
                           font=dict(size=12, color=color))
    def ar(x1,y1,x2,y2):
        fig.add_annotation(x=x2,y=y2,ax=x1,ay=y1,xref="x",yref="y",axref="x",ayref="y",
                           showarrow=True, arrowhead=3, arrowsize=1.2, arrowwidth=2,
                           arrowcolor=THEME["muted"])
    ar(2.1,5.15,2.5,5.15); ar(4.1,5.15,4.7,5.15); ar(6.3,5.15,7.0,5.85)
    ar(8.6,5.85,9.3,5.15); ar(8.6,5.15,7.8,4.5); ar(7.8,4.5,7.8,5.5)
    ar(7.0,4.15,6.3,2.35); ar(5.5,2.7,3.3,2.7); ar(2.5,2.7,1.3,4.8)
    fig.add_annotation(x=5.8, y=1.45, text="Any running state → TRIP on critical limits",
                       showarrow=False, font=dict(size=12, color=THEME["danger"]))
    fig.update_layout(title="PLC state machine used during simulation", height=300,
                      margin=dict(l=10, r=10, t=55, b=10))
    return fig


def tab_stress_test(A):
    section_intro(
        "Stress-test it",
        "Run the control system through transients and faults",
        "Use the dynamic model to test startup, load steps, heat-reuse switching, chiller assist, low level, pump failure, high temperature, and sensor faults."
    )
    v1, v2 = st.columns([1.15, 1.0])
    with v1:
        safe_plotly_chart(plc_architecture_figure(), use_container_width=True)
    with v2:
        safe_plotly_chart(plc_state_machine_figure(), use_container_width=True)
    tab_dynamic(A)


def tab_justify_it(A, ss):
    section_intro(
        "Justify it",
        "Translate thermal performance into business and scale-up impact",
        "This view collects the decision evidence: benchmark comparison, economics, and campus-level heat reuse."
    )
    view = st.radio("justify_journey", ["BAU comparison", "Economics", "Campus scale-up"],
                    horizontal=True, label_visibility="collapsed")
    if view == "BAU comparison":
        tab_comparison(A, ss)
    elif view == "Economics":
        tab_economics(A, ss)
    else:
        tab_scaleup(A, ss)


def design_kpis(label, A):
    ss = core.steady_state(A)
    cp = coldplate_snapshot(A, ss) if ss.get("ok") else {}
    return {
        "Design": label,
        "Fluid": A.fluid,
        "Rack kW": A.Q_rack_kW,
        "Chips": A.n_chips,
        "Chip °C": cp.get("Tchip_C", np.nan),
        "CHF margin ×": cp.get("CHF_margin", np.nan),
        "PUE full": ss.get("PUE_full", np.nan),
        "Loop pPUE": ss.get("pPUE_loop", np.nan),
        "Pump kW": ss.get("Wpump_W", np.nan) / 1000,
        "Ref L/min": ss.get("Vdot_Lmin", np.nan),
        "Water L/min": ss.get("Vdot_w_Lmin", np.nan),
        "Chiller kW": ss.get("Qchiller_kW", np.nan),
        "P evap bar": ss.get("Pevap_bar", np.nan),
        "P cond bar": ss.get("Pcond_bar", np.nan),
    }


def tab_scenario_comparison(A, ss):
    section_intro(
        "Scenario comparison",
        "Save up to three designs and compare them side by side",
        "Use this for Design A / B / C trade-offs. Each saved case keeps the current sidebar assumptions and recalculates the same KPI set."
    )
    if "saved_designs" not in st.session_state:
        st.session_state.saved_designs = []

    c1, c2, c3 = st.columns([2, 1, 1])
    default_label = f"Design {chr(65 + min(len(st.session_state.saved_designs), 2))}"
    label = c1.text_input("Design label", default_label)
    if c2.button("Save current design", type="primary"):
        payload = {"label": label.strip() or default_label, "assumptions": asdict(A)}
        # Replace a design with the same label, otherwise append. Keep a clean 3-case board.
        labels = [d["label"] for d in st.session_state.saved_designs]
        if payload["label"] in labels:
            st.session_state.saved_designs[labels.index(payload["label"])] = payload
        else:
            if len(st.session_state.saved_designs) >= 3:
                st.session_state.saved_designs.pop(0)
            st.session_state.saved_designs.append(payload)
        st.toast(f"Saved {payload['label']} for comparison")
    if c3.button("Clear board"):
        st.session_state.saved_designs = []

    if not st.session_state.saved_designs:
        st.info("Save the current sidebar configuration to start a comparison board.")
        return

    rows = []
    for item in st.session_state.saved_designs:
        rows.append(design_kpis(item["label"], Assumptions(**item["assumptions"])))
    df = pd.DataFrame(rows)

    st.markdown("##### KPI board")
    st.dataframe(df.round(3), use_container_width=True, hide_index=True)

    cols = st.columns(len(st.session_state.saved_designs))
    for i, item in enumerate(st.session_state.saved_designs):
        r = rows[i]
        verdict_cls = severity(r["PUE full"], 1.18, 1.35)
        with cols[i]:
            st.markdown(status_pill(item["label"], verdict_cls), unsafe_allow_html=True)
            st.caption(f"{r['Fluid']} · {r['Rack kW']:.0f} kW · PUE {r['PUE full']:.3f}")
            if st.button(f"Remove {item['label']}", key=f"remove_design_{i}"):
                st.session_state.saved_designs.pop(i)
                st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["Design"], y=df["PUE full"], name="PUE full"))
        fig.add_trace(go.Bar(x=df["Design"], y=df["Loop pPUE"], name="Loop pPUE"))
        fig.add_hline(y=1.0, line_dash="dash", line_color=THEME["safe"])
        fig.update_layout(title="Efficiency comparison", barmode="group", height=360)
        safe_plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["Design"], y=df["Pump kW"], name="Pump kW"))
        fig.add_trace(go.Bar(x=df["Design"], y=df["Chiller kW"], name="Chiller kW"))
        fig.update_layout(title="Auxiliary power pressure points", barmode="group", height=360)
        safe_plotly_chart(fig, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download comparison CSV", csv, "adams_design_comparison.csv", "text/csv")


def encode_uploaded_images(files):
    """Return image records for report preview/download."""
    records = []
    for f in files or []:
        raw = f.getvalue()
        mime = getattr(f, "type", None) or "image/png"
        data_uri = "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))
        records.append({"name": getattr(f, "name", "image"), "bytes": raw, "mime": mime, "data_uri": data_uri})
    return records


def make_report_html(A, ss, image_records=None):
    cp = coldplate_snapshot(A, ss)
    verdict, cls, _ = operating_verdict(A, ss)
    E = core.Econ()
    econ = core.economics(A.Q_rack_kW, E, ss["PUE_full"], pPUE_air=1.55)
    chip = cp.get("Tchip_C", np.nan)
    chf = cp.get("CHF_margin", np.nan)
    pbp = "n/a" if not np.isfinite(econ["pbp"]) else f"{econ['pbp']:.1f} yr"
    npv = econ["npv"] / 1000
    cls_color = {"safe": THEME["safe"], "warn": THEME["warn"], "danger": THEME["danger"]}[cls]
    img_html = ""
    if image_records:
        cards = []
        for rec in image_records[:6]:
            cards.append(f"<div><img src='{rec['data_uri']}' alt='{escape(rec['name'])}'><div class='muted-report' style='font-size:.78rem;margin-top:.25rem;'>{escape(rec['name'])}</div></div>")
        img_html = "<h3>Supporting images</h3><div class='report-image-grid'>" + "".join(cards) + "</div>"
    return f"""
<div class='report-sheet'>
  <div style='display:flex; justify-content:space-between; align-items:flex-start; gap:1rem;'>
    <div>
      <div class='muted-report' style='font-size:.78rem; text-transform:uppercase; letter-spacing:.12em;'>ADAMS one-page design brief</div>
      <h1 style='margin:.2rem 0 .35rem;'>Two-phase rack cooling concept</h1>
      <div class='muted-report'>Generated from the current live Streamlit inputs.</div>
    </div>
    <div style='border:1px solid {cls_color}; color:{cls_color}; border-radius:999px; padding:.45rem .75rem; font-weight:800;'>{escape(verdict)}</div>
  </div>
  <div class='report-grid' style='margin-top:1rem;'>
    <div class='report-metric'><div class='label'>IT load</div><div class='value'>{A.Q_rack_kW:.0f} kW</div><div class='muted-report'>{A.n_chips} chips · {A.Q_rack_kW/A.n_chips:.1f} kW/chip</div></div>
    <div class='report-metric'><div class='label'>Refrigerant</div><div class='value'>{escape(A.fluid)}</div><div class='muted-report'>{ss['Pevap_bar']:.1f}/{ss['Pcond_bar']:.1f} bar evap/cond</div></div>
    <div class='report-metric'><div class='label'>Full PUE</div><div class='value'>{ss['PUE_full']:.3f}</div><div class='muted-report'>loop-only {ss['pPUE_loop']:.3f}</div></div>
    <div class='report-metric'><div class='label'>Chip / CHF</div><div class='value'>{chip:.1f} °C</div><div class='muted-report'>CHF margin {chf:.1f}×</div></div>
  </div>
  <div style='display:grid; grid-template-columns:1.25fr .95fr; gap:1rem; margin-top:1rem;'>
    <div style='border:1px solid #CBD5E1; border-radius:14px; padding:1rem; background:white;'>
      <h3 style='margin-top:0;'>System schematic summary</h3>
      <p>Rack heat is absorbed by boiling refrigerant in the microchannel cold plate, condensed in the heat exchanger, and rejected to the secondary water loop or routed to heat reuse when outlet temperature is useful.</p>
      <table style='width:100%; border-collapse:collapse; font-size:.9rem;'>
        <tr><td><b>Refrigerant flow</b></td><td style='text-align:right;'>{ss['mdot']:.3f} kg/s · {ss['Vdot_Lmin']:.0f} L/min</td></tr>
        <tr><td><b>Water flow</b></td><td style='text-align:right;'>{ss['Vdot_w_Lmin']:.0f} L/min · {ss['Tw_in']:.0f}→{ss['Tw_out']:.0f} °C</td></tr>
        <tr><td><b>Condenser duty</b></td><td style='text-align:right;'>{ss['Qcond_kW']:.0f} kW</td></tr>
        <tr><td><b>Pump power</b></td><td style='text-align:right;'>{ss['Wpump_W']/1000:.2f} kW</td></tr>
      </table>
    </div>
    <div style='border:1px solid #CBD5E1; border-radius:14px; padding:1rem; background:white;'>
      <h3 style='margin-top:0;'>Economic screen</h3>
      <table style='width:100%; border-collapse:collapse; font-size:.9rem;'>
        <tr><td><b>Payback</b></td><td style='text-align:right;'>{pbp}</td></tr>
        <tr><td><b>NPV, 10 yr</b></td><td style='text-align:right;'>${npv:,.0f}k</td></tr>
        <tr><td><b>Annual net</b></td><td style='text-align:right;'>${econ['annual_net']/1000:,.0f}k/yr</td></tr>
        <tr><td><b>Incremental CAPEX</b></td><td style='text-align:right;'>${econ['capex_delta']/1000:,.0f}k</td></tr>
      </table>
      <p class='muted-report'>Default finance settings: $0.12/kWh electricity, 10-year life, 8% discount rate, air baseline PUE 1.55.</p>
    </div>
  </div>
  <div style='margin-top:1rem; display:grid; grid-template-columns:1fr 1fr; gap:1rem;'>
    <div style='border-left:4px solid {THEME['safe']}; padding-left:.75rem;'>
      <b>Recommended next design checks</b><br>
      <span class='muted-report'>Confirm cold-plate geometry, condenser UA, pump curve/NPSH, valve Cv, refrigerant charge, relief basis, and controls fail-safe positions with supplier data.</span>
    </div>
    <div style='border-left:4px solid {THEME['warn']}; padding-left:.75rem;'>
      <b>Decision use</b><br>
      <span class='muted-report'>Use this brief for early concept screening and trade-off discussion, not final equipment procurement.</span>
    </div>
  </div>
  {img_html}
</div>
"""


def make_report_standalone_html(A, ss, image_records=None, include_charts=True):
    css = f"""
    <style>
    body {{font-family: Inter, Segoe UI, Arial, sans-serif; background:#F8FAFC; margin:24px; color:#0F172A;}}
    .report-sheet {{background:#FFFFFF; color:#0F172A; border-radius:18px; padding:1.35rem; border:1px solid #CBD5E1; box-shadow:0 16px 42px rgba(15,23,42,.08);}}
    .muted-report {{color:#64748B;}}
    .report-grid {{display:grid; grid-template-columns:repeat(4,1fr); gap:.75rem;}}
    .report-metric {{border:1px solid #CBD5E1; border-radius:12px; padding:.75rem; background:white;}}
    .report-metric .value {{font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:1.45rem; font-weight:850;}}
    .report-metric .label {{font-size:.72rem; color:#64748B; text-transform:uppercase; letter-spacing:.08em;}}
    .report-image-grid {{display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:.75rem; margin-top:1rem;}}
    .report-image-grid img {{width:100%; border-radius:12px; border:1px solid #CBD5E1; background:white;}}
    .chart-wrap {{margin-top:18px; padding:14px; background:#FFFFFF; border:1px solid #CBD5E1; border-radius:16px;}}
    </style>
    """
    body = make_report_html(A, ss, image_records=image_records)
    charts = ""
    if include_charts:
        try:
            charts = "<div class='chart-wrap'><h2>Process flow</h2>" + process_flow_figure(A, ss).to_html(full_html=False, include_plotlyjs="cdn") + "</div>"
            charts += "<div class='chart-wrap'><h2>PUE gauge</h2>" + pue_gauge(ss).to_html(full_html=False, include_plotlyjs=False) + "</div>"
        except Exception:
            charts = ""
    return f"<!doctype html><html><head><meta charset='utf-8'><title>ADAMS Design Brief</title>{css}</head><body>{body}{charts}</body></html>"


def make_report_pdf_bytes(A, ss, image_records=None):
    """Create a compact PDF brief. Requires reportlab (listed in requirements)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    cp = coldplate_snapshot(A, ss)
    verdict, cls, _ = operating_verdict(A, ss)
    chip = cp.get("Tchip_C", np.nan)
    chf = cp.get("CHF_margin", np.nan)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 16 * mm
    y = H - margin

    def text(x, y, value, size=10, color=colors.HexColor("#0F172A"), bold=False):
        c.setFillColor(color)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, str(value))

    def box(x, y, w, h, title, value, sub=""):
        c.setStrokeColor(colors.HexColor("#CBD5E1")); c.setFillColor(colors.white)
        c.roundRect(x, y, w, h, 7, stroke=1, fill=1)
        text(x+8, y+h-14, title.upper(), 7, colors.HexColor("#64748B"), True)
        text(x+8, y+h-34, value, 15, colors.HexColor("#0F172A"), True)
        if sub:
            text(x+8, y+9, sub, 7, colors.HexColor("#64748B"))

    text(margin, y, "ADAMS one-page design brief", 8, colors.HexColor("#64748B"), True)
    y -= 18
    text(margin, y, "Two-phase rack cooling concept", 22, colors.HexColor("#0F172A"), True)
    pill_color = {"safe":"#16A34A", "warn":"#D97706", "danger":"#DC2626"}[cls]
    c.setStrokeColor(colors.HexColor(pill_color)); c.roundRect(W-margin-115, y-3, 115, 18, 9, stroke=1, fill=0)
    text(W-margin-105, y+2, verdict, 8, colors.HexColor(pill_color), True)
    y -= 44

    card_w = (W - 2*margin - 3*6*mm) / 4
    vals = [
        ("IT load", f"{A.Q_rack_kW:.0f} kW", f"{A.n_chips} chips"),
        ("Refrigerant", A.fluid, f"{ss['Pevap_bar']:.1f}/{ss['Pcond_bar']:.1f} bar"),
        ("Full PUE", f"{ss['PUE_full']:.3f}", f"loop {ss['pPUE_loop']:.3f}"),
        ("Chip / CHF", f"{chip:.1f} °C", f"CHF {chf:.1f}x"),
    ]
    for i,(t,v,sub) in enumerate(vals):
        box(margin+i*(card_w+6*mm), y-48, card_w, 48, t, v, sub)
    y -= 75

    # flow diagram
    text(margin, y, "Process flow", 13, colors.HexColor("#0F172A"), True); y -= 12
    def flow_box(x, yb, w, h, label, fill):
        c.setStrokeColor(colors.HexColor("#CBD5E1")); c.setFillColor(colors.HexColor(fill))
        c.roundRect(x, yb, w, h, 6, stroke=1, fill=1)
        text(x+6, yb+h/2-3, label, 8, colors.HexColor("#0F172A"), True)
    def arrow(x1,y1,x2,y2,col="#0EA5E9"):
        c.setStrokeColor(colors.HexColor(col)); c.setLineWidth(1.6)
        c.line(x1,y1,x2,y2); c.circle(x2,y2,1.6,stroke=1,fill=1)
    fy = y-52
    flow_box(margin, fy, 80, 38, "Cold plate", "#E0F2FE")
    flow_box(margin+115, fy, 90, 38, "Condenser", "#FEE2E2")
    flow_box(margin+245, fy, 90, 38, "Water / reuse", "#ECFDF5")
    flow_box(margin+375, fy, 80, 38, "Pump + reservoir", "#FEF3C7")
    arrow(margin+80, fy+26, margin+115, fy+26, "#DC2626")
    arrow(margin+205, fy+26, margin+245, fy+26, "#DC2626")
    arrow(margin+375, fy+12, margin+80, fy+12, "#0EA5E9")
    text(margin, fy-15, f"Refrigerant {ss['mdot']:.3f} kg/s · Condenser duty {ss['Qcond_kW']:.0f} kW · Water {ss['Tw_in']:.0f}->{ss['Tw_out']:.0f} °C", 8, colors.HexColor("#64748B"))
    y = fy - 42

    # bar chart summary
    text(margin, y, "Key chart", 13, colors.HexColor("#0F172A"), True); y -= 8
    chart_x, chart_y, chart_w, chart_h = margin, y-78, 230, 70
    metrics = [("PUE", ss["PUE_full"], 1.6, "#16A34A"), ("Pump kW", ss["Wpump_W"]/1000, 10, "#0EA5E9"), ("CHF", chf, 6, "#D97706")]
    for i,(lab,val,maxv,col) in enumerate(metrics):
        yy = chart_y + chart_h - 18 - i*20
        text(chart_x, yy+3, lab, 8, colors.HexColor("#64748B"), True)
        c.setFillColor(colors.HexColor("#E2E8F0")); c.rect(chart_x+55, yy, chart_w-70, 9, fill=1, stroke=0)
        c.setFillColor(colors.HexColor(col)); c.rect(chart_x+55, yy, max(2, min(chart_w-70, (val/maxv)*(chart_w-70))), 9, fill=1, stroke=0)
        text(chart_x+chart_w-10, yy+2, f"{val:.2f}", 7, colors.HexColor("#0F172A"), True)

    # optional images
    if image_records:
        ix = margin + 270
        iy = y-82
        text(ix, y, "Supporting image", 13, colors.HexColor("#0F172A"), True)
        try:
            img = ImageReader(io.BytesIO(image_records[0]["bytes"]))
            c.drawImage(img, ix, iy, 150, 80, preserveAspectRatio=True, anchor="nw")
            text(ix, iy-10, image_records[0]["name"][:52], 7, colors.HexColor("#64748B"))
        except Exception:
            text(ix, iy, "Image could not be embedded.", 8, colors.HexColor("#64748B"))

    y = chart_y - 35
    text(margin, y, "Recommended next checks", 12, colors.HexColor("#0F172A"), True); y -= 13
    for line in [
        "Confirm cold-plate geometry and supplier HTC/CHF limits.",
        "Confirm condenser UA, pump curve/NPSH, valve Cv, and refrigerant charge.",
        "Confirm relief basis, leak detection, fail-safe positions, and PLC interlocks.",
    ]:
        text(margin+8, y, u"• " + line, 8, colors.HexColor("#334155")); y -= 11

    c.showPage(); c.save(); buf.seek(0)
    return buf.getvalue()


def tab_report_mode(A, ss):
    section_intro(
        "Guided report mode",
        "Generate a clean one-page brief from the current design",
        "This turns the exploratory model into a printable technical summary with hero numbers, schematic summary, operating verdict, and economic screen."
    )
    c1, c2, c3 = st.columns(3)
    show_flow = c1.checkbox("Show process flow chart", value=True)
    show_pue = c2.checkbox("Show PUE gauge", value=True)
    show_power = c3.checkbox("Show auxiliary-power chart", value=True)
    uploads = st.file_uploader("Add supporting images to the report", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    image_records = encode_uploaded_images(uploads)

    report_html = make_report_html(A, ss, image_records=image_records)
    st.markdown(report_html, unsafe_allow_html=True)

    if show_flow or show_pue or show_power:
        st.markdown("### Report visuals")
        cols = st.columns(sum([show_flow, show_pue, show_power]))
        idx = 0
        if show_flow:
            with cols[idx]:
                safe_plotly_chart(process_flow_figure(A, ss), use_container_width=True)
            idx += 1
        if show_pue:
            with cols[idx]:
                safe_plotly_chart(pue_gauge(ss), use_container_width=True)
            idx += 1
        if show_power:
            with cols[idx]:
                power = pd.DataFrame({"Item":["Refrig pump","Water pump","Chiller","Fans"],
                                      "kW":[ss["Wpump_W"]/1000, ss["W_waterpump_W"]/1000, ss["W_chiller_W"]/1000, ss["W_fans_W"]/1000]})
                fig = go.Figure(go.Bar(x=power["Item"], y=power["kW"], marker_color=[THEME["accent"], THEME["safe"], THEME["warn"], THEME["muted"]]))
                fig.update_layout(title="Auxiliary-power chart", yaxis_title="kW", height=330)
                safe_plotly_chart(fig, use_container_width=True)

    standalone = make_report_standalone_html(A, ss, image_records=image_records, include_charts=(show_flow or show_pue))
    d1, d2 = st.columns(2)
    d1.download_button("Download HTML brief", standalone.encode("utf-8"),
                       "ADAMS_one_page_design_brief.html", "text/html")
    try:
        pdf_bytes = make_report_pdf_bytes(A, ss, image_records=image_records)
        d2.download_button("Download PDF brief", pdf_bytes,
                           "ADAMS_one_page_design_brief.pdf", "application/pdf")
    except Exception as ex:
        d2.info("PDF export needs `reportlab`. It is now listed in requirements.txt; run `pip install -r requirements.txt` and the PDF button will appear.")

def tab_reference(A, ss):
    section_intro(
        "Reference",
        "Controls, safety, and design-improvement checklist",
        "A concise technical reference for the architecture, PLC safeguards, and practical upgrades that make the concept more reliable."
    )
    st.markdown("##### Visual and controls standards applied")
    c1, c2, c3 = st.columns(3)
    c1.markdown("<div class='journey-card'><b>One design language</b><br><span class='muted'>A global light theme and Plotly template are applied across every journey.</span></div>", unsafe_allow_html=True)
    c2.markdown("<div class='journey-card'><b>Semantic safety colors</b><br><span class='muted'>Green = safe, amber = warning, red = danger for temperatures, PUE, CHF, alarms, and trips.</span></div>", unsafe_allow_html=True)
    c3.markdown("<div class='journey-card'><b>Product micro-detail</b><br><span class='muted'>Line icons, tabular numbers, muted units, and generous spacing improve scanning speed.</span></div>", unsafe_allow_html=True)

    improvements = pd.DataFrame([
        ("Control architecture", "Keep PLC deterministic; let predictive control propose setpoints only", "High"),
        ("Pumping", "Add N+1 pump configuration with automatic changeover and check valve", "High"),
        ("Instrumentation", "Add cold-plate differential pressure, refrigerant flow meter, and redundant chip temperature sensors", "High"),
        ("Inventory", "Use level transmitter plus independent low-low switch and validated V2 make-up/bleed logic", "High"),
        ("Pressure protection", "Add relief valve / rupture disk and safe vent routing based on final refrigerant and MAWP", "High"),
        ("Cleanliness", "Add compatible filter/dryer or strainer and commissioning flush procedure", "Medium"),
        ("Leak management", "Add rack and underfloor leak detection tied to isolation and alarm logic", "High"),
        ("Water side", "Add condenser bypass and anti-short-cycling logic for chiller assist", "Medium"),
        ("Heat reuse", "Validate useful heat temperature before three-way routing", "Medium"),
        ("Digital", "Add SCADA historian, commissioning modes, cybersecurity controls, and role-based access", "Medium"),
    ], columns=["Area", "Recommended upgrade", "Priority"])
    st.dataframe(improvements, use_container_width=True, hide_index=True)

    st.markdown("##### PLC state-machine reference")
    states = pd.DataFrame([
        ("OFF", "Plant stopped; safe outputs"),
        ("PRECHECK", "Validate permissives, sensors, level, pressure, flow availability"),
        ("STARTUP", "Start pump, establish flow, stabilize pressure and reservoir level"),
        ("NORMAL_FREE_COOLING", "Operate without chiller when water inlet and condensing pressure are acceptable"),
        ("NORMAL_HEAT_REUSE", "Route useful heat when demand exists and outlet temperature is adequate"),
        ("NORMAL_CHILLER_ASSIST", "Enable chiller when heat sink temperature or condensing pressure is too high"),
        ("WARNING", "Hold safe operating envelope and alert operator"),
        ("TRIP", "Stop/isolate equipment on critical limit"),
        ("SHUTDOWN", "Controlled ramp-down sequence"),
    ], columns=["State", "Purpose"])
    st.dataframe(states, use_container_width=True, hide_index=True)


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main():
    st.markdown(
        f"<div class='app-title'><div class='logo-mark'>{svg_icon('shield')}</div>"
        "<div><h1>ADAMS</h1>"
        "<p>Advanced Data-center Adaptive Multiphase System · engineering design studio</p>"
        "</div></div>", unsafe_allow_html=True)

    A = sidebar_assumptions()

    # ---- sanity checks (surfaced to the user) ----
    warns, errs = core.sanity_check(A)
    for e in errs:
        st.error("⚠️ " + e)
    if errs:
        st.stop()
    for w in warns:
        st.warning(w)

    ss = core.steady_state(A)
    if not ss.get("ok"):
        st.error(f"Operating point infeasible for {A.fluid}: {ss.get('note')}. "
                 "Try a different fluid or lower the condensing temperature.")
        st.stop()

    tabs = st.tabs([
        "Command Center", "Design a System", "Stress-test It", "Justify It",
        "Compare Scenarios", "Report Mode", "Reference"
    ])
    with tabs[0]:
        tab_command_center(A, ss)
    with tabs[1]:
        tab_design_system(A, ss)
    with tabs[2]:
        tab_stress_test(A)
    with tabs[3]:
        tab_justify_it(A, ss)
    with tabs[4]:
        tab_scenario_comparison(A, ss)
    with tabs[5]:
        tab_report_mode(A, ss)
    with tabs[6]:
        tab_reference(A, ss)


if __name__ == "__main__":
    main()

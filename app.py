"""
Pitch-ready Streamlit app: Waste-Heat-Driven Absorption Chiller
================================================================

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

This file keeps the existing engineering calculation layer and redesigns only the
Streamlit experience: modern pitch dashboard, CSS animations, cleaner navigation,
manual heavy calculations, cached scenario runs, and export support.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src.dependencies import COOLPROP_AVAILABLE, COOLPROP_IMPORT_ERROR, TESPY_AVAILABLE, TESPY_IMPORT_ERROR
from src.utils.tables import dataframe_for_display, style_numeric_table, usd
from src.models.steam_case import steam_waste_heat_to_abs_chiller
from src.models.gas_turbine import gt_exhaust_to_abs_chiller
from src.models.air_chiller import air_abs_chiller
from src.models.brayton import ideal_brayton
from src.analysis.sensitivity import (
    air_ambient_sensitivity,
    air_chilled_supply_sensitivity,
    air_hot_air_sensitivity,
    run_gt_sensitivity,
    run_steam_sensitivity,
)
from src.visualization.charts import (
    air_system_diagram,
    base_bar_chart,
    brayton_screening_chart,
    plot_air_sensitivity,
    sensitivity_chart,
)
from src.export.excel import make_excel_bytes


# ============================================================
# PAGE SETUP
# ============================================================
st.set_page_config(
    page_title="Waste Heat Cooling | Pitch Dashboard",
    page_icon="♨️",
    layout="wide",
    initial_sidebar_state="expanded",
)

plt.rcParams["figure.figsize"] = (11, 5.5)
plt.rcParams["font.size"] = 11
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25


# ============================================================
# DESIGN SYSTEM
# ============================================================
def inject_design_system() -> None:
    """Inject a modern Streamlit visual layer with lightweight CSS animation."""
    st.markdown(
        """
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

            :root {
                --bg-0: #eef4fb;
                --bg-1: #f8fafc;
                --ink: #0f172a;
                --muted: #64748b;
                --card: rgba(255, 255, 255, 0.86);
                --line: rgba(148, 163, 184, 0.22);
                --blue: #2563eb;
                --cyan: #06b6d4;
                --green: #10b981;
                --amber: #f59e0b;
                --red: #ef4444;
                --shadow: 0 18px 45px rgba(15, 23, 42, 0.09);
            }

            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif;
            }

            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 28rem),
                    radial-gradient(circle at 70% 20%, rgba(6, 182, 212, 0.10), transparent 24rem),
                    linear-gradient(135deg, var(--bg-1) 0%, var(--bg-0) 100%);
                color: var(--ink);
            }

            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #07111f 0%, #0f172a 55%, #111827 100%);
                border-right: 1px solid rgba(255,255,255,0.08);
            }

            [data-testid="stSidebar"] * {
                color: rgba(255,255,255,0.92);
            }

            [data-testid="stSidebar"] .stNumberInput label,
            [data-testid="stSidebar"] .stSlider label,
            [data-testid="stSidebar"] .stSelectbox label,
            [data-testid="stSidebar"] .stRadio label,
            [data-testid="stSidebar"] .stToggle label {
                color: rgba(255,255,255,0.88) !important;
                font-weight: 600;
            }

            [data-testid="stSidebar"] section[data-testid="stSidebarUserContent"] {
                padding-top: 1.1rem;
            }

            .block-container {
                padding-top: 1.7rem;
                padding-bottom: 3.5rem;
                max-width: 1480px;
            }

            div[data-testid="stButton"] button {
                border-radius: 999px;
                border: 0;
                min-height: 2.85rem;
                font-weight: 700;
                box-shadow: 0 12px 28px rgba(37, 99, 235, 0.20);
                transition: transform 180ms ease, box-shadow 180ms ease;
            }

            div[data-testid="stButton"] button:hover {
                transform: translateY(-1px);
                box-shadow: 0 18px 32px rgba(37, 99, 235, 0.26);
            }

            .hero {
                position: relative;
                overflow: hidden;
                border-radius: 28px;
                padding: 34px 36px;
                color: white;
                background:
                    radial-gradient(circle at 86% 15%, rgba(6, 182, 212, 0.50), transparent 15rem),
                    linear-gradient(135deg, #07111f 0%, #172554 45%, #0f766e 100%);
                box-shadow: var(--shadow);
                animation: fadeUp 700ms ease both;
                margin-bottom: 1.2rem;
            }

            .hero:after {
                content: "";
                position: absolute;
                width: 360px;
                height: 360px;
                right: -120px;
                top: -140px;
                background: radial-gradient(circle, rgba(255,255,255,0.22), transparent 68%);
                animation: pulseGlow 6s ease-in-out infinite;
            }

            .hero .eyebrow {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 7px 13px;
                border-radius: 999px;
                background: rgba(255,255,255,0.12);
                border: 1px solid rgba(255,255,255,0.18);
                color: rgba(255,255,255,0.90);
                font-size: 0.78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                margin-bottom: 14px;
            }

            .hero h1 {
                position: relative;
                z-index: 1;
                font-size: clamp(2.0rem, 4vw, 4.2rem);
                line-height: 0.95;
                letter-spacing: -0.06em;
                margin: 0 0 14px 0;
                max-width: 970px;
            }

            .hero p {
                position: relative;
                z-index: 1;
                max-width: 820px;
                margin: 0;
                color: rgba(255,255,255,0.82);
                font-size: 1.02rem;
                line-height: 1.55;
            }

            .hero-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
                margin-top: 24px;
                position: relative;
                z-index: 1;
            }

            .hero-pill {
                border-radius: 18px;
                padding: 14px 16px;
                background: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.14);
                color: rgba(255,255,255,0.88);
                backdrop-filter: blur(12px);
                font-size: 0.92rem;
            }

            .hero-pill strong {
                display: block;
                color: white;
                font-size: 1rem;
                margin-bottom: 2px;
            }

            .metric-card {
                min-height: 150px;
                padding: 22px 22px 20px 22px;
                border: 1px solid var(--line);
                border-radius: 24px;
                background: var(--card);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
                transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
                animation: fadeUp 650ms ease both;
            }

            .metric-card:hover {
                transform: translateY(-4px);
                border-color: rgba(37, 99, 235, 0.30);
                box-shadow: 0 24px 52px rgba(15, 23, 42, 0.13);
            }

            .metric-label {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 10px;
                color: var(--muted);
                font-weight: 700;
                font-size: 0.80rem;
                text-transform: uppercase;
                letter-spacing: 0.07em;
                margin-bottom: 10px;
            }

            .metric-icon {
                height: 34px;
                min-width: 34px;
                border-radius: 12px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, rgba(37, 99, 235, 0.14), rgba(6, 182, 212, 0.12));
                color: var(--blue);
                font-size: 1.08rem;
            }

            .metric-value {
                color: var(--ink);
                font-size: clamp(1.55rem, 2.6vw, 2.35rem);
                font-weight: 800;
                letter-spacing: -0.05em;
                line-height: 1.0;
                margin-bottom: 8px;
            }

            .metric-caption {
                color: var(--muted);
                line-height: 1.42;
                font-size: 0.90rem;
            }

            .panel {
                border: 1px solid var(--line);
                border-radius: 24px;
                padding: 22px;
                background: rgba(255,255,255,0.78);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
                animation: fadeUp 700ms ease both;
                margin: 8px 0 16px 0;
            }

            .section-kicker {
                color: var(--blue);
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 0.08em;
                font-size: 0.78rem;
                margin-bottom: 4px;
            }

            .section-title {
                color: var(--ink);
                font-weight: 800;
                font-size: 1.45rem;
                letter-spacing: -0.03em;
                margin-bottom: 4px;
            }

            .section-text {
                color: var(--muted);
                line-height: 1.55;
                margin-bottom: 0.6rem;
            }

            .flow-lane {
                position: relative;
                height: 74px;
                border-radius: 22px;
                background:
                    linear-gradient(90deg, rgba(245, 158, 11, 0.15), rgba(16, 185, 129, 0.14), rgba(37, 99, 235, 0.13));
                border: 1px solid var(--line);
                overflow: hidden;
                margin-top: 10px;
            }

            .flow-lane:before {
                content: "Waste heat   →   Absorption chiller   →   Avoided compressor power   →   Lower CO₂";
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #0f172a;
                font-weight: 800;
                letter-spacing: -0.01em;
            }

            .flow-dot {
                position: absolute;
                top: 22px;
                left: -45px;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                background: linear-gradient(135deg, #f59e0b, #06b6d4);
                box-shadow: 0 0 0 10px rgba(6, 182, 212, 0.11), 0 0 28px rgba(6, 182, 212, 0.45);
                animation: heatFlow 4.2s linear infinite;
            }

            .status-row {
                display: flex;
                flex-wrap: wrap;
                gap: 9px;
                margin: 10px 0 2px 0;
            }

            .chip {
                display: inline-flex;
                align-items: center;
                gap: 7px;
                border-radius: 999px;
                padding: 7px 11px;
                font-size: 0.82rem;
                font-weight: 700;
                border: 1px solid var(--line);
                background: rgba(255,255,255,0.72);
                color: #334155;
            }

            .chip-ok { color: #047857; background: rgba(16,185,129,0.10); border-color: rgba(16,185,129,0.22); }
            .chip-warn { color: #b45309; background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.25); }
            .chip-bad { color: #b91c1c; background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.22); }

            .small-note {
                color: var(--muted);
                font-size: 0.90rem;
                line-height: 1.5;
            }

            .case-card {
                border-radius: 20px;
                padding: 18px 18px 16px 18px;
                background: rgba(255,255,255,0.74);
                border: 1px solid var(--line);
                box-shadow: 0 12px 30px rgba(15, 23, 42, 0.07);
                min-height: 150px;
            }

            .case-card h3 {
                font-size: 1.1rem;
                margin: 0 0 8px 0;
                letter-spacing: -0.02em;
            }

            .case-card p {
                color: var(--muted);
                margin: 0;
                line-height: 1.5;
                font-size: 0.93rem;
            }

            .footer-note {
                border-top: 1px solid var(--line);
                margin-top: 28px;
                padding-top: 15px;
                color: var(--muted);
                font-size: 0.85rem;
            }

            @keyframes fadeUp {
                from { opacity: 0; transform: translateY(12px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @keyframes heatFlow {
                0% { left: -45px; opacity: 0; }
                8% { opacity: 1; }
                88% { opacity: 1; }
                100% { left: calc(100% + 45px); opacity: 0; }
            }

            @keyframes pulseGlow {
                0%, 100% { transform: scale(1); opacity: 0.65; }
                50% { transform: scale(1.12); opacity: 0.92; }
            }

            @media (max-width: 900px) {
                .hero-grid { grid-template-columns: 1fr; }
                .flow-lane:before { font-size: 0.82rem; padding: 0 14px; text-align: center; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, caption: str, icon: str = "↗") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label"><span>{label}</span><span class="metric-icon">{icon}</span></div>
            <div class="metric-value">{value}</div>
            <div class="metric-caption">{caption}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(kicker: str, title: str, text: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-kicker">{kicker}</div>
        <div class="section-title">{title}</div>
        <div class="section-text">{text}</div>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, ok: bool, detail: str = "") -> str:
    css = "chip-ok" if ok else "chip-bad"
    symbol = "●" if ok else "▲"
    suffix = f" — {detail}" if detail else ""
    return f'<span class="chip {css}">{symbol} {label}{suffix}</span>'


def render_status_chips() -> None:
    chips = [
        status_chip("CoolProp", COOLPROP_AVAILABLE, "steam + humid air" if COOLPROP_AVAILABLE else "missing"),
        status_chip("TESPy", TESPY_AVAILABLE, "GT model" if TESPY_AVAILABLE else "missing"),
        '<span class="chip chip-ok">● Excel export ready</span>',
    ]
    st.markdown(f'<div class="status-row">{"".join(chips)}</div>', unsafe_allow_html=True)


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="eyebrow">Pitch mode · Waste-heat monetization</div>
            <h1>Convert rejected heat into bankable cooling capacity.</h1>
            <p>
                A cleaner executive dashboard for steam waste heat, gas-turbine exhaust, and air-driven absorption cooling.
                The interface leads with commercial impact, then lets technical reviewers drill into assumptions, sensitivity,
                and exportable evidence.
            </p>
            <div class="hero-grid">
                <div class="hero-pill"><strong>1 · Value first</strong>Cooling, avoided power cost, and CO₂ benefit are visible immediately.</div>
                <div class="hero-pill"><strong>2 · Faster pitch flow</strong>Heavy sensitivity runs only when requested; base scenarios are cached.</div>
                <div class="hero-pill"><strong>3 · Modern motion</strong>Animated cards and heat-flow ribbon add polish without extra packages.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_flow_ribbon() -> None:
    st.markdown('<div class="flow-lane"><div class="flow-dot"></div></div>', unsafe_allow_html=True)


def safe_sum(results: List[Dict[str, Any]], key: str) -> float:
    return float(sum(float(r.get(key, 0.0) or 0.0) for r in results))


def fmt_mw(value: float) -> str:
    return f"{value:,.2f} MWc"


def fmt_tr(value: float) -> str:
    return f"{value:,.0f} TR"


def fmt_usd_short(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M/y"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}k/y"
    return usd(value)


def fmt_tonnes(value: float) -> str:
    return f"{value:,.0f} t/y"


# ============================================================
# INPUTS
# ============================================================
def build_sidebar_inputs() -> Tuple[str, bool, bool, Dict[str, Any]]:
    with st.sidebar:
        st.markdown("### Waste Heat Cooling")
        st.caption("Pitch dashboard · engineering model")

        page = st.radio(
            "Navigate",
            [
                "Pitch Dashboard",
                "Source Analysis",
                "Sensitivity Lab",
                "Air Cooling",
                "Brayton Map",
                "Export",
            ],
            index=0,
        )

        st.divider()
        run_model = st.button("Run / refresh model", type="primary", use_container_width=True)
        auto_refresh = st.toggle("Auto-refresh when assumptions change", value=False)

        with st.expander("Commercial assumptions", expanded=True):
            operating_hours_per_year = st.number_input("Operating hours per year", 1000, 8760, 8000, 100)
            grid_emission_factor_kgCO2_per_MWh = st.number_input("Grid emission factor (kgCO₂/MWh)", 0, 1200, 400, 10)
            electricity_price_USD_per_MWh = st.number_input("Electricity price (USD/MWh)", 0, 1000, 120, 5)
            electric_chiller_COP_reference = st.number_input("Reference electric chiller COP", 1.0, 12.0, 5.5, 0.1)

        with st.expander("Absorption chiller", expanded=True):
            effect = st.selectbox("Absorption chiller effect", ["single", "double"], index=0)
            T_chilled_water_supply_C = st.number_input("Chilled-water supply equivalent (°C)", -2.0, 20.0, 7.0, 0.5)
            T_cooling_water_C = st.number_input("Cooling-water temperature (°C)", 15.0, 50.0, 30.0, 0.5)
            generator_approach_C = st.number_input("Generator/source approach (°C)", 0.0, 40.0, 8.0, 0.5)

        with st.expander("Steam waste heat source", expanded=False):
            steam_m_kg_s = st.number_input("Steam flow (kg/s)", 0.1, 100.0, 5.0, 0.1)
            steam_pressure_bar = st.number_input("Steam pressure (bar)", 0.5, 80.0, 3.0, 0.1)
            steam_quality = st.slider("Steam quality", 0.70, 1.00, 1.00, 0.01)
            steam_condensate_return_C = st.number_input("Condensate return temperature (°C)", 30.0, 180.0, 85.0, 1.0)
            steam_heat_recovery_eff = st.slider("Steam heat recovery efficiency", 0.10, 1.00, 0.88, 0.01)

        with st.expander("GT exhaust source", expanded=False):
            gt_air_m_kg_s = st.number_input("GT air flow (kg/s)", 1.0, 1000.0, 86.0, 1.0)
            gt_pressure_ratio = st.number_input("Compressor pressure ratio", 2.0, 60.0, 19.0, 0.5)
            gt_TIT_C = st.number_input("Turbine inlet temperature (°C)", 600.0, 1800.0, 1188.0, 10.0)
            gt_eta_comp = st.slider("Compressor isentropic efficiency", 0.50, 0.98, 0.88, 0.01)
            gt_eta_turb = st.slider("Turbine isentropic efficiency", 0.50, 0.98, 0.90, 0.01)
            gt_stack_temp_C = st.number_input("Stack temperature after heat recovery (°C)", 70.0, 300.0, 120.0, 5.0)
            gt_exhaust_cp_kJ_kgK = st.number_input("Exhaust gas cp (kJ/kg.K)", 0.90, 1.30, 1.10, 0.01)
            gt_heat_recovery_eff = st.slider("GT exhaust heat recovery efficiency", 0.10, 1.00, 0.75, 0.01)

        with st.expander("Dependency status", expanded=False):
            st.write("CoolProp:", "available" if COOLPROP_AVAILABLE else f"missing — {COOLPROP_IMPORT_ERROR}")
            st.write("TESPy:", "available" if TESPY_AVAILABLE else f"missing — {TESPY_IMPORT_ERROR}")
            st.code("pip install streamlit tespy CoolProp numpy pandas matplotlib openpyxl")

    project = {
        "operating_hours_per_year": float(operating_hours_per_year),
        "grid_emission_factor_kgCO2_per_MWh": float(grid_emission_factor_kgCO2_per_MWh),
        "electricity_price_USD_per_MWh": float(electricity_price_USD_per_MWh),
        "electric_chiller_COP_reference": float(electric_chiller_COP_reference),
        "effect": effect,
        "T_chilled_water_supply_C": float(T_chilled_water_supply_C),
        "T_cooling_water_C": float(T_cooling_water_C),
        "generator_approach_C": float(generator_approach_C),
        "steam_m_kg_s": float(steam_m_kg_s),
        "steam_pressure_bar": float(steam_pressure_bar),
        "steam_quality": float(steam_quality),
        "steam_condensate_return_C": float(steam_condensate_return_C),
        "steam_heat_recovery_eff": float(steam_heat_recovery_eff),
        "gt_air_m_kg_s": float(gt_air_m_kg_s),
        "gt_pressure_ratio": float(gt_pressure_ratio),
        "gt_TIT_C": float(gt_TIT_C),
        "gt_eta_comp": float(gt_eta_comp),
        "gt_eta_turb": float(gt_eta_turb),
        "gt_stack_temp_C": float(gt_stack_temp_C),
        "gt_exhaust_cp_kJ_kgK": float(gt_exhaust_cp_kJ_kgK),
        "gt_heat_recovery_eff": float(gt_heat_recovery_eff),
    }
    return page, run_model, auto_refresh, project


# ============================================================
# CALCULATION WRAPPERS
# ============================================================
@st.cache_data(show_spinner=False)
def compute_base_cases(project: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        steam_case = steam_waste_heat_to_abs_chiller(
            m_steam_kg_s=project["steam_m_kg_s"],
            P_steam_bar=project["steam_pressure_bar"],
            steam_quality=project["steam_quality"],
            T_condensate_return_C=project["steam_condensate_return_C"],
            heat_recovery_eff=project["steam_heat_recovery_eff"],
            generator_approach_C=project["generator_approach_C"],
            effect=project["effect"],
            T_cooling_water_C=project["T_cooling_water_C"],
            T_chilled_water_C=project["T_chilled_water_supply_C"],
            operating_hours=project["operating_hours_per_year"],
            electric_chiller_COP=project["electric_chiller_COP_reference"],
            electricity_price_USD_per_MWh=project["electricity_price_USD_per_MWh"],
            grid_emission_factor_kgCO2_per_MWh=project["grid_emission_factor_kgCO2_per_MWh"],
        )
        results.append(steam_case)
    except Exception as exc:  # pragma: no cover - depends on optional scientific packages
        errors.append(f"Steam case failed: {exc}")

    try:
        gt_case = gt_exhaust_to_abs_chiller(
            m_air=project["gt_air_m_kg_s"],
            pr_comp=project["gt_pressure_ratio"],
            T_turbine_inlet=project["gt_TIT_C"],
            eta_s_comp=project["gt_eta_comp"],
            eta_s_turb=project["gt_eta_turb"],
            stack_temp_C=project["gt_stack_temp_C"],
            exhaust_cp_kJ_kgK=project["gt_exhaust_cp_kJ_kgK"],
            heat_recovery_eff=project["gt_heat_recovery_eff"],
            generator_approach_C=project["generator_approach_C"],
            effect=project["effect"],
            T_cooling_water_C=project["T_cooling_water_C"],
            T_chilled_water_C=project["T_chilled_water_supply_C"],
            operating_hours=project["operating_hours_per_year"],
            electric_chiller_COP=project["electric_chiller_COP_reference"],
            electricity_price_USD_per_MWh=project["electricity_price_USD_per_MWh"],
            grid_emission_factor_kgCO2_per_MWh=project["grid_emission_factor_kgCO2_per_MWh"],
        )
        results.append(gt_case)
    except Exception as exc:  # pragma: no cover - depends on optional scientific packages
        errors.append(f"GT exhaust case failed: {exc}")

    return results, errors


@st.cache_data(show_spinner=False)
def compute_steam_sensitivity_cached(project: Dict[str, Any]) -> pd.DataFrame:
    return run_steam_sensitivity(project)


@st.cache_data(show_spinner=False)
def compute_gt_sensitivity_cached(project: Dict[str, Any]) -> pd.DataFrame:
    return run_gt_sensitivity(project)


@st.cache_data(show_spinner=False)
def compute_air_case_cached(air_case_input: Dict[str, Any]) -> Dict[str, Any]:
    return air_abs_chiller(**air_case_input)


def get_base_results(project: Dict[str, Any], run_model: bool, auto_refresh: bool) -> Tuple[List[Dict[str, Any]], List[str]]:
    signature = json.dumps(project, sort_keys=True)
    needs_first_run = "base_results" not in st.session_state
    assumptions_changed = st.session_state.get("project_signature") != signature

    if run_model or needs_first_run or (auto_refresh and assumptions_changed):
        with st.spinner("Running base steam and GT scenarios..."):
            results, errors = compute_base_cases(project)
        st.session_state["base_results"] = results
        st.session_state["base_errors"] = errors
        st.session_state["project_signature"] = signature
    elif assumptions_changed:
        st.info("Assumptions changed. Press **Run / refresh model** to update the dashboard, or enable auto-refresh.")

    return st.session_state.get("base_results", []), st.session_state.get("base_errors", [])


def collect_warnings(results: List[Dict[str, Any]]) -> List[str]:
    warnings: List[str] = []
    for result in results:
        for warning in result.get("warnings", []) or []:
            warnings.append(f"{result.get('case_name', 'Case')}: {warning}")
    return warnings


def make_base_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    return dataframe_for_display(results) if results else pd.DataFrame()


# ============================================================
# PAGES
# ============================================================
def pitch_dashboard(project: Dict[str, Any], run_model: bool, auto_refresh: bool) -> None:
    render_hero()
    render_status_chips()

    if not COOLPROP_AVAILABLE:
        st.warning("CoolProp is missing. Steam and humid-air calculations need CoolProp installed.")
    if not TESPY_AVAILABLE:
        st.warning("TESPy is missing. The GT exhaust case and GT sensitivity need TESPy installed.")

    results, errors = get_base_results(project, run_model, auto_refresh)

    if errors:
        for error in errors:
            st.error(error)

    if not results:
        st.info("No base scenario has produced results yet. Check dependencies, then run the model from the sidebar.")
        return

    total_cooling = safe_sum(results, "Q_cooling_MW")
    total_tr = safe_sum(results, "cooling_TR")
    total_value = safe_sum(results, "annual_savings_USD")
    total_co2 = safe_sum(results, "annual_CO2_t")
    best_case = max(results, key=lambda r: float(r.get("Q_cooling_MW", 0.0) or 0.0))

    st.write("")
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        metric_card("Total cooling", fmt_mw(total_cooling), "Combined absorption cooling capacity from active sources.", "❄️")
    with k2:
        metric_card("Cooling scale", fmt_tr(total_tr), "Equivalent refrigeration capacity for pitch-level sizing.", "📏")
    with k3:
        metric_card("Annual value", fmt_usd_short(total_value), "Avoided electric chiller power cost at current assumptions.", "💵")
    with k4:
        metric_card("CO₂ reduction", fmt_tonnes(total_co2), "Annual emissions reduction from displaced electricity.", "🌱")

    st.markdown('<div class="panel">', unsafe_allow_html=True)
    section_header(
        "Executive flow",
        "The investment logic is now visible in one line",
        "Rejected heat is converted into useful cooling, which reduces compressor electricity demand, operating cost, and grid-linked CO₂ emissions.",
    )
    render_flow_ribbon()
    st.markdown('</div>', unsafe_allow_html=True)

    left, right = st.columns([1.25, 0.75], gap="large")
    with left:
        section_header("Portfolio view", "Source comparison", "Capacity and annual value by heat source.")
        c1, c2 = st.columns(2)
        with c1:
            st.pyplot(
                base_bar_chart(results, "Q_cooling_MW", "Cooling capacity (MWc)", "Absorption Cooling Capacity", "{:.1f} MWc"),
                clear_figure=True,
            )
        with c2:
            annual_musd_results = [dict(r, annual_savings_musd=float(r.get("annual_savings_USD", 0.0) or 0.0) / 1e6) for r in results]
            st.pyplot(
                base_bar_chart(
                    annual_musd_results,
                    "annual_savings_musd",
                    "Annual avoided electricity value (million USD/year)",
                    "Annual Value",
                    "${:.2f}M/y",
                ),
                clear_figure=True,
            )

    with right:
        section_header("Lead source", best_case.get("case_name", "Best case"), "Highest cooling capacity under the current assumptions.")
        metric_card(
            "Lead capacity",
            fmt_mw(float(best_case.get("Q_cooling_MW", 0.0) or 0.0)),
            f"Annual value: {fmt_usd_short(float(best_case.get('annual_savings_USD', 0.0) or 0.0))}",
            "🏆",
        )
        st.markdown(
            """
            <div class="case-card">
                <h3>Pitch note</h3>
                <p>
                    Use this dashboard for the first 2 minutes. Keep detailed thermodynamic assumptions in the drill-down pages unless the audience asks for them.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    warnings = collect_warnings(results)
    if warnings:
        with st.expander("Model warnings"):
            for warning in warnings:
                st.warning(warning)

    with st.expander("Detailed base-case table"):
        base_df = make_base_dataframe(results)
        st.dataframe(style_numeric_table(base_df), use_container_width=True)


def source_analysis(project: Dict[str, Any], run_model: bool, auto_refresh: bool) -> None:
    section_header("Technical drill-down", "Source analysis", "A cleaner space for detailed comparison after the pitch dashboard has established the business value.")
    results, errors = get_base_results(project, run_model, auto_refresh)

    for error in errors:
        st.error(error)

    if not results:
        st.info("Run the model from the sidebar to populate source analysis.")
        return

    cols = st.columns(len(results) if len(results) <= 3 else 3)
    for idx, result in enumerate(results):
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="case-card">
                    <h3>{result.get('case_name', f'Case {idx + 1}')}</h3>
                    <p><strong>Cooling:</strong> {fmt_mw(float(result.get('Q_cooling_MW', 0.0) or 0.0))}</p>
                    <p><strong>TR:</strong> {fmt_tr(float(result.get('cooling_TR', 0.0) or 0.0))}</p>
                    <p><strong>Annual value:</strong> {fmt_usd_short(float(result.get('annual_savings_USD', 0.0) or 0.0))}</p>
                    <p><strong>CO₂:</strong> {fmt_tonnes(float(result.get('annual_CO2_t', 0.0) or 0.0))}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    base_df = make_base_dataframe(results)
    st.write("")
    st.dataframe(style_numeric_table(base_df), use_container_width=True)

    with st.expander("Raw result dictionaries"):
        st.json(results)


def sensitivity_lab(project: Dict[str, Any]) -> None:
    section_header(
        "Scenario testing",
        "Sensitivity lab",
        "Run sensitivities only when needed. This keeps the pitch interface fast while preserving the deeper engineering analysis.",
    )

    source = st.radio(
        "Select sensitivity set",
        ["Steam waste heat", "GT exhaust"],
        index=0,
        horizontal=True,
    )

    if source == "Steam waste heat":
        st.info("Sensitivity variables: steam flow, pressure, condensate return temperature, and heat recovery efficiency.")
        run = st.button("Run steam sensitivity", type="primary")
        if run:
            with st.spinner("Running steam sensitivity..."):
                st.session_state["steam_sens_df"] = compute_steam_sensitivity_cached(project)
        steam_sens_df = st.session_state.get("steam_sens_df")
        if steam_sens_df is not None and not steam_sens_df.empty:
            display_cols = [
                "sensitivity",
                "x",
                "Q_generator_MW",
                "T_generator_C",
                "COP_abs",
                "Q_cooling_MW",
                "cooling_TR",
                "annual_savings_USD",
            ]
            st.dataframe(steam_sens_df[[c for c in display_cols if c in steam_sens_df.columns]], use_container_width=True)
            for _, fig in sensitivity_chart(steam_sens_df, "Steam Case Sensitivity"):
                st.pyplot(fig, clear_figure=True)
    else:
        st.warning("GT sensitivity repeatedly solves TESPy networks. Run it when the audience wants deeper technical evidence.")
        run = st.button("Run GT sensitivity", type="primary")
        if run:
            with st.spinner("Running GT sensitivity cases..."):
                st.session_state["gt_sens_df"] = compute_gt_sensitivity_cached(project)
        gt_sens_df = st.session_state.get("gt_sens_df")
        if gt_sens_df is not None and not gt_sens_df.empty:
            display_cols = [
                "sensitivity",
                "x",
                "gt_net_power_MW",
                "gt_efficiency_pct",
                "gt_exhaust_T_C",
                "Q_generator_MW",
                "Q_cooling_MW",
                "cooling_TR",
                "annual_savings_USD",
            ]
            st.dataframe(gt_sens_df[[c for c in display_cols if c in gt_sens_df.columns]], use_container_width=True)
            for _, fig in sensitivity_chart(gt_sens_df, "GT Exhaust Case Sensitivity", include_gt_exhaust_temp=True):
                st.pyplot(fig, clear_figure=True)
            if "error" in gt_sens_df.columns and gt_sens_df["error"].notna().any():
                with st.expander("Failed TESPy points"):
                    st.dataframe(gt_sens_df[gt_sens_df["error"].notna()][["sensitivity", "x", "error"]], use_container_width=True)


def air_cooling_page() -> None:
    section_header(
        "Data-center option",
        "Air-driven absorption chiller",
        "A focused page for air-side cooling assumptions, outputs, diagram, and optional sensitivity charts.",
    )

    with st.form("air_chiller_inputs"):
        col1, col2, col3 = st.columns(3)
        with col1:
            air_Q_cool_kW = st.number_input("Cooling load (kW)", 100.0, 50000.0, 2000.0, 100.0)
            air_T_ambient = st.number_input("Ambient air temperature (°C)", -10.0, 55.0, 30.0, 1.0)
            air_RH = st.slider("Ambient relative humidity", 0.05, 1.00, 0.50, 0.01)
            air_effect = st.selectbox("Air chiller effect", ["single", "double"], index=0, key="air_effect")
        with col2:
            air_T_chill_supply = st.number_input("Chilled air supply temperature (°C)", 5.0, 30.0, 15.0, 1.0)
            air_T_chill_return = st.number_input("Chilled air return temperature (°C)", 5.0, 55.0, 30.0, 1.0)
            air_T_hot_in = st.number_input("Hot air inlet to generator (°C)", 40.0, 200.0, 85.0, 1.0)
            air_T_hot_out = st.number_input("Hot air outlet from generator (°C)", 20.0, 180.0, 65.0, 1.0)
        with col3:
            air_T_reject_out = st.number_input("Reject air outlet temperature (°C)", 15.0, 90.0, 45.0, 1.0)
            approach_chw = st.number_input("CHW/air approach (°C)", 0.0, 20.0, 8.0, 0.5)
            approach_hw = st.number_input("Hot-water/air approach (°C)", 0.0, 30.0, 10.0, 0.5)
            approach_cw = st.number_input("Cooling-water/air approach (°C)", 0.0, 20.0, 7.0, 0.5)

        submitted_air = st.form_submit_button("Run air chiller case", type="primary")

    air_case_input = {
        "Q_cool_kW": float(air_Q_cool_kW),
        "T_ambient_air": float(air_T_ambient),
        "RH_ambient": float(air_RH),
        "T_chill_supply": float(air_T_chill_supply),
        "T_chill_return": float(air_T_chill_return),
        "T_hot_air_in": float(air_T_hot_in),
        "T_hot_air_out": float(air_T_hot_out),
        "T_reject_air_out": float(air_T_reject_out),
        "effect": air_effect,
        "approach_chw": float(approach_chw),
        "approach_hw": float(approach_hw),
        "approach_cw": float(approach_cw),
        "case_name": "Interactive air-driven chiller case",
    }

    if submitted_air or "air_result" not in st.session_state:
        try:
            with st.spinner("Running air chiller calculation..."):
                st.session_state["air_result"] = compute_air_case_cached(air_case_input)
                st.session_state["air_case_input"] = air_case_input
        except Exception as exc:
            st.error(f"Air-driven chiller calculation failed: {exc}")
            return

    air_result = st.session_state.get("air_result")
    if not air_result:
        return

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Cooling output", f"{float(air_result['Q_cool_kW']):,.0f} kW", "Input cooling load served by absorption chiller.", "❄️")
    with c2:
        metric_card("Cooling scale", f"{float(air_result['Q_cool_TR']):,.0f} TR", "Refrigeration ton equivalent.", "📏")
    with c3:
        metric_card("COP", f"{float(air_result['COP']):.3f}", "Absorption cooling performance indicator.", "⚙️")
    with c4:
        metric_card("Heat input", f"{float(air_result['Q_gen_kW']):,.0f} kW", "Generator heat required for the case.", "♨️")

    air_case_df = pd.DataFrame([air_result])
    st.session_state["air_case_df"] = air_case_df

    summary_cols = [
        "Q_cool_kW",
        "Q_cool_TR",
        "Q_gen_kW",
        "Q_reject_kW",
        "Q_sensible_kW",
        "Q_latent_kW",
        "COP",
        "m_chill_air_kg_s",
        "V_chill_air_m3_h",
        "V_hot_air_m3_h",
        "V_rej_air_m3_h",
        "m_condensate_kg_h",
        "T_dp_ambient",
        "T_wb_ambient",
        "T_chw_internal",
        "T_hw_internal",
        "T_cw_internal",
    ]

    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        section_header("Outputs", "Air chiller summary table")
        st.dataframe(
            air_case_df[[c for c in summary_cols if c in air_case_df.columns]].T.rename(columns={0: "value"}),
            use_container_width=True,
        )
    with right:
        section_header("System view", "Air-side energy flow")
        st.pyplot(air_system_diagram(air_result), clear_figure=True)

    if air_result.get("warnings"):
        with st.expander("Air chiller warnings"):
            for warning in air_result["warnings"]:
                st.warning(warning)

    show_sensitivity = st.toggle("Show air-chiller sensitivity charts", value=False)
    if show_sensitivity:
        amb_df = air_ambient_sensitivity(st.session_state.get("air_case_input", air_case_input))
        hot_df = air_hot_air_sensitivity(st.session_state.get("air_case_input", air_case_input))
        chw_df = air_chilled_supply_sensitivity(st.session_state.get("air_case_input", air_case_input))

        col_a, col_b = st.columns(2)
        with col_a:
            st.pyplot(plot_air_sensitivity(amb_df, "Ambient air temperature (°C)", "COP", "COP vs Ambient Temperature"), clear_figure=True)
            st.pyplot(
                plot_air_sensitivity(hot_df, "Hot air inlet (°C)", "COP", "COP vs Hot Air Temperature", group="Ambient air temperature (°C)"),
                clear_figure=True,
            )
        with col_b:
            st.pyplot(plot_air_sensitivity(amb_df, "Ambient air temperature (°C)", "Heat input (kW)", "Heat Input vs Ambient Temperature"), clear_figure=True)
            st.pyplot(
                plot_air_sensitivity(
                    chw_df,
                    "Chilled air supply (°C)",
                    "Chilled air flow (m3/h)",
                    "Required Chilled Air Flow vs Supply Temperature",
                    group="Ambient air temperature (°C)",
                ),
                clear_figure=True,
            )


def brayton_page() -> None:
    section_header(
        "Fast screening",
        "Ideal Brayton map",
        "A quick pressure-ratio and turbine-inlet-temperature screening view. Use the TESPy GT model for detailed project discussion.",
    )
    st.pyplot(brayton_screening_chart(), clear_figure=True)

    with st.expander("Single-point ideal Brayton calculation", expanded=True):
        b_col1, b_col2, b_col3 = st.columns(3)
        b_T1 = b_col1.number_input("Compressor inlet T1 (K)", 250.0, 350.0, 300.0, 1.0)
        b_pr = b_col2.number_input("Pressure ratio", 2.0, 60.0, 20.0, 1.0)
        b_T3 = b_col3.number_input("Turbine inlet T3 (K)", 900.0, 2100.0, 1500.0, 10.0)
        b = ideal_brayton(T1_K=b_T1, P_ratio=b_pr, T3_K=b_T3)
        st.json(b)


def export_page(project: Dict[str, Any], run_model: bool, auto_refresh: bool) -> None:
    section_header(
        "Decision pack",
        "Export results",
        "Generate the Excel workbook after running the dashboard and any required sensitivity cases.",
    )

    results, errors = get_base_results(project, run_model, auto_refresh)
    for error in errors:
        st.error(error)

    export_base_df = make_base_dataframe(results)
    export_steam_sens = st.session_state.get("steam_sens_df", pd.DataFrame())
    export_gt_sens = st.session_state.get("gt_sens_df", pd.DataFrame())
    export_air_df = st.session_state.get("air_case_df", pd.DataFrame())

    if not export_base_df.empty:
        st.dataframe(style_numeric_table(export_base_df), use_container_width=True)
    else:
        st.info("Run the model first to create exportable base-case results.")

    excel_bytes = make_excel_bytes(export_base_df, export_steam_sens, export_gt_sens, export_air_df)
    st.download_button(
        label="Download Excel results",
        data=excel_bytes,
        file_name="waste_heat_absorption_chiller_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.markdown(
        """
        <div class="footer-note">
            Deployment: <code>streamlit run app.py</code> · Dependencies: <code>pip install -r requirements.txt</code>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# MAIN
# ============================================================
def main() -> None:
    inject_design_system()
    page, run_model, auto_refresh, project = build_sidebar_inputs()

    if page == "Pitch Dashboard":
        pitch_dashboard(project, run_model, auto_refresh)
    elif page == "Source Analysis":
        source_analysis(project, run_model, auto_refresh)
    elif page == "Sensitivity Lab":
        sensitivity_lab(project)
    elif page == "Air Cooling":
        air_cooling_page()
    elif page == "Brayton Map":
        brayton_page()
    elif page == "Export":
        export_page(project, run_model, auto_refresh)


if __name__ == "__main__":
    main()

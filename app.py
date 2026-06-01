"""
Two-Phase Data-Center Cooling — Interactive Engineering App
===========================================================
A multi-tab Streamlit front-end over the validated thermodynamic / control /
economic model in `core/`.

Run:  streamlit run app.py
"""
import time
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

import core
from core import Assumptions, UI_RANGES, FLUID_CHOICES

st.set_page_config(page_title="ADAMS — Two-Phase Cooling",
                   page_icon="🧊", layout="wide",
                   initial_sidebar_state="expanded")

# --------------------------------------------------------------------------- #
#  Styling
# --------------------------------------------------------------------------- #
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 1400px;}
[data-testid="stMetricValue"] {font-size: 1.5rem;}
h1, h2, h3 {color: #1a3a5c;}
.small-note {font-size: 0.82rem; color: #666;}
</style>
""", unsafe_allow_html=True)

PALETTE = dict(red="#d94545", blue="#3a78c2", green="#2e8b57",
               purple="#9b6fb5", orange="#e0a458", grey="#9aa3ad",
               dark="#1a3a5c")


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
        st.plotly_chart(process_flow_figure(A, ss), use_container_width=True)
    with right:
        st.markdown("##### Cooling efficiency")
        st.plotly_chart(pue_gauge(ss), use_container_width=True)


def pue_gauge(ss):
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=ss["PUE_full"],
        number=dict(valueformat=".3f", font=dict(size=40)),
        delta=dict(reference=1.0, increasing=dict(color="#d94545"),
                   valueformat=".3f"),
        title=dict(text="Full-facility PUE (1.0 = ideal)", font=dict(size=13)),
        gauge=dict(axis=dict(range=[1.0, 1.7]),
                   bar=dict(color="#2e8b57"),
                   steps=[dict(range=[1.0, 1.15], color="#d8f0df"),
                          dict(range=[1.15, 1.35], color="#fdf0d0"),
                          dict(range=[1.35, 1.7], color="#f6d6d2")],
                   threshold=dict(line=dict(color="#1a3a5c", width=3),
                                  value=ss["PUE_full"]))))
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
    return fig



def process_flow_figure(A, ss):
    """Annotated process-flow schematic built with Plotly shapes."""
    fig = go.Figure()
    fig.update_xaxes(visible=False, range=[0, 13])
    fig.update_yaxes(visible=False, range=[0, 8])

    def box(x, y, w, h, text, color):
        fig.add_shape(type="rect", x0=x, y0=y, x1=x + w, y1=y + h,
                      line=dict(color="#333", width=1.8), fillcolor=color,
                      opacity=0.9)
        fig.add_annotation(x=x + w / 2, y=y + h / 2, text=text, showarrow=False,
                           font=dict(size=16, color="#111"))

    def arrow(x1, y1, x2, y2, color, label=None):
        fig.add_annotation(x=x2, y=y2, ax=x1, ay=y1, xref="x", yref="y",
                           axref="x", ayref="y", showarrow=True, arrowhead=3,
                           arrowsize=1.6, arrowwidth=3.0, arrowcolor=color)
        if label:
            fig.add_annotation(x=(x1 + x2) / 2, y=(y1 + y2) / 2 + 0.28,
                               text=label, showarrow=False,
                               font=dict(size=13, color="#222"),
                               bgcolor="rgba(255,255,255,0.85)")

    box(0.4, 3.0, 2.0, 3.0, "Server Rack<br>+ Cold Plate", "#c9ced6")
    box(5.2, 5.0, 2.6, 1.7, "Condenser /<br>Heat Exchanger", "#e8a0a0")
    box(9.6, 4.8, 3.0, 1.9, "External Water<br>/ Heat Reuse", "#a8c7e8")
    box(9.9, 2.0, 2.0, 1.4, "Liquid<br>Reservoir", "#a8c7e8")
    box(5.9, 1.1, 1.3, 1.0, "Pump", "#dfe4ea")

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
                       showarrow=False, font=dict(size=13, color="#a60"))
    info = (f"Evap {A.T_evap_C:.0f}°C/{ss['Pevap_bar']:.1f} bar · "
            f"Cond {A.T_cond_C:.0f}°C/{ss['Pcond_bar']:.1f} bar · "
            f"Cond duty {ss['Qcond_kW']:.0f} kW · PUE-full {ss['PUE_full']:.3f}")
    fig.update_layout(title=dict(text=f"Process Flow — {A.fluid}, "
                                 f"{A.Q_rack_kW:.0f} kW rack",
                                 font=dict(size=18)),
                      height=480, margin=dict(l=10, r=10, t=46, b=10),
                      annotations=list(fig.layout.annotations) + [dict(
                          x=6.5, y=7.6, text=info, showarrow=False,
                          font=dict(size=14, color=PALETTE["dark"]))])
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
        st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(fig, use_container_width=True)

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
    st.plotly_chart(fig, use_container_width=True)


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
    st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(dynamic_figure(A, df), use_container_width=True)
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
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = go.Figure(go.Bar(x=df.Technology, y=df.MaxDensity_kW,
                               marker_color=colors, text=df.MaxDensity_kW,
                               textposition="outside"))
        fig.update_layout(title="Max rack density [kW]", height=330,
                          margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        fig = go.Figure(go.Bar(x=df.Technology, y=df.CoolingCost_kUSD_yr,
                               marker_color=colors,
                               text=df.CoolingCost_kUSD_yr.round(1),
                               textposition="outside"))
        fig.update_layout(title=f"Cooling cost/rack/yr @ ${elec}/kWh [k$]",
                          height=330, margin=dict(t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)

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
    .econ-card{background:#11233a;border:1px solid #1f3b5c;border-radius:12px;
        padding:14px 16px;text-align:center;}
    .econ-lab{font-size:0.75rem;color:#8fa9c4;text-transform:uppercase;
        letter-spacing:0.05em;}
    .econ-val{font-size:1.7rem;font-weight:700;color:#eaf2fb;}
    .econ-pos{color:#5fd08a;} .econ-neg{color:#e07a7a;}
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
        st.plotly_chart(fig, use_container_width=True)
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
        st.plotly_chart(fig, use_container_width=True)

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
        st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
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
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = go.Figure(go.Bar(x=ok.Fluid, y=ok.hfg_kJ_kg,
                                   marker_color=PALETTE["green"]))
            fig.update_layout(title="Latent heat h_fg [kJ/kg]", height=350,
                              margin=dict(t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
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
    # V1 -> HPZ pressure (linear), plus vapor-load back-pressure coupling
    hpz_bar = P_min + (P_max - P_min) * (v1_pct / 100.0)
    hpz_bar += 0.25 * (load_factor - 1.0) * (P_max - P_min) / 4.5
    hpz_bar = float(np.clip(hpz_bar, P_min, P_max + 0.5))

    t_sat_out = _sat_T_from_P(fluid, hpz_bar)
    t_sat_in = _sat_T_from_P(fluid, hpz_bar + dP_cp)

    # cold-plate ΔT scales with heat flux (finite conductance): 18 K at nominal
    dT_cp = 18.0 * load_factor
    t_junc_in = t_sat_in + dT_cp          # hottest point
    t_junc_out = t_sat_out + dT_cp

    # free-cooling offset: how far above ambient the heat sink sits. Cold
    # ambient gives a generous offset (lots of free-cooling headroom);
    # warm ambient shrinks it. Continuous across the whole 10-50C range so
    # ambient always has a visible effect.
    #   <=10C -> +18 ; 28C -> +15 ; 30C -> +10 ; >=50C -> +4
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

    # condensation tracks ambient continuously (sink = ambient + offset),
    # widened by heat load. Floored at the loop saturation it must condense.
    cond_approach = 3.0 * load_factor
    t_cond = max(t_amb_C + offset + cond_approach, t_sat_out + 1.0)
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
                offset=offset, dT_cp=dT_cp, load_factor=load_factor)


def _gauge(value, vmin, vmax, title, unit, danger=None, warning=None):
    """Plotly gauge with optional warning/danger zones."""
    steps = []
    if warning is not None and danger is not None:
        steps = [dict(range=[vmin, warning], color="#1f3b2f"),
                 dict(range=[warning, danger], color="#7a6a1f"),
                 dict(range=[danger, vmax], color="#6b1f1f")]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value,
        number=dict(suffix=f" {unit}", font=dict(size=34, color="#eaeaea")),
        title=dict(text=title, font=dict(size=14, color="#bbb")),
        gauge=dict(axis=dict(range=[vmin, vmax], tickcolor="#888"),
                   bar=dict(color="#4fa3e0"), bgcolor="#1a1a1a",
                   borderwidth=1, bordercolor="#333", steps=steps,
                   threshold=dict(line=dict(color="red", width=3),
                                  value=danger) if danger else None)))
    fig.update_layout(height=240, margin=dict(l=20, r=20, t=50, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#eaeaea"))
    return fig


def _temp_bar(value, label):
    """Horizontal temperature bar with yellow (>85) / red (>95) zones."""
    color = "#4fa3e0"
    if value >= 95:
        color = "#e0453a"
    elif value >= 85:
        color = "#e0a83a"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[value], y=[label], orientation="h",
                         marker_color=color, width=0.5,
                         text=[f"{value:.1f} °C"], textposition="outside",
                         textfont=dict(size=18, color="#eaeaea")))
    # zone shading
    fig.add_vrect(x0=85, x1=95, fillcolor="#e0a83a", opacity=0.18, line_width=0)
    fig.add_vrect(x0=95, x1=130, fillcolor="#e0453a", opacity=0.18, line_width=0)
    fig.add_vline(x=85, line_dash="dot", line_color="#e0a83a")
    fig.add_vline(x=95, line_dash="dot", line_color="#e0453a")
    fig.update_layout(height=130, margin=dict(l=10, r=60, t=10, b=10),
                      xaxis=dict(range=[20, 130], title="°C",
                                 color="#bbb", gridcolor="#333"),
                      yaxis=dict(color="#bbb"),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig


def tab_adams(A):
    # dark theme scoped to this tab
    st.markdown("""
    <style>
    .adams-card {background:#161616; border:1px solid #2a2a2a; border-radius:12px;
                 padding:14px 18px; margin-bottom:10px;}
    .adams-val {font-size:2.0rem; font-weight:700; color:#eaeaea; line-height:1.1;}
    .adams-lab {font-size:0.8rem; color:#9aa3ad; text-transform:uppercase;
                letter-spacing:0.05em;}
    .adams-unit {font-size:1.0rem; color:#9aa3ad;}
    </style>
    """, unsafe_allow_html=True)

    st.header("ADAMS Live Dashboard")
    # per-chip nominal load comes from the sidebar (rack load / chip count)
    q_nom = A.Q_rack_kW * 1000.0 / A.n_chips
    st.caption(f"{A.fluid} · per-chip nominal {q_nom:.0f} W (from sidebar: "
               f"{A.Q_rack_kW:.0f} kW ÷ {A.n_chips} chips) · V1 & ambient are "
               f"local to this dashboard")

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
    mode_color = {"Performance": "#2f6fd0", "Standby Thermal": "#2e8b57",
                  "Circular": "#e06b2f"}[r["mode"]]
    st.markdown(
        f"<div class='adams-card' style='background:{mode_color};"
        f"text-align:center;'><span class='adams-lab' style='color:#eee;'>"
        f"Operating Mode</span><div class='adams-val' style='color:#fff;'>"
        f"{r['mode']}</div></div>", unsafe_allow_html=True)

    # ---- top row: gauges ----
    g1, g2 = st.columns(2)
    with g1:
        st.plotly_chart(_gauge(r["hpz_bar"], 1.0, 6.0, "HPZ Pressure", "bar"),
                        use_container_width=True)
    with g2:
        peak = max(r["t_junc_in"], r["t_junc_out"])
        st.plotly_chart(_gauge(peak, 20, 130, "Peak Junction Temp", "°C",
                               danger=95, warning=85), use_container_width=True)

    # ---- junction temperature bars ----
    st.markdown("##### Chip junction temperature (yellow >85°C, red >95°C)")
    b1, b2 = st.columns(2)
    with b1:
        st.plotly_chart(_temp_bar(r["t_junc_in"], "T_junc inlet (hottest)"),
                        use_container_width=True)
    with b2:
        st.plotly_chart(_temp_bar(r["t_junc_out"], "T_junc outlet"),
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
    card(d2, "Free-cooling offset", f"+{r['offset']:.1f}", "°C")
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
- **Ambient** ({t_amb:.0f} °C): sets the free-cooling offset
  (**+{r['offset']:.1f} °C**) and the condensation floor. It drives T_cond and
  T_water **when the loop runs cool** (low V1 / low pressure); at high V1 the
  refrigerant's own saturation temperature is hotter than ambient+offset, so it
  governs instead and ambient has little visible effect — that is correct
  physics, not a bug.
- **T_junction = T_sat + cold-plate ΔT**; inlet uses HPZ + 0.48 bar
  (4 Venturi × 0.12 bar).
- **Mode**: Performance if T_sat_out ≤ ambient+offset; Circular if
  T_sat_out ≥ 60 °C; else Standby Thermal.
        """)


# --------------------------------------------------------------------------- #
#  Main
# --------------------------------------------------------------------------- #
def main():
    st.title("ADAMS")
    st.markdown("<div style='font-size:1.15rem;color:#3a5a7a;font-weight:500;"
                "margin-top:-8px;margin-bottom:10px;'>Advanced Data-center "
                "Adaptive Multiphase System · two-phase cooling design studio"
                "</div>", unsafe_allow_html=True)

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

    tabs = st.tabs(["Overview", "ADAMS Live", "Steady State", "Dynamic Sim",
                    "Comparison", "Economics", "Scale-Up", "Cold Plate",
                    "Refrigerants & Sizing"])
    with tabs[0]:
        tab_overview(A, ss)
    with tabs[1]:
        tab_adams(A)
    with tabs[2]:
        tab_steady(A, ss)
    with tabs[3]:
        tab_dynamic(A)
    with tabs[4]:
        tab_comparison(A, ss)
    with tabs[5]:
        tab_economics(A, ss)
    with tabs[6]:
        tab_scaleup(A, ss)
    with tabs[7]:
        tab_coldplate(A, ss)
    with tabs[8]:
        tab_refrig_sizing(A)


if __name__ == "__main__":
    main()

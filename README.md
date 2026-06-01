# ADAMS — Two-Phase Cooling Design Studio

**ADAMS** (Advanced Data-center Adaptive Multiphase System) is an interactive
Streamlit app for evaluating a **pumped two-phase, direct-to-chip cooling
system** for high-density data-center racks. It wraps a validated
thermodynamic / control / economic model in a multi-tab UI where every input is
adjustable and every result updates live.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501).

If `CoolProp` cannot be installed, the app still runs using built-in analytic
fallback properties (clearly indicated). R1336mzz(Z) always uses its vendor
saturation curve.

## Structure

```
cooling_app/
├── app.py                 # Streamlit UI (tabs, charts, controls)
├── requirements.txt
├── README.md
└── core/                  # pure-Python engineering model (no UI deps)
    ├── __init__.py
    ├── assumptions.py     # Assumptions dataclass, UI ranges, sanity_check()
    ├── fluids.py          # CoolProp + R1336mzz(Z) vendor curve + fallback
    ├── steady.py          # energy/mass balance, cold plate, condenser, sizing
    ├── control.py         # PID, PLC state machine, supervisory optimizer
    ├── dynamic.py         # lumped ODE plant, simulator, scenario builder
    └── economics.py       # CAPEX/PBP/NPV/IRR/TCO, BAU, climate, build-out
```

## Tabs

1. **Overview** — styled hero cards, energy-flow Sankey, PUE gauge, annotated
   process-flow diagram, microchannel explainer.
2. **ADAMS Live** — real-time dashboard for the ADAMS architecture on
   R1336mzz(Z). Sliders for V1 valve, chip load and ambient drive an HPZ
   pressure gauge, junction-temperature bars (yellow >85 °C, red >95 °C),
   loop temperatures, and a colour-coded mode indicator. Dark theme.
3. **Steady State** — power breakdown, partial vs full-facility PUE, mode
   comparison, condenser sensitivity.
4. **Cold Plate** — interactive geometry; chip temp, vapor quality, ΔP, CHF
   margin, mass-flow sweep.
5. **Dynamic Sim** — closed-loop simulator with preset and custom scenarios,
   plus automatic remediation advice (redundancy for pump failure, make-up /
   leak detection for low level, etc.).
6. **Comparison** — two-phase vs air vs single-phase, with editable air and
   single-phase PUE and electricity price.
7. **Economics** — dashboard with KPI cards (payback / NPV / IRR / CAPEX), TCO
   bars, cumulative cash flow, NPV tornado, year-by-year table. Parameters are
   hidden behind a collapsed "Edit cost & finance assumptions" panel.
8. **Scale-Up** — three sub-sections: energy & reuse, climate & heat off-take
   (free-cooling fraction and district-heat uptake by climate), and multi-year
   build-out with carbon and water footprint.
9. **Refrigerants & Sizing** — fluid comparison (R1336mzz(Z) default) and
   component sizing with CSV export.

## Sanity checks

The sidebar inputs are validated on every run: water return must exceed supply,
condensing must exceed evaporation, trip must exceed target, etc. Hard errors
stop the app with a message; soft warnings are shown but allowed.

## Refrigerants

**R1336mzz(Z)** (Honeywell Solstice N40) is the default low-pressure HFO; since
it is not in this CoolProp build, its saturation behaviour comes from the vendor
P–T curve (1.3 bar @ 35 °C … 5.8 bar @ 75 °C) with property estimates. The other
fluids use CoolProp's NIST-grade equations of state.

## Caveats

Early-screening model. Cold-plate HTC/CHF, condenser UA, lumped masses, the
R1336mzz(Z) non-saturation properties, and all cost/climate figures are
clearly-labelled, editable assumptions — not vendor/measured data. Replace them
before detailed design or investment decisions.

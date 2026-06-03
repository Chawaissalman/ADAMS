# Waste-Heat Absorption Chiller — Pitch-Ready Streamlit Redesign

This package replaces the original `app.py` with a modern pitch dashboard while preserving the existing engineering calculation layer under `src/`.

## What changed

- Rebuilt the app around a pitch-first dashboard rather than a dense tabbed technical interface.
- Added a modern dark sidebar, gradient hero section, animated KPI cards, and an animated heat-flow ribbon.
- Replaced always-active tabs with page-based navigation so only the selected view runs.
- Added cached base calculations and cached sensitivity wrappers to reduce repeated recalculation during live demos.
- Moved technical drill-downs into separate pages: Source Analysis, Sensitivity Lab, Air Cooling, Brayton Map, and Export.
- Made heavy GT sensitivity a deliberate action rather than something that loads with the main pitch screen.
- Kept the existing model imports and function calls intact.

## How to use

Copy this `app.py` into your existing project root, replacing the current `app.py`.

Your project should still include the original `src/` folder shown in the previous project structure.

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Notes

- The redesigned app requires the same dependencies as before.
- The CSS animations are built into `app.py`; no extra animation package is required.
- The app uses Streamlit's cache for base runs and sensitivity runs, so changed assumptions can be refreshed manually or through the auto-refresh toggle.

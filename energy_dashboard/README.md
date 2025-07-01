# Energy Dashboard Simulator

A modular simulation and visualization tool for modeling energy consumption patterns across commercial or industrial buildings, now adapted for realistic home energy simulation.

## Features
- Modular load models: HVAC, lighting, appliances/machines, solar
- Time-based simulation (15-min or 1-hour steps)
- Analytics: peak demand, subsystem breakdown, inefficiency flags
- **Cost calculation:** total energy cost at 9 rupees per kWh
- **Energy recommendations:** actionable suggestions based on your simulation results
- Interactive dashboard: time-series, pie, and bar charts (dark mode)
- Built-in test data for quick start

## Directory Structure
```
simulator/
  __init__.py
  models/
    hvac.py
    lighting.py
    appliances.py
  analytics.py
  visualizer.py
  simulator.py
main.py
```

## Requirements
- Python 3.7+
- pandas
- numpy
- plotly
- dash
- dash-bootstrap-components

## Getting Started
1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Run the simulator:
   ```
   python main.py
   ```

## Dashboard Usage
- Select your desired time step and simulation period.
- Click **Run Simulation** to generate results.
- **Analytics panel** will display:
  - Peak load and subsystem
  - Subsystem energy shares
  - Solar offset percentage
  - **Total energy consumed (kWh)**
  - **Total cost (₹, at 9 rupees per kWh)**
  - **Energy recommendations** (e.g., increase solar, shift loads, reduce night HVAC, audit appliances)
- Plots update instantly to show time series, subsystem shares, and daily totals.

## Customization
- Edit `main.py` or `app.py` to define your own load schedules, power ratings, or simulation period.
- Extend models in `simulator/models/` for more detailed equipment.
- Adjust the cost rate or recommendation logic in `app.py` as needed.

## Optional Extensions
- Add schedule optimization, export features, or more advanced analytics as needed.

---
MIT License 
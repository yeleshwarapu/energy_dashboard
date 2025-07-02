# Energy Dashboard Simulator

A modular, realistic home energy simulation and dashboard for a 3-bedroom house. Model and visualize energy use, costs, and solar offset across all seasons.

## Features
- **Realistic home simulation:** 3-bedroom house with HVAC, kitchen, laundry, entertainment, EV charging, lighting, and solar PV
- **Season-aware:** Choose Spring, Summer, Fall, or Winter—temperature, solar, lighting, HVAC, and price profiles adjust automatically
- **Human-centric schedules:** Each subsystem/asset uses realistic daily/weekly usage patterns
- **Interactive dashboard:**
  - Time-series, pie, bar, and hierarchical sunburst charts (dark mode)
  - Hierarchical analytics: see breakdowns by HVAC, Kitchen, Laundry, Entertainment, EV Charging, etc.
  - **Interactive sliders** for HVAC setpoint and chiller max power—see the impact instantly
  - No plots shown until you run a simulation (clean startup)
- **Analytics:**
  - Peak load and subsystem
  - Subsystem energy shares (with hierarchy)
  - Solar offset percentage
  - Total energy consumed (kWh)
  - Total cost (₹, seasonally adjusted per kWh)
  - Actionable energy recommendations
- **Customizable:** Easily adjust schedules, power ratings, or add new loads

## Directory Structure
```
simulator/
  models/
    hvac.py
    lighting.py
    appliances.py
  analytics.py
  visualizer.py
  simulator.py
app.py
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
2. Run the dashboard:
   ```
   python app.py
   ```

## Dashboard Usage
- **Select your season** (Spring, Summer, Fall, Winter) in the controls.
- Choose time step (1-hour or 15-min) and simulation period (1 day or 7 days).
- **Adjust the HVAC setpoint and chiller max power using the sliders** to see how comfort and system size affect energy and cost.
- Click **Run Simulation** to generate results.
- **Analytics panel** will display:
  - Peak load and subsystem
  - Hierarchical subsystem energy shares (e.g., HVAC > Chiller/Pump/Fan)
  - Solar offset percentage
  - Total energy consumed (kWh)
  - Total cost (₹, with seasonal price per kWh)
  - Actionable recommendations (e.g., increase solar, shift loads, reduce night HVAC, audit appliances)
- **Plots:**
  - Time series (kW)
  - Pie chart (energy share)
  - Sunburst (hierarchical breakdown)
  - Daily bar chart (total kWh per day)
- **No plots are shown until you run a simulation.**

## Seasons & What Changes
- **Spring:** 15–25°C, 10h solar, mild HVAC, normal lighting, ₹8/kWh
- **Summer:** 22–34°C, 10h solar, cooling HVAC, normal lighting, ₹9/kWh
- **Fall:** 14–24°C, 9h solar, mild HVAC, normal lighting, ₹8/kWh
- **Winter:** 5–16°C, 7h solar, heating HVAC, more lighting, ₹10/kWh
- Schedules, solar output, and costs all adjust automatically.

## Customization
- Edit `app.py` to define your own load schedules, power ratings, or simulation period.
- Extend models in `simulator/models/` for more detailed equipment.
- Adjust the cost rate, temperature profiles, or recommendation logic as needed.

## Interpreting Results
- **Peak load:** When and which subsystem draws the most power
- **Subsystem shares:** See which areas (HVAC, Kitchen, etc.) use the most energy
- **Solar offset:** How much of your demand is met by solar
- **Total cost:** Calculated with the correct seasonal rate
- **Recommendations:** Suggestions are based on your simulated usage and can help you save energy or money

## Example: Compare Summer vs. Winter
1. Select "Summer", 1-hour steps, 7 days, and run the simulation.
2. Note the high HVAC and EV charging shares, and solar offset.
3. Switch to "Winter" and run again—see how heating, lighting, and costs change.
4. **Try adjusting the HVAC setpoint and chiller max power sliders** to see how comfort and system size affect your results.

---
MIT License 
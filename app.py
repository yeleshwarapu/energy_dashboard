import dash
from dash import dcc, html, Output, Input, State
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
from simulator.simulator import BuildingSimulator
from simulator.models.hvac import HVACLoad
from simulator.models.lighting import LightingLoad
from simulator.models.appliances import ApplianceLoad
from simulator.analytics import find_peak_load, subsystem_share, flag_inefficiencies, solar_offset_pct
from simulator.visualizer import get_time_series_fig, get_pie_share_fig, get_daily_bar_fig
import json

# Dash app with dark theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
app.title = "Energy Dashboard Simulator"

def repeat_with_variation(base, days, steps_per_day, min_on=0, max_on=None):
    result = []
    for d in range(days):
        arr = base[:]
        on_indices = [i for i, v in enumerate(arr) if v == 1]
        off_indices = [i for i, v in enumerate(arr) if v == 0]
        # Randomly turn off some ON hours
        if min_on > 0 and len(on_indices) > min_on:
            to_off = np.random.choice(on_indices, size=np.random.randint(0, len(on_indices)-min_on+1), replace=False)
            for idx in to_off:
                arr[idx] = 0
        # Randomly turn on up to max_on extra hours
        if max_on and len(off_indices) > 0:
            to_on = np.random.choice(off_indices, size=np.random.randint(0, max_on+1), replace=False)
            for idx in to_on:
                arr[idx] = 1
        result.extend(arr)
    return result

def run_simulation(randomize=True, timestep_hours=1.0, period_hours=24):
    np.random.seed(42)
    sim = BuildingSimulator(timestep_hours=timestep_hours, period_hours=period_hours)
    days = int(period_hours / 24)
    steps_per_day = int(24 / timestep_hours)
    total_steps = int(period_hours / timestep_hours)
    # --- OUTDOOR TEMPERATURE PROFILE ---
    # Simulate a daily temperature curve (min at night, max in afternoon), with random day-to-day variation
    base_min = 22  # °C, night
    base_max = 34  # °C, afternoon
    temp_profile = []
    for d in range(days):
        day_min = base_min + np.random.uniform(-1, 1)
        day_max = base_max + np.random.uniform(-2, 2)
        for t in range(steps_per_day):
            hour = t * timestep_hours
            # Sine curve: min at 4am, max at 3pm
            temp = day_min + (day_max - day_min) * 0.5 * (1 + np.sin((hour - 15) / 24 * 2 * np.pi))
            temp_profile.append(temp)
    # --- HVAC: 4 kW max, setpoint 24°C ---
    sim.add_load(HVACLoad("Central AC", temp_profile, setpoint=24, max_power=4.0, alpha=0.1), 'HVAC')
    # Lighting: 0.7 kW, 6-8 hours/day, more on weekends
    light_schedule = []
    for d in range(days):
        light_hours = 8 if d in [5, 6] else 6
        light_on = int(light_hours / timestep_hours)
        light_off1 = int(16 / timestep_hours)
        light_off2 = steps_per_day - light_off1 - light_on
        light_schedule += [0]*light_off1 + [1]*light_on + [0]*light_off2
    sim.add_load(LightingLoad("Whole House", 0.7, light_schedule, randomize), 'Lighting')
    # Clothes washer/dryer: only on weekends
    washer_schedule = []
    dryer_schedule = []
    for d in range(days):
        if d in [5, 6]:
            washer_on = [0]*int(8/timestep_hours) + [1]*int(1/timestep_hours) + [0]*(steps_per_day - int(8/timestep_hours) - int(1/timestep_hours))
            dryer_on = [0]*int(12/timestep_hours) + [1]*int(1/timestep_hours) + [0]*(steps_per_day - int(12/timestep_hours) - int(1/timestep_hours))
        else:
            washer_on = [0]*steps_per_day
            dryer_on = [0]*steps_per_day
        washer_schedule += washer_on
        dryer_schedule += dryer_on
    sim.add_load(ApplianceLoad("Washer", 0.5, washer_schedule, randomize), 'Appliances')
    sim.add_load(ApplianceLoad("Dryer", 4, dryer_schedule, randomize), 'Appliances')
    # Dishwasher: 1.2 kW, 1 hour in morning, 1 hour in evening, every day
    dw_schedule = []
    for d in range(days):
        dw_on1 = [0]*int(7/timestep_hours) + [1]*int(1/timestep_hours)
        dw_on2 = [0]*int(10/timestep_hours) + [1]*int(1/timestep_hours)
        dw_rest = [0]*(steps_per_day - len(dw_on1) - len(dw_on2))
        dw_schedule += dw_on1 + dw_on2 + dw_rest
    sim.add_load(ApplianceLoad("Dishwasher", 1.2, dw_schedule, randomize), 'Kitchen')
    # EV Charger: 7 kW, overnight (12am-2am), 3 random days/week
    ev_days = np.random.choice(range(days), 3, replace=False) if days >= 3 else range(days)
    ev_schedule = []
    for d in range(days):
        if d in ev_days:
            ev_on = [1]*int(2/timestep_hours) + [0]*(steps_per_day - int(2/timestep_hours))
        else:
            ev_on = [0]*steps_per_day
        ev_schedule += ev_on
    sim.add_load(ApplianceLoad("EV Charger", 7, ev_schedule, randomize), 'Appliances')
    # Oven: 2.5 kW, random dinner hour
    oven_schedule = []
    for d in range(days):
        oven_hour = np.random.randint(17, 20)
        oven_on = [0]*int(oven_hour/timestep_hours) + [1]*int(1/timestep_hours) + [0]*(steps_per_day - int(oven_hour/timestep_hours) - int(1/timestep_hours))
        oven_schedule += oven_on
    sim.add_load(ApplianceLoad("Oven", 2.5, oven_schedule, randomize), 'Kitchen')
    # Microwave: 1.2 kW, random breakfast hour
    mw_schedule = []
    for d in range(days):
        mw_hour = np.random.randint(7, 10)
        mw_on = [0]*int(mw_hour/timestep_hours) + [1]*int(1/timestep_hours) + [0]*(steps_per_day - int(mw_hour/timestep_hours) - int(1/timestep_hours))
        mw_schedule += mw_on
    sim.add_load(ApplianceLoad("Microwave", 1.2, mw_schedule, randomize), 'Kitchen')
    # Fridge: 0.18 kW, always on
    sim.add_load(ApplianceLoad("Fridge", 0.18, [1]*total_steps, randomize), 'Appliances')
    # TV: 0.15 kW, 3-6 hours/day, random evening hours
    tv_base = [0]*int(17/timestep_hours) + [1]*int(5/timestep_hours) + [0]*(steps_per_day - int(17/timestep_hours) - int(5/timestep_hours))
    sim.add_load(ApplianceLoad("TV", 0.15, repeat_with_variation(tv_base, days, steps_per_day, min_on=int(3/timestep_hours), max_on=int(2/timestep_hours)), randomize), 'Appliances')
    # Computer: 0.1 kW, 6-10 hours/day, random day hours
    comp_base = [0]*int(8/timestep_hours) + [1]*int(8/timestep_hours) + [0]*(steps_per_day - int(8/timestep_hours) - int(8/timestep_hours))
    sim.add_load(ApplianceLoad("Computer", 0.1, repeat_with_variation(comp_base, days, steps_per_day, min_on=int(6/timestep_hours), max_on=int(2/timestep_hours)), randomize), 'Appliances')
    # Solar PV: -4 kW, 10 hours/day, output varies by day
    solar_schedule = []
    solar_powers = [float(np.random.uniform(2, 3.5)) for _ in range(days)]
    for d in range(days):
        solar_on = [0]*int(7/timestep_hours) + [1]*int(10/timestep_hours) + [0]*(steps_per_day - int(7/timestep_hours) - int(10/timestep_hours))
        solar_schedule += solar_on
    # Build a full-length solar power array (elementwise multiply)
    solar_power_profile = []
    idx = 0
    for d in range(days):
        for v in ([0]*int(7/timestep_hours) + [1]*int(10/timestep_hours) + [0]*(steps_per_day - int(7/timestep_hours) - int(10/timestep_hours))):
            solar_power_profile.append(-solar_powers[d] if v == 1 else 0)
            idx += 1
    sim.add_load(ApplianceLoad("Solar PV", -1, solar_power_profile, randomize), 'Solar')
    df = sim.run()
    return df

def get_analytics(df, timestep_hours):
    peak_hour, peak_subsystem, peak_value = find_peak_load(df)
    shares = subsystem_share(df, timestep_hours)
    solar_pct = solar_offset_pct(df, timestep_hours)
    warnings = flag_inefficiencies(df)
    # --- COST CALCULATION ---
    # Only include positive (consumption) subsystems, exclude 'Solar'
    consumption_cols = [col for col in df.columns if col not in ['Total', 'Solar'] and df[col].sum() > 0]
    total_energy_kwh = df[consumption_cols].sum().sum() * timestep_hours
    cost_per_kwh = 9  # rupees
    total_cost = total_energy_kwh * cost_per_kwh
    # --- RECOMMENDATIONS ---
    recommendations = []
    if solar_pct < 20:
        recommendations.append("Consider increasing solar capacity to offset more demand.")
    if peak_value > 10:
        recommendations.append("Peak load is high; consider shifting flexible loads to off-peak hours.")
    if 'High night-time HVAC consumption detected.' in warnings:
        recommendations.append("Reduce HVAC usage at night to save energy.")
    if total_energy_kwh > 200:
        recommendations.append("Overall energy use is high; audit appliances for efficiency.")
    if not recommendations:
        recommendations.append("Energy usage is within typical range. Good job!")
    return peak_hour, peak_subsystem, peak_value, shares, solar_pct, warnings, total_energy_kwh, total_cost, recommendations

# --- DASH APP LAYOUT ---
# The main layout of the dashboard, including controls, analytics, and plots.
app.layout = dbc.Container([
    # Title
    html.H2("Building Energy Dashboard Simulator", className="text-center my-4"),
    # Controls and analytics row
    dbc.Row([
        # Controls card (left)
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Simulation Controls"),
                dbc.CardBody([
                    # Toggle for randomizing loads
                    dbc.Checklist(
                        options=[{"label": "Randomize Loads (+/-10%)", "value": 1}],
                        value=[1],
                        id="randomize-toggle",
                        switch=True,
                    ),
                    html.Br(),
                    # Time step selection
                    dbc.RadioItems(
                        options=[
                            {"label": "1-hour Steps", "value": 1.0},
                            {"label": "15-min Steps", "value": 0.25},
                        ],
                        value=1.0,
                        id="timestep-radio",
                        inline=True,
                        labelClassName="me-3"
                    ),
                    html.Br(),
                    # Simulation period selection
                    dbc.RadioItems(
                        options=[
                            {"label": "1 Day", "value": 24},
                            {"label": "7 Days", "value": 168},
                        ],
                        value=24,
                        id="period-radio",
                        inline=True,
                        labelClassName="me-3"
                    ),
                    html.Br(),
                    # Run simulation button
                    dbc.Button("Run Simulation", id="run-btn", color="primary", className="me-2"),
                ])
            ])
        ], width=3),
        # Analytics card (right)
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Analytics"),
                dbc.CardBody([
                    html.Div(id="analytics-output"),
                    html.Div(id="warnings-output", className="text-warning mt-2"),
                ])
            ])
        ], width=9)
    ], className="mb-4"),
    # Main plots
    dbc.Row([
        dbc.Col(dcc.Graph(id="time-series-plot"), width=12)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id="pie-plot"), width=6),
        dbc.Col(dcc.Graph(id="bar-plot"), width=6)
    ])
], fluid=True)

# --- MAIN DASH CALLBACK ---
# Runs the simulation and updates all plots and analytics when the user clicks 'Run Simulation'.
@app.callback(
    [Output("time-series-plot", "figure"),
     Output("pie-plot", "figure"),
     Output("bar-plot", "figure"),
     Output("analytics-output", "children"),
     Output("warnings-output", "children")],
    [Input("run-btn", "n_clicks")],
    [State("randomize-toggle", "value"), State("timestep-radio", "value"), State("period-radio", "value")]
)
def update_dashboard(n_clicks, randomize_value, timestep_value, period_value):
    # Only run if the button was clicked
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    # Get user-selected simulation parameters
    randomize = 1 in (randomize_value or [])
    timestep = float(timestep_value)
    period = int(period_value)
    # Run the simulation
    df = run_simulation(randomize=randomize, timestep_hours=timestep, period_hours=period)
    # Compute analytics
    peak_hour, peak_subsystem, peak_value, shares, solar_pct, warnings, total_energy_kwh, total_cost, recommendations = get_analytics(df, timestep)
    # Format analytics for display
    analytics = [
        html.P(f"Peak load at hour {peak_hour}: {peak_value:.2f} kW ({peak_subsystem})"),
        html.P("Subsystem energy share (%):")
    ]
    if isinstance(shares, pd.Series):
        analytics += [html.Li(f"{k}: {v:.1f}%") for k, v in shares.items()]
    else:
        analytics.append(html.P("No consumption data."))
    analytics.append(html.P(f"Solar offset: {solar_pct:.1f}% of total demand"))
    analytics.append(html.P(f"Total energy consumed: {total_energy_kwh:.1f} kWh"))
    analytics.append(html.P(f"Total cost: ₹{total_cost:,.0f}"))
    analytics.append(html.P("Recommendations:"))
    analytics += [html.Li(rec) for rec in recommendations]
    warnings_div = [html.Div(w) for w in warnings] if warnings else ""
    # Return all updated dashboard elements
    return (
        get_time_series_fig(df),
        get_pie_share_fig(df, timestep),
        get_daily_bar_fig(df, timestep),
        analytics,
        warnings_div
    )

if __name__ == "__main__":
    app.run(debug=True) 
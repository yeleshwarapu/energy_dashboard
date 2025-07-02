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
from simulator.visualizer import get_time_series_fig, get_pie_share_fig, get_daily_bar_fig, get_sunburst_share_fig
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

def run_simulation(randomize=True, timestep_hours=1.0, period_hours=24, season="summer"):
    np.random.seed(42)
    sim = BuildingSimulator(timestep_hours=timestep_hours, period_hours=period_hours)
    days = int(period_hours / 24)
    steps_per_day = int(24 / timestep_hours)
    total_steps = int(period_hours / timestep_hours)
    # Ensure all schedules are the correct length
    def fix_length(arr):
        if len(arr) > total_steps:
            return arr[:total_steps]
        elif len(arr) < total_steps:
            return arr + [0] * (total_steps - len(arr))
        return arr
    # --- SEASONAL PARAMETERS ---
    if season == "summer":
        base_min, base_max = 22, 34
        solar_hours = 10
        price_per_kwh = 9
        hvac_mode = "cool"
        lighting_factor = 1.0
    elif season == "winter":
        base_min, base_max = 5, 16
        solar_hours = 7
        price_per_kwh = 10
        hvac_mode = "heat"
        lighting_factor = 1.3  # more lighting in winter
    elif season == "spring":
        base_min, base_max = 15, 25
        solar_hours = 10
        price_per_kwh = 8
        hvac_mode = "mild"
        lighting_factor = 1.0
    elif season == "fall":
        base_min, base_max = 14, 24
        solar_hours = 9
        price_per_kwh = 8
        hvac_mode = "mild"
        lighting_factor = 1.0
    else:
        base_min, base_max = 20, 30
        solar_hours = 10
        price_per_kwh = 9
        hvac_mode = "cool"
        lighting_factor = 1.0
    # --- OUTDOOR TEMPERATURE PROFILE ---
    temp_profile = []
    for d in range(days):
        day_min = base_min + np.random.uniform(-1, 1)
        day_max = base_max + np.random.uniform(-2, 2)
        for t in range(steps_per_day):
            hour = t * timestep_hours
            temp = day_min + (day_max - day_min) * 0.5 * (1 + np.sin((hour - 15) / 24 * 2 * np.pi))
            temp_profile.append(temp)
    # --- HVAC: Chiller, Pump, Fan (seasonal logic) ---
    if hvac_mode == "cool":
        sim.add_load(HVACLoad("Chiller", temp_profile, setpoint=25, max_power=2.2, alpha=0.07), 'Chiller')
        sim.add_load(HVACLoad("Pump", temp_profile, setpoint=25, max_power=0.15, alpha=0.07), 'Pump')
        sim.add_load(HVACLoad("Fan", temp_profile, setpoint=25, max_power=0.4, alpha=0.10), 'Fan')
    elif hvac_mode == "heat":
        # Assume resistive heating (COP=1), higher setpoint
        sim.add_load(HVACLoad("Chiller", [18-temp for temp in temp_profile], setpoint=18, max_power=2.2, alpha=0.07), 'Chiller')
        sim.add_load(HVACLoad("Pump", [18-temp for temp in temp_profile], setpoint=18, max_power=0.15, alpha=0.07), 'Pump')
        sim.add_load(HVACLoad("Fan", [18-temp for temp in temp_profile], setpoint=18, max_power=0.4, alpha=0.10), 'Fan')
    else:
        # Mild: minimal HVAC
        sim.add_load(HVACLoad("Chiller", temp_profile, setpoint=25, max_power=0.8, alpha=0.03), 'Chiller')
        sim.add_load(HVACLoad("Pump", temp_profile, setpoint=25, max_power=0.05, alpha=0.03), 'Pump')
        sim.add_load(HVACLoad("Fan", temp_profile, setpoint=25, max_power=0.2, alpha=0.05), 'Fan')
    # --- Lighting: more in winter evenings ---
    light_schedule = []
    for d in range(days):
        if d % 7 in [5, 6]:
            morning_on = [0]*int(5/timestep_hours) + [1]*int(2/timestep_hours) + [0]*int(1/timestep_hours)
            evening_on = [0]*int(17/timestep_hours) + [1]*int(5/timestep_hours) + [0]*(steps_per_day - int(22/timestep_hours))
        else:
            morning_on = [0]*int(6/timestep_hours) + [1]*int(1/timestep_hours) + [0]*int(1/timestep_hours)
            evening_on = [0]*int(18/timestep_hours) + [1]*int(4/timestep_hours) + [0]*(steps_per_day - int(22/timestep_hours))
        off_hours = steps_per_day - len(morning_on) - len(evening_on)
        light_schedule += morning_on + [0]*off_hours + evening_on
    light_schedule = [min(1, int(lighting_factor * v + 0.5)) for v in light_schedule]
    light_schedule = fix_length(light_schedule)
    sim.add_load(LightingLoad("Whole House", 0.7, light_schedule, randomize), 'Lighting')
    # --- Kitchen ---
    # Fridge: always on
    sim.add_load(ApplianceLoad("Fridge", 0.18, fix_length([1]*total_steps), randomize), 'Fridge')
    # Dishwasher: after dinner (19-21), sometimes after breakfast on weekends
    dw_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        # After dinner
        dinner_hour = int(np.random.uniform(19, 21) / timestep_hours)
        arr[dinner_hour] = 1
        # After breakfast on weekends
        if d % 7 in [5, 6] and np.random.rand() < 0.5:
            breakfast_hour = int(np.random.uniform(7, 9) / timestep_hours)
            arr[breakfast_hour] = 1
        dw_schedule += arr
    sim.add_load(ApplianceLoad("Dishwasher", 1.2, fix_length(dw_schedule), randomize), 'Dishwasher')
    # Microwave: breakfast, lunch, dinner
    mw_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        for meal, window in [("breakfast", (7, 9)), ("lunch", (12, 14)), ("dinner", (18, 20))]:
            if np.random.rand() < 0.8:
                hour = int(np.random.uniform(*window) / timestep_hours)
                arr[hour] = 1
        mw_schedule += arr
    sim.add_load(ApplianceLoad("Microwave", 1.2, fix_length(mw_schedule), randomize), 'Microwave')
    # Oven: dinner prep, more likely on weekends
    oven_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        if np.random.rand() < (0.5 if d % 7 in [5, 6] else 0.2):
            hour = int(np.random.uniform(17, 20) / timestep_hours)
            arr[hour] = 1
        oven_schedule += arr
    sim.add_load(ApplianceLoad("Oven", 2.5, fix_length(oven_schedule), randomize), 'Oven')
    # --- Laundry: Washer/Dryer, mostly weekends, sometimes one weekday ---
    washer_schedule = []
    dryer_schedule = []
    for d in range(days):
        arr_w = [0]*steps_per_day
        arr_d = [0]*steps_per_day
        if d % 7 in [5, 6] or (np.random.rand() < 0.2):
            # Weekend or random weekday
            hour_w = int(np.random.uniform(10, 15) / timestep_hours)
            hour_d = hour_w + int(1/timestep_hours)
            arr_w[hour_w] = 1
            arr_d[hour_d % steps_per_day] = 1
        washer_schedule += arr_w
        dryer_schedule += arr_d
    sim.add_load(ApplianceLoad("Washer", 0.5, fix_length(washer_schedule), randomize), 'Washer')
    sim.add_load(ApplianceLoad("Dryer", 4, fix_length(dryer_schedule), randomize), 'Dryer')
    # --- Entertainment: TV, Computer ---
    # TV: evenings, more on weekends
    tv_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        evening_hours = range(int(18/timestep_hours), int(23/timestep_hours))
        hours_on = np.random.choice(list(evening_hours), size=np.random.randint(2, 5), replace=False)
        for h in hours_on:
            arr[h] = 1
        # More hours on weekends
        if d % 7 in [5, 6]:
            extra = np.random.choice(list(evening_hours), size=1)
            arr[extra[0]] = 1
        tv_schedule += arr
    sim.add_load(ApplianceLoad("TV", 0.15, fix_length(tv_schedule), randomize), 'TV')
    # Computer: afternoons/evenings, more on weekdays
    comp_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        if d % 7 not in [5, 6]:
            # Weekday: more likely
            for h in range(int(16/timestep_hours), int(22/timestep_hours)):
                if np.random.rand() < 0.5:
                    arr[h] = 1
        else:
            # Weekend: less likely
            for h in range(int(16/timestep_hours), int(22/timestep_hours)):
                if np.random.rand() < 0.2:
                    arr[h] = 1
        comp_schedule += arr
    sim.add_load(ApplianceLoad("Computer", 0.1, fix_length(comp_schedule), randomize), 'Computer')
    # --- EV Charging: late night, a few nights per week ---
    ev_schedule = []
    ev_days = np.random.choice(range(days), min(3, days), replace=False)
    for d in range(days):
        arr = [0]*steps_per_day
        if d in ev_days:
            hour = int(np.random.uniform(22, 24) / timestep_hours)
            arr[hour] = 1
        ev_schedule += arr
    sim.add_load(ApplianceLoad("EV Charger", 7, fix_length(ev_schedule), randomize), 'EV Charger')
    # --- Solar PV: -4 kW, 10 hours/day, output varies by day ---
    solar_power_profile = []
    solar_powers = [float(np.random.uniform(2, 3.5)) for _ in range(days)]
    for d in range(days):
        for t in range(steps_per_day):
            hour = t * timestep_hours
            if 7 <= hour < 17:
                solar_power_profile.append(-solar_powers[d])
            else:
                solar_power_profile.append(0)
    sim.add_load(ApplianceLoad("Solar PV", -1, fix_length(solar_power_profile), randomize), 'Solar')
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
                    # Season selector
                    dbc.RadioItems(
                        options=[
                            {"label": "Spring", "value": "spring"},
                            {"label": "Summer", "value": "summer"},
                            {"label": "Fall", "value": "fall"},
                            {"label": "Winter", "value": "winter"},
                        ],
                        value="summer",
                        id="season-radio",
                        inline=True,
                        labelClassName="me-3"
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
    # Main plots (all start empty)
    dbc.Row([
        dbc.Col(dcc.Graph(id="time-series-plot", figure={}), width=12)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id="pie-plot", figure={}), width=4),
        dbc.Col(dcc.Graph(id="sunburst-plot", figure={}), width=4),
        dbc.Col(dcc.Graph(id="bar-plot", figure={}), width=4)
    ])
], fluid=True)

# --- MAIN DASH CALLBACK ---
# Runs the simulation and updates all plots and analytics when the user clicks 'Run Simulation'.
@app.callback(
    [Output("time-series-plot", "figure"),
     Output("pie-plot", "figure"),
     Output("sunburst-plot", "figure"),
     Output("bar-plot", "figure"),
     Output("analytics-output", "children"),
     Output("warnings-output", "children")],
    [Input("run-btn", "n_clicks")],
    [State("randomize-toggle", "value"), State("season-radio", "value"), State("timestep-radio", "value"), State("period-radio", "value")]
)
def update_dashboard(n_clicks, randomize_value, season_value, timestep_value, period_value):
    if not n_clicks:
        raise dash.exceptions.PreventUpdate
    randomize = 1 in (randomize_value or [])
    timestep = float(timestep_value)
    period = int(period_value)
    season = season_value or "summer"
    df = run_simulation(randomize=randomize, timestep_hours=timestep, period_hours=period, season=season)
    # Get price_per_kwh for analytics
    if season == "summer":
        price_per_kwh = 9
    elif season == "winter":
        price_per_kwh = 10
    elif season == "spring":
        price_per_kwh = 8
    elif season == "fall":
        price_per_kwh = 8
    else:
        price_per_kwh = 9
    peak_hour, peak_subsystem, peak_value, shares, solar_pct, warnings, total_energy_kwh, _, recommendations = get_analytics(df, timestep)
    total_cost = total_energy_kwh * price_per_kwh
    analytics = [
        html.P(f"Peak load at hour {peak_hour}: {peak_value:.2f} kW ({peak_subsystem})"),
        html.P("Subsystem energy share (%):")
    ]
    # Hierarchical order for analytics
    def add_hierarchical_share(analytics, shares):
        hvac_children = ['Chiller', 'Pump', 'Fan']
        kitchen_children = ['Fridge', 'Dishwasher', 'Microwave', 'Oven']
        laundry_children = ['Washer', 'Dryer']
        entertainment_children = ['TV', 'Computer']
        ev_children = ['EV Charger']
        # HVAC and children
        hvac_total = sum(shares[c] for c in hvac_children if c in shares)
        if hvac_total > 0:
            analytics.append(html.Li(f"HVAC: {hvac_total:.1f}%"))
            for child in hvac_children:
                if child in shares:
                    analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
        # Kitchen and children
        kitchen_total = sum(shares[c] for c in kitchen_children if c in shares)
        if kitchen_total > 0:
            analytics.append(html.Li(f"Kitchen: {kitchen_total:.1f}%"))
            for child in kitchen_children:
                if child in shares:
                    analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
        # Laundry and children
        laundry_total = sum(shares[c] for c in laundry_children if c in shares)
        if laundry_total > 0:
            analytics.append(html.Li(f"Laundry: {laundry_total:.1f}%"))
            for child in laundry_children:
                if child in shares:
                    analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
        # Entertainment and children
        entertainment_total = sum(shares[c] for c in entertainment_children if c in shares)
        if entertainment_total > 0:
            analytics.append(html.Li(f"Entertainment: {entertainment_total:.1f}%"))
            for child in entertainment_children:
                if child in shares:
                    analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
        # EV Charging
        ev_total = sum(shares[c] for c in ev_children if c in shares)
        if ev_total > 0:
            analytics.append(html.Li(f"EV Charging: {ev_total:.1f}%"))
            for child in ev_children:
                if child in shares:
                    analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
        # Other top-level (do not list parents or children again)
        all_children = hvac_children + kitchen_children + laundry_children + entertainment_children + ev_children
        for k, v in shares.items():
            if k not in all_children:
                analytics.append(html.Li(f"{k}: {v:.1f}%"))
        return analytics
    analytics = add_hierarchical_share(analytics, shares)
    analytics.append(html.P(f"Solar offset: {solar_pct:.1f}% of total demand"))
    analytics.append(html.P(f"Total energy consumed: {total_energy_kwh:.1f} kWh"))
    analytics.append(html.P(f"Total cost: ₹{total_cost:,.0f} (₹{price_per_kwh}/kWh for {season.title()})"))
    analytics.append(html.P("Recommendations:"))
    analytics += [html.Li(rec) for rec in recommendations]
    warnings_div = [html.Div(w) for w in warnings] if warnings else ""
    # Return all updated dashboard elements
    return (
        get_time_series_fig(df),
        get_pie_share_fig(df, timestep),
        get_sunburst_share_fig(df, timestep),
        get_daily_bar_fig(df, timestep),
        analytics,
        warnings_div
    )

if __name__ == "__main__":
    app.run(debug=True) 
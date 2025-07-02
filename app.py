import dash
from dash import dcc, html, Output, Input
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

# Define realistic energy costs for each source and season
ENERGY_COSTS = {
    ("coal", "summer"): 9,
    ("coal", "winter"): 10,
    ("coal", "spring"): 8,
    ("coal", "fall"): 8,
    ("solar", "summer"): 4,
    ("solar", "winter"): 6,
    ("solar", "spring"): 5,
    ("solar", "fall"): 5,
    ("nuclear", "summer"): 6,
    ("nuclear", "winter"): 6,
    ("nuclear", "spring"): 6,
    ("nuclear", "fall"): 6,
    ("hydro", "summer"): 5,
    ("hydro", "winter"): 5,
    ("hydro", "spring"): 5,
    ("hydro", "fall"): 5,
    ("wind", "summer"): 5,
    ("wind", "winter"): 5,
    ("wind", "spring"): 5,
    ("wind", "fall"): 5,
}

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

def run_simulation(randomize=True, timestep_hours=1.0, period_hours=24, season="summer", hvac_setpoint=25, chiller_max_power=2.2):
    np.random.seed(42)
    sim = BuildingSimulator(timestep_hours=timestep_hours, period_hours=period_hours)
    days = int(period_hours / 24)
    steps_per_day = int(24 / timestep_hours)
    total_steps = int(period_hours / timestep_hours)
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
        lighting_factor = 1.3
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
    temp_profile = []
    for d in range(days):
        day_min = base_min + np.random.uniform(-1, 1)
        day_max = base_max + np.random.uniform(-2, 2)
        for t in range(steps_per_day):
            hour = t * timestep_hours
            temp = day_min + (day_max - day_min) * 0.5 * (1 + np.sin((hour - 15) / 24 * 2 * np.pi))
            temp_profile.append(temp)
    if hvac_mode == "cool":
        sim.add_load(HVACLoad("Chiller", temp_profile, setpoint=hvac_setpoint, max_power=chiller_max_power, alpha=0.07, mode='cool'), 'Chiller')
        sim.add_load(HVACLoad("Pump", temp_profile, setpoint=hvac_setpoint, max_power=0.15, alpha=0.07, mode='cool'), 'Pump')
        sim.add_load(HVACLoad("Fan", temp_profile, setpoint=hvac_setpoint, max_power=0.4, alpha=0.10, mode='cool'), 'Fan')
    elif hvac_mode == "heat":
        sim.add_load(HVACLoad("Chiller", temp_profile, setpoint=hvac_setpoint, max_power=chiller_max_power, alpha=0.07, mode='heat'), 'Chiller')
        sim.add_load(HVACLoad("Pump", temp_profile, setpoint=hvac_setpoint, max_power=0.15, alpha=0.07, mode='heat'), 'Pump')
        sim.add_load(HVACLoad("Fan", temp_profile, setpoint=hvac_setpoint, max_power=0.4, alpha=0.10, mode='heat'), 'Fan')
    else:
        sim.add_load(HVACLoad("Chiller", temp_profile, setpoint=hvac_setpoint, max_power=chiller_max_power, alpha=0.03, mode='cool'), 'Chiller')
        sim.add_load(HVACLoad("Pump", temp_profile, setpoint=hvac_setpoint, max_power=0.05, alpha=0.03, mode='cool'), 'Pump')
        sim.add_load(HVACLoad("Fan", temp_profile, setpoint=hvac_setpoint, max_power=0.2, alpha=0.05, mode='cool'), 'Fan')
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
    sim.add_load(ApplianceLoad("Fridge", 0.18, fix_length([1]*total_steps), randomize), 'Fridge')
    dw_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        dinner_hour = int(np.random.uniform(19, 21) / timestep_hours)
        arr[dinner_hour] = 1
        if d % 7 in [5, 6] and np.random.rand() < 0.5:
            breakfast_hour = int(np.random.uniform(7, 9) / timestep_hours)
            arr[breakfast_hour] = 1
        dw_schedule += arr
    sim.add_load(ApplianceLoad("Dishwasher", 1.2, fix_length(dw_schedule), randomize), 'Dishwasher')
    mw_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        for meal, window in [("breakfast", (7, 9)), ("lunch", (12, 14)), ("dinner", (18, 20))]:
            if np.random.rand() < 0.8:
                hour = int(np.random.uniform(*window) / timestep_hours)
                arr[hour] = 1
        mw_schedule += arr
    sim.add_load(ApplianceLoad("Microwave", 1.2, fix_length(mw_schedule), randomize), 'Microwave')
    oven_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        if np.random.rand() < (0.5 if d % 7 in [5, 6] else 0.2):
            hour = int(np.random.uniform(17, 20) / timestep_hours)
            arr[hour] = 1
        oven_schedule += arr
    sim.add_load(ApplianceLoad("Oven", 2.5, fix_length(oven_schedule), randomize), 'Oven')
    washer_schedule = []
    dryer_schedule = []
    for d in range(days):
        arr_w = [0]*steps_per_day
        arr_d = [0]*steps_per_day
        if d % 7 in [5, 6] or (np.random.rand() < 0.2):
            hour_w = int(np.random.uniform(10, 15) / timestep_hours)
            hour_d = hour_w + int(1/timestep_hours)
            arr_w[hour_w] = 1
            arr_d[hour_d % steps_per_day] = 1
        washer_schedule += arr_w
        dryer_schedule += arr_d
    sim.add_load(ApplianceLoad("Washer", 0.5, fix_length(washer_schedule), randomize), 'Washer')
    sim.add_load(ApplianceLoad("Dryer", 4, fix_length(dryer_schedule), randomize), 'Dryer')
    tv_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        evening_hours = range(int(18/timestep_hours), int(23/timestep_hours))
        hours_on = np.random.choice(list(evening_hours), size=np.random.randint(2, 5), replace=False)
        for h in hours_on:
            arr[h] = 1
        if d % 7 in [5, 6]:
            extra = np.random.choice(list(evening_hours), size=1)
            arr[extra[0]] = 1
        tv_schedule += arr
    sim.add_load(ApplianceLoad("TV", 0.15, fix_length(tv_schedule), randomize), 'TV')
    comp_schedule = []
    for d in range(days):
        arr = [0]*steps_per_day
        if d % 7 not in [5, 6]:
            for h in range(int(16/timestep_hours), int(22/timestep_hours)):
                if np.random.rand() < 0.5:
                    arr[h] = 1
        else:
            for h in range(int(16/timestep_hours), int(22/timestep_hours)):
                if np.random.rand() < 0.2:
                    arr[h] = 1
        comp_schedule += arr
    sim.add_load(ApplianceLoad("Computer", 0.1, fix_length(comp_schedule), randomize), 'Computer')
    ev_schedule = []
    ev_days = np.random.choice(range(days), min(3, days), replace=False)
    for d in range(days):
        arr = [0]*steps_per_day
        if d in ev_days:
            hour = int(np.random.uniform(22, 24) / timestep_hours)
            arr[hour] = 1
        ev_schedule += arr
    sim.add_load(ApplianceLoad("EV Charger", 7, fix_length(ev_schedule), randomize), 'EV Charger')
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
    consumption_cols = [col for col in df.columns if col not in ['Total', 'Solar'] and df[col].sum() > 0]
    total_energy_kwh = df[consumption_cols].sum().sum() * timestep_hours
    cost_per_kwh = 9
    total_cost = total_energy_kwh * cost_per_kwh
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

def add_hierarchical_share(analytics, shares):
    hvac_children = ['Chiller', 'Pump', 'Fan']
    kitchen_children = ['Fridge', 'Dishwasher', 'Microwave', 'Oven']
    laundry_children = ['Washer', 'Dryer']
    entertainment_children = ['TV', 'Computer']
    ev_children = ['EV Charger']
    hvac_total = sum(shares[c] for c in hvac_children if c in shares)
    if hvac_total > 0:
        analytics.append(html.Li(f"HVAC: {hvac_total:.1f}%"))
        for child in hvac_children:
            if child in shares:
                analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
    kitchen_total = sum(shares[c] for c in kitchen_children if c in shares)
    if kitchen_total > 0:
        analytics.append(html.Li(f"Kitchen: {kitchen_total:.1f}%"))
        for child in kitchen_children:
            if child in shares:
                analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
    laundry_total = sum(shares[c] for c in laundry_children if c in shares)
    if laundry_total > 0:
        analytics.append(html.Li(f"Laundry: {laundry_total:.1f}%"))
        for child in laundry_children:
            if child in shares:
                analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
    entertainment_total = sum(shares[c] for c in entertainment_children if c in shares)
    if entertainment_total > 0:
        analytics.append(html.Li(f"Entertainment: {entertainment_total:.1f}%"))
        for child in entertainment_children:
            if child in shares:
                analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
    ev_total = sum(shares[c] for c in ev_children if c in shares)
    if ev_total > 0:
        analytics.append(html.Li(f"EV Charging: {ev_total:.1f}%"))
        for child in ev_children:
            if child in shares:
                analytics.append(html.Ul([html.Li(f"{child}: {shares[child]:.1f}%")]))
    all_children = hvac_children + kitchen_children + laundry_children + entertainment_children + ev_children
    for k, v in shares.items():
        if k not in all_children:
            analytics.append(html.Li(f"{k}: {v:.1f}%"))
    return analytics

# --- DASH APP LAYOUT ---
app.layout = dbc.Container([
    html.H2("Building Energy Dashboard Simulator", className="text-center my-4"),
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("Simulation Controls"),
                dbc.CardBody([
                    dbc.Checklist(
                        options=[{"label": "Randomize Loads (+/-10%)", "value": 1}],
                        value=[1],
                        id="randomize-toggle",
                        switch=True,
                    ),
                    html.Br(),
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
                    html.Label("HVAC Setpoint (°C)", style={"marginTop": "10px"}),
                    dcc.Slider(
                        id="hvac-setpoint-slider",
                        min=18, max=28, step=0.5, value=25,
                        marks={i: str(i) for i in range(18, 29)},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                    html.Br(),
                    html.Label("Chiller Max Power (kW)", style={"marginTop": "10px"}),
                    dcc.Slider(
                        id="chiller-maxpower-slider",
                        min=1.0, max=4.0, step=0.1, value=2.2,
                        marks={i: str(i) for i in range(1, 5)},
                        tooltip={"placement": "bottom", "always_visible": False}
                    ),
                    html.Label("Energy Source", style={"marginTop": "10px"}),
                    dbc.RadioItems(
                        options=[
                            {"label": "Coal", "value": "coal"},
                            {"label": "Solar", "value": "solar"},
                            {"label": "Nuclear", "value": "nuclear"},
                            {"label": "Hydro", "value": "hydro"},
                            {"label": "Wind", "value": "wind"},
                        ],
                        value="coal",
                        id="energy-source-radio",
                        inline=True,
                        labelClassName="me-3"
                    ),
                ])
            ])
        ], width=3),
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
    dbc.Row([
        dbc.Col(dcc.Graph(id="time-series-plot", figure={}, style={'display': 'none'}), width=12)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id="pie-plot", figure={}, style={'display': 'none'}), width=4),
        dbc.Col(dcc.Graph(id="sunburst-plot", figure={}, style={'display': 'none'}), width=4),
        dbc.Col(dcc.Graph(id="bar-plot", figure={}, style={'display': 'none'}), width=4)
    ])
], fluid=True)

# --- MAIN DASH CALLBACK ---
@app.callback(
    [Output("time-series-plot", "figure"), Output("time-series-plot", "style"),
     Output("pie-plot", "figure"), Output("pie-plot", "style"),
     Output("sunburst-plot", "figure"), Output("sunburst-plot", "style"),
     Output("bar-plot", "figure"), Output("bar-plot", "style"),
     Output("analytics-output", "children"),
     Output("warnings-output", "children")],
    [
        Input("randomize-toggle", "value"),
        Input("season-radio", "value"),
        Input("timestep-radio", "value"),
        Input("period-radio", "value"),
        Input("hvac-setpoint-slider", "value"),
        Input("chiller-maxpower-slider", "value"),
        Input("energy-source-radio", "value")
    ]
)
def update_dashboard(randomize_value, season_value, timestep_value, period_value, hvac_setpoint, chiller_max_power, energy_source):
    randomize = 1 in (randomize_value or [])
    timestep = float(timestep_value)
    period = int(period_value)
    season = season_value or "summer"
    df = run_simulation(randomize=randomize, timestep_hours=timestep, period_hours=period, season=season, hvac_setpoint=hvac_setpoint, chiller_max_power=chiller_max_power)
    # Set cost per kWh based on energy source and season
    price_per_kwh = ENERGY_COSTS.get((energy_source, season), 8)
    peak_hour, peak_subsystem, peak_value, shares, solar_pct, warnings, total_energy_kwh, total_cost, recommendations = get_analytics(df, timestep)
    total_cost = total_energy_kwh * price_per_kwh
    recs = []
    if season == "summer":
        recs.append("Set HVAC to 26°C or higher to reduce cooling load in summer.")
    elif season == "winter":
        recs.append("Set HVAC to 20°C or lower to reduce heating load in winter.")
    elif season == "spring":
        recs.append("Take advantage of mild weather to minimize HVAC use.")
    elif season == "fall":
        recs.append("Use natural ventilation when possible in fall.")
    if energy_source == "coal":
        recs.append("Consider switching to renewable energy sources to reduce emissions.")
    elif energy_source == "nuclear":
        recs.append("Ensure regular safety checks for nuclear energy systems.")
    elif energy_source == "hydro":
        recs.append("Maintain hydro systems for optimal efficiency.")
    elif energy_source == "wind":
        recs.append("Schedule regular maintenance for wind turbines.")
    elif energy_source == "solar":
        recs.append("Keep solar panels clean and unobstructed for best performance.")
    for r in recommendations:
        if "solar" in r.lower() and energy_source != "solar":
            continue
        recs.append(r)
    analytics_output = [
        html.P(f"Peak load at hour {peak_hour}: {peak_value:.2f} kW ({peak_subsystem})"),
        html.P("Subsystem energy share (%):"),
        *add_hierarchical_share([], shares),
        html.P(f"Total energy consumed: {total_energy_kwh:.1f} kWh"),
        html.P(f"Total cost: ₹{total_cost:,.0f} (₹{price_per_kwh}/kWh, {energy_source.title()})"),
        html.P("Recommendations:"),
        html.Ul([html.Li(rec) for rec in recs])
    ]
    if energy_source == "solar" or ("Solar" in df.columns and df["Solar"].abs().sum() > 0):
        analytics_output.insert(4, html.P(f"Solar offset: {solar_pct:.1f}% of total demand"))
    return (
        get_time_series_fig(df), {},
        get_pie_share_fig(df, timestep), {},
        get_sunburst_share_fig(df, timestep), {},
        get_daily_bar_fig(df, timestep), {},
        analytics_output,
        [html.Div(w) for w in warnings] if warnings else ""
    )

if __name__ == "__main__":
    app.run(debug=True) 
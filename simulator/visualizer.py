import plotly.graph_objs as go
import plotly.io as pio
import pandas as pd

pio.templates.default = "plotly_dark"

# --- VISUALIZATION FUNCTIONS ---

def get_time_series_fig(df):
    """
    Returns a Plotly Figure for time-series of each subsystem.
    Each line shows the power profile (kW) for a subsystem over time.
    """
    fig = go.Figure()
    for col in df.columns:
        if col != 'Total':
            fig.add_trace(go.Scatter(x=df.index, y=df[col], mode='lines', name=col))
    fig.update_layout(title="Subsystem Energy Usage (Time Series)", xaxis_title="Hour", yaxis_title="kWh")
    return fig

def get_pie_share_fig(df, timestep_hours=1.0):
    """
    Returns a Plotly Figure for subsystem energy share pie chart.
    Only includes consumption subsystems (positive total energy, not 'Solar').
    Energy is in kWh, accounting for time step.
    """
    shares = df.drop('Total', axis=1).sum() * timestep_hours
    shares = shares[(shares > 0) & (shares.index != 'Solar')]
    fig = go.Figure(go.Pie(labels=shares.index, values=shares.values, hole=0.3))
    fig.update_layout(title="Subsystem Energy Share (%)")
    return fig

def get_daily_bar_fig(df, timestep_hours=1.0):
    """
    Returns a Plotly Figure for daily total energy bar chart.
    Energy is in kWh, accounting for time step.
    """
    df = df.copy()
    df['Total'] = df['Total'] * timestep_hours  # Convert to kWh per step
    df['Day'] = (df.index * timestep_hours // 24) + 1
    daily = df.groupby('Day')['Total'].sum()
    fig = go.Figure(go.Bar(x=daily.index, y=daily.values))
    fig.update_layout(title="Total Energy Consumption per Day", xaxis_title="Day", yaxis_title="kWh")
    return fig

# Example test visualization
if __name__ == "__main__":
    import numpy as np
    from simulator import BuildingSimulator
    np.random.seed(42)
    sim = BuildingSimulator()
    from models.hvac import HVACLoad
    from models.lighting import LightingLoad
    from models.appliances import ApplianceLoad
    sim.add_load(HVACLoad("Chiller", 50, [1]*8 + [0]*8 + [1]*8), 'HVAC')
    sim.add_load(LightingLoad("Office", 3, [0]*7 + [1]*10 + [0]*7), 'Lighting')
    sim.add_load(ApplianceLoad("Pump", 4, [0]*6 + [1]*12 + [0]*6), 'Appliances')
    df = sim.run()
    plot_time_series(df)
    plot_pie_share(df)
    plot_daily_bar(df) 
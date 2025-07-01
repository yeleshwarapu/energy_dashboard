import pandas as pd

# --- ANALYTICS FUNCTIONS ---

def find_peak_load(df):
    """
    Identify the hour and subsystem with the peak load.
    Returns (hour, subsystem, value).
    """
    peak_hour = df['Total'].idxmax()
    peak_value = df['Total'].max()
    subsystem = df.loc[peak_hour].drop('Total').idxmax()
    return peak_hour, subsystem, peak_value


def subsystem_share(df, timestep_hours=1.0):
    """
    Returns % share of total energy per consumption subsystem (excluding 'Total' and generation like 'Solar').
    Energy is in kWh, accounting for time step.
    """
    # Only include positive (consumption) subsystems, exclude 'Solar'
    consumption_cols = [col for col in df.columns if col not in ['Total', 'Solar'] and df[col].sum() > 0]
    # Total demand in kWh
    total_demand = df[consumption_cols].sum().sum() * timestep_hours
    # Share per subsystem
    shares = df[consumption_cols].sum() * timestep_hours / total_demand * 100 if total_demand > 0 else 0
    return shares


def solar_offset_pct(df, timestep_hours=1.0):
    """
    Returns % of total demand offset by solar generation.
    Energy is in kWh, accounting for time step.
    """
    if 'Solar' not in df.columns:
        return 0
    # Only include positive (consumption) subsystems, exclude 'Solar'
    consumption_cols = [col for col in df.columns if col not in ['Total', 'Solar'] and df[col].sum() > 0]
    total_demand = df[consumption_cols].sum().sum() * timestep_hours
    # Solar generation (make positive)
    solar_gen = -df['Solar'].sum() * timestep_hours
    return solar_gen / total_demand * 100 if total_demand > 0 else 0


def flag_inefficiencies(df, night_hours=range(0,7)):
    """
    Flags inefficiencies like high night-time HVAC draw.
    Returns list of warnings.
    """
    warnings = []
    if 'HVAC' in df.columns:
        night_hvac = df.loc[night_hours, 'HVAC'].sum()
        if night_hvac > 0.1 * df['HVAC'].sum():
            warnings.append("High night-time HVAC consumption detected.")
    return warnings

# --- EXAMPLE TEST ---
if __name__ == "__main__":
    from simulator import BuildingSimulator
    import numpy as np
    np.random.seed(42)
    sim = BuildingSimulator()
    from models.hvac import HVACLoad
    from models.lighting import LightingLoad
    from models.appliances import ApplianceLoad
    sim.add_load(HVACLoad("AC", 3, [0]*6 + [1]*2 + [0]*6 + [1]*4 + [0]*6), 'HVAC')
    sim.add_load(LightingLoad("Living Room", 0.2, [0]*17 + [1]*4 + [0]*3), 'Lighting')
    sim.add_load(ApplianceLoad("Fridge", 0.15, [1]*24), 'Appliances')
    sim.add_load(ApplianceLoad("Solar PV", -2, [0]*6 + [1]*12 + [0]*6), 'Solar')
    df = sim.run()
    print("Peak load:", find_peak_load(df))
    print("Subsystem share (%):\n", subsystem_share(df, 1.0))
    print("Solar offset %:", solar_offset_pct(df, 1.0))
    print("Inefficiency flags:", flag_inefficiencies(df)) 
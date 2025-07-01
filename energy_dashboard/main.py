import numpy as np
from simulator.simulator import BuildingSimulator
from simulator.models.hvac import HVACLoad
from simulator.models.lighting import LightingLoad
from simulator.models.appliances import ApplianceLoad
from simulator.analytics import find_peak_load, subsystem_share, flag_inefficiencies
from simulator.visualizer import plot_time_series, plot_pie_share, plot_daily_bar

if __name__ == "__main__":
    np.random.seed(42)
    sim = BuildingSimulator(timestep_hours=1, period_hours=24)
    # Add test loads
    sim.add_load(HVACLoad("Chiller", 50, [1]*8 + [0]*8 + [1]*8), 'HVAC')
    sim.add_load(HVACLoad("Fan", 5, [1]*24), 'HVAC')
    sim.add_load(LightingLoad("Office", 3, [0]*7 + [1]*10 + [0]*7), 'Lighting')
    sim.add_load(LightingLoad("Hallway", 1, [1]*24), 'Lighting')
    sim.add_load(LightingLoad("External", 2, [0]*18 + [1]*6), 'Lighting')
    sim.add_load(ApplianceLoad("Pump", 4, [0]*6 + [1]*12 + [0]*6), 'Appliances')
    sim.add_load(ApplianceLoad("Computer", 0.5, [0]*8 + [1]*10 + [0]*6), 'Appliances')
    df = sim.run()

    # Analytics
    peak_hour, peak_subsystem, peak_value = find_peak_load(df)
    print(f"Peak load at hour {peak_hour}: {peak_value:.2f} kW ({peak_subsystem})")
    print("Subsystem energy share (%):\n", subsystem_share(df))
    for warning in flag_inefficiencies(df):
        print("Warning:", warning)

    # Visualization
    plot_time_series(df)
    plot_pie_share(df)
    plot_daily_bar(df) 
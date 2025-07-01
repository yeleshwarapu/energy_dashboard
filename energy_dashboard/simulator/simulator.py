import numpy as np
import pandas as pd
from .models.hvac import HVACLoad
from .models.lighting import LightingLoad
from .models.appliances import ApplianceLoad

# --- SIMULATION ENGINE ---

class BuildingSimulator:
    """
    Coordinates all load models, runs simulation, aggregates results.
    """
    def __init__(self, timestep_hours=1.0, period_hours=24):
        # Time step in hours (e.g., 1.0 for hourly, 0.25 for 15-min)
        self.timestep_hours = timestep_hours
        # Total simulation period in hours (e.g., 24 for 1 day, 168 for 7 days)
        self.period_hours = period_hours
        # Number of time steps in the simulation
        self.timesteps = int(period_hours / timestep_hours)
        # List of (load, subsystem) tuples
        self.loads = []

    def add_load(self, load, subsystem):
        """
        Add a load model to the simulation under a given subsystem name.
        """
        self.loads.append((load, subsystem))

    def run(self):
        """
        Run the simulation: aggregate all subsystem loads over the simulation period.
        Returns a DataFrame with each subsystem and the total load per time step.
        """
        data = {}
        for load, subsystem in self.loads:
            profile = load.simulate()
            # Ensure all subsystem arrays are float for correct aggregation
            if subsystem not in data:
                data[subsystem] = profile.astype(float)
            else:
                data[subsystem] += profile
        # Create DataFrame: each column is a subsystem, each row is a time step
        df = pd.DataFrame(data)
        df.index.name = 'Hour'
        # Add a 'Total' column for total load at each time step
        df['Total'] = df.sum(axis=1)
        return df

# --- EXAMPLE TEST ---
if __name__ == "__main__":
    np.random.seed(42)
    sim = BuildingSimulator(timestep_hours=1, period_hours=24)
    # Add example loads
    sim.add_load(HVACLoad("Chiller", 50, [1]*8 + [0]*8 + [1]*8), 'HVAC')
    sim.add_load(HVACLoad("Fan", 5, [1]*24), 'HVAC')
    sim.add_load(LightingLoad("Office", 3, [0]*7 + [1]*10 + [0]*7), 'Lighting')
    sim.add_load(LightingLoad("Hallway", 1, [1]*24), 'Lighting')
    sim.add_load(LightingLoad("External", 2, [0]*18 + [1]*6), 'Lighting')
    sim.add_load(ApplianceLoad("Pump", 4, [0]*6 + [1]*12 + [0]*6), 'Appliances')
    sim.add_load(ApplianceLoad("Computer", 0.5, [0]*8 + [1]*10 + [0]*6), 'Appliances')
    df = sim.run()
    print(df) 
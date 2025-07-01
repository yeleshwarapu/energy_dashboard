# Lighting load model for the building/home simulation
import numpy as np
import pandas as pd

class LightingLoad:
    """
    Represents a lighting load (e.g., room, area).
    Each instance models a single lighting circuit with a given power rating and schedule.
    """
    def __init__(self, name, power_kw, schedule, randomize=True):
        """
        name: str, name of the lighting circuit
        power_kw: float, power rating in kW
        schedule: list/array of 0/1 (off/on) for each time step
        """
        self.name = name
        self.power_kw = power_kw
        self.schedule = np.array(schedule)
        self.randomize = randomize

    def simulate(self):
        """
        Returns the power profile (kW) for each time step, based on the schedule.
        """
        base = self.power_kw * self.schedule
        if self.randomize:
            variation = np.random.uniform(0.9, 1.1, size=base.shape)
            base = base * variation
        return base

# Example test data for 24 hours, 1-hour steps
if __name__ == "__main__":
    np.random.seed(42)
    office = LightingLoad("Office", 3, [0]*7 + [1]*10 + [0]*7)
    hallway = LightingLoad("Hallway", 1, [1]*24)
    external = LightingLoad("External", 2, [0]*18 + [1]*6)
    df = pd.DataFrame({
        "Office": office.simulate(),
        "Hallway": hallway.simulate(),
        "External": external.simulate()
    })
    print(df) 
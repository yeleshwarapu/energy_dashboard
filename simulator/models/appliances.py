# Appliance load model for the building/home simulation
import numpy as np
import pandas as pd

class ApplianceLoad:
    """
    Represents a generic appliance load (e.g., fridge, oven, EV charger).
    Each instance models a single appliance with a given power rating and schedule.
    """
    def __init__(self, name, power_kw, schedule, randomize=True):
        """
        name: str, name of the appliance
        power_kw: float, power rating in kW (negative for generation, e.g., solar)
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
    pump = ApplianceLoad("Pump", 4, [0]*6 + [1]*12 + [0]*6)
    computer = ApplianceLoad("Computer", 0.5, [0]*8 + [1]*10 + [0]*6)
    df = pd.DataFrame({
        "Pump": pump.simulate(),
        "Computer": computer.simulate()
    })
    print(df) 
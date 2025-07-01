# HVAC load model for the building/home simulation
import numpy as np
import pandas as pd

class HVACLoad:
    """
    Represents an HVAC (Heating, Ventilation, and Air Conditioning) load.
    Power draw is based on outdoor temperature and thermostat setpoint.
    """
    def __init__(self, name, temperature_profile, setpoint=24, max_power=4.0, alpha=0.1):
        """
        name: str, name of the HVAC unit
        temperature_profile: array-like, outdoor temperature for each time step (°C)
        setpoint: float, thermostat setpoint (°C)
        max_power: float, maximum power draw (kW)
        alpha: float, scaling factor for duty cycle per degree above setpoint
        """
        self.name = name
        self.temperature_profile = np.array(temperature_profile)
        self.setpoint = setpoint
        self.max_power = max_power
        self.alpha = alpha

    def simulate(self):
        """
        Returns the power profile (kW) for each time step, based on temperature and setpoint.
        If temperature <= setpoint: power = 0.
        If temperature > setpoint: power = max_power * min(1, alpha * (T_out - setpoint)).
        """
        delta = self.temperature_profile - self.setpoint
        duty_cycle = np.clip(self.alpha * delta, 0, 1)
        return self.max_power * duty_cycle

# Example test data for 24 hours, 1-hour steps
if __name__ == "__main__":
    np.random.seed(42)
    chiller = HVACLoad("Chiller", [20]*8 + [25]*8 + [20]*8)
    fan = HVACLoad("Fan", [20]*24)
    chiller_profile = chiller.simulate()
    fan_profile = fan.simulate()
    df = pd.DataFrame({"Chiller": chiller_profile, "Fan": fan_profile})
    print(df) 
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class ManualController:
    """
    Contrôleur de chauffage "Ouvrier" (Manuel) basique basé sur des seuils de température absolus.
    N'a aucune prescience des prix de l'électricité ou de la météo future.
    """
    def __init__(self, target_temp=20.0, trigger_delta=0.5):
        self.target_temp = target_temp
        self.trigger_delta = trigger_delta
        
    async def optimize(self, current_temp: float) -> dict:
        """
        Si la température est sous un certain seuil, allume le chauffage à fond.
        Si la température est au-dessus du plafond, l'éteint complètement.
        Sinon (dans la zone morte), il maintient son état précédent (simplifié ici par juste OFF car il surchauffe rapidement).
        """
        # Hystérésis classique de thermostat manuel
        if current_temp < (self.target_temp - self.trigger_delta):
            valve_position = 100
            planned_power = settings.SIM_HEATER_MAX_POWER
        elif current_temp > (self.target_temp + self.trigger_delta):
            valve_position = 0
            planned_power = 0
        else:
             # Dans un vrai thermostat il maintient l'état précédent. 
             # Pour simplifier on coupe si on est dans la zone de confort.
             valve_position = 0
             planned_power = 0
             
        # logger.debug(f"Manual Control - T={current_temp:.2f}C -> Valve={valve_position}%")
             
        return {"valve_position": valve_position, "planned_power": planned_power}

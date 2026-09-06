from .models import Baseline, Observation

PRODUCTION_ID = "glass-house"
SCENE_ID = "28"

def scene_28_baselines() -> list[Baseline]:
    return [
        Baseline(PRODUCTION_ID, SCENE_ID, "maya", "prop.mug.hand", "right", "S28-T31"),
        Baseline(PRODUCTION_ID, SCENE_ID, "maya", "wardrobe.jacket.state", "zipped", "S28-T31"),
        Baseline(PRODUCTION_ID, SCENE_ID, "set-lamp-a", "set.practical_lamp.state", "on", "S28-T31"),
    ]

def take_47_observations() -> list[Observation]:
    return [
        Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "maya", "prop.mug.hand", "left", 0.96, 4200, 8200),
        Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "maya", "wardrobe.jacket.state", "open", 0.93, 1500, 9000),
        Observation(PRODUCTION_ID, SCENE_ID, "S28-T47", "set-lamp-a", "set.practical_lamp.state", "off", 0.68, 1200, 9000),
    ]

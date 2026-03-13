from __future__ import annotations

import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "game_config.json")

try:
    with open(_CONFIG_PATH) as _f:
        _loaded = json.load(_f)
        _CONFIG: dict = _loaded if isinstance(_loaded, dict) else {}
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"[config_loader] Failed to load game_config.json: {e}, using defaults")
    _CONFIG = {"items": [], "mobs": [], "zones": []}

ITEMS_BY_NAME: dict[str, dict] = {
    item["name"]: item for item in _CONFIG.get("items", [])
}
MOBS: list[dict] = _CONFIG.get("mobs", [])
ZONES: list[dict] = _CONFIG.get("zones", [])

# Fallback defaults if config is empty
if not ZONES:
    ZONES = [
        {"name": "Peaceful Meadow", "danger": 1, "monster_types": ["beast"]},
        {
            "name": "Whispering Woods",
            "danger": 2,
            "monster_types": ["humanoid", "beast"],
        },
        {"name": "Dark Forest", "danger": 3, "monster_types": ["undead", "humanoid"]},
        {"name": "Cursed Swamp", "danger": 4, "monster_types": ["humanoid", "beast"]},
        {
            "name": "Dragon's Peak",
            "danger": 5,
            "monster_types": ["elemental", "dragon", "humanoid"],
        },
    ]


def get_mobs_for_zone(zone_name: str) -> list[dict]:
    zone = get_zone(zone_name)
    if not zone:
        return MOBS[:3] if MOBS else []
    return [
        m
        for m in MOBS
        if m["type"] in zone["monster_types"] and m["tier"] == zone["danger"]
    ]


def get_item(name: str) -> dict | None:
    return ITEMS_BY_NAME.get(name)


def get_loot_for_mob(mob_name: str) -> list[dict]:
    mob = next((m for m in MOBS if m["name"] == mob_name), None)
    if not mob:
        return []
    return [
        ITEMS_BY_NAME[name] for name in mob.get("loot", []) if name in ITEMS_BY_NAME
    ]


def get_zone(name: str) -> dict | None:
    return next((z for z in ZONES if z["name"] == name), None)


BOSSES: list[dict] = _CONFIG.get("bosses", [])
for _boss in BOSSES:
    _boss["phases"] = sorted(
        _boss.get("phases", []), key=lambda p: p["threshold"], reverse=True
    )
_BOSSES_BY_ZONE: dict[str, dict] = {b["zone"]: b for b in BOSSES}
_BOSSES_BY_NAME: dict[str, dict] = {b["name"]: b for b in BOSSES}

NPCS: list[dict] = _CONFIG.get("npcs", [])
EXPEDITION_DESTINATIONS: list[dict] = _CONFIG.get("expedition_destinations", [])
BASE_TIERS: list[dict] = _CONFIG.get("base_tiers", [])
_BASE_TIERS_BY_TIER: dict[int, dict] = {t["tier"]: t for t in BASE_TIERS}
DAY_NIGHT: dict = _CONFIG.get("day_night", {})
INTENT_CONFIG: dict = _CONFIG.get("player_intent", {})


def get_base_tier(tier: int) -> dict | None:
    return _BASE_TIERS_BY_TIER.get(tier)


def get_next_base_tier(current_tier: int) -> dict | None:
    return _BASE_TIERS_BY_TIER.get(current_tier + 1)


def get_npcs_for_zone(zone_name: str) -> list[dict]:
    return [n for n in NPCS if n["zone"] == zone_name]


def get_npcs_in_zone(zone_name: str, npc_world: dict) -> list[dict]:
    """Get NPCs currently in a zone, using runtime state with config fallback."""
    result = []
    for npc in NPCS:
        current = npc_world.get(npc["name"], {}).get("current_zone", npc["zone"])
        if current == zone_name:
            result.append(npc)
    return result


def get_boss_for_zone(zone_name: str) -> dict | None:
    return _BOSSES_BY_ZONE.get(zone_name)


def get_boss_loot(boss_name: str) -> list[dict]:
    boss = _BOSSES_BY_NAME.get(boss_name)
    if not boss:
        return []
    return [
        ITEMS_BY_NAME[name] for name in boss.get("loot", []) if name in ITEMS_BY_NAME
    ]


def get_expedition_destination(risk_max: int) -> dict | None:
    import random as _rng

    candidates = [d for d in EXPEDITION_DESTINATIONS if d["risk"] <= risk_max]
    if not candidates:
        return EXPEDITION_DESTINATIONS[0] if EXPEDITION_DESTINATIONS else None
    return _rng.choice(candidates)

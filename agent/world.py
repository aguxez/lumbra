from __future__ import annotations

import random

from config_loader import (
    ZONES,
    get_item,
    get_loot_for_mob,
    get_mobs_for_zone,
)
from game_state import Enemy

QUEST_TEMPLATES = [
    {"desc": "Kill {n} {monster}s", "type": "kill"},
    {"desc": "Defeat {n} {monster}s in the {zone}", "type": "kill"},
    {"desc": "Clear {n} {monster}s from the area", "type": "kill"},
]

EXPLORATION_EVENTS = [
    "You find a hidden path through the undergrowth.",
    "A cool breeze carries the scent of wildflowers.",
    "You discover ancient ruins covered in moss.",
    "A mysterious merchant offers you a wave before vanishing.",
    "You rest by a stream and feel refreshed.",
    "Strange markings on a tree catch your eye.",
    "You hear distant thunder rumbling beyond the hills.",
    "A flock of birds takes flight as you pass.",
    "You spot footprints leading deeper into the wilderness.",
    "The air shimmers with faint magical energy.",
]


def roll_encounter(zone_name: str) -> Enemy | None:
    if random.random() < 0.6:
        monsters = get_mobs_for_zone(zone_name)
        if not monsters:
            return None
        m = random.choice(monsters)
        return Enemy(
            name=m["name"],
            hp=m["hp"],
            max_hp=m["hp"],
            attack=m["attack"],
            defense=m["defense"],
        )
    return None


def pick_next_zone(current_zone: str, character_attack: int) -> str:
    current_idx = next((i for i, z in enumerate(ZONES) if z["name"] == current_zone), 0)
    if character_attack >= (current_idx + 1) * 5 and current_idx < len(ZONES) - 1:
        return ZONES[current_idx + 1]["name"]
    return current_zone


def generate_hardcoded_quest(zone_name: str) -> dict:
    monsters = get_mobs_for_zone(zone_name)
    if not monsters:
        monsters = get_mobs_for_zone("Peaceful Meadow")
    monster = random.choice(monsters)
    n = random.randint(3, 6)
    template = random.choice(QUEST_TEMPLATES)
    desc = template["desc"].format(n=n, monster=monster["name"], zone=zone_name)
    loot_items = get_loot_for_mob(monster["name"])
    reward_item = (
        random.choice(loot_items)["name"]
        if loot_items and random.random() < 0.5
        else None
    )
    zone_idx = next((i for i, z in enumerate(ZONES) if z["name"] == zone_name), 0)
    return {
        "description": desc,
        "target": monster["name"],
        "goal": n,
        "reward_xp": n * 15 + zone_idx * 10,
        "reward_item": reward_item,
    }


def get_exploration_event() -> str:
    return random.choice(EXPLORATION_EVENTS)


def roll_loot(mob_name: str) -> dict | None:
    if random.random() < 0.2:
        loot_items = get_loot_for_mob(mob_name)
        if loot_items:
            return random.choice(loot_items)
    return None

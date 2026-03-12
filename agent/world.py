import random
from game_state import Enemy

ZONES = [
    {"name": "Peaceful Meadow", "danger": 1},
    {"name": "Whispering Woods", "danger": 2},
    {"name": "Dark Forest", "danger": 3},
    {"name": "Cursed Swamp", "danger": 4},
    {"name": "Dragon's Peak", "danger": 5},
]

MONSTER_TABLE: dict[str, list[dict]] = {
    "Peaceful Meadow": [
        {"name": "Slime", "hp": 10, "attack": 3, "defense": 1},
        {"name": "Field Rat", "hp": 8, "attack": 4, "defense": 1},
        {"name": "Wild Chicken", "hp": 6, "attack": 2, "defense": 0},
    ],
    "Whispering Woods": [
        {"name": "Goblin", "hp": 15, "attack": 6, "defense": 2},
        {"name": "Wolf", "hp": 18, "attack": 7, "defense": 3},
        {"name": "Forest Spider", "hp": 12, "attack": 8, "defense": 1},
    ],
    "Dark Forest": [
        {"name": "Skeleton", "hp": 22, "attack": 9, "defense": 4},
        {"name": "Dark Elf", "hp": 25, "attack": 10, "defense": 5},
        {"name": "Troll", "hp": 35, "attack": 8, "defense": 7},
    ],
    "Cursed Swamp": [
        {"name": "Swamp Witch", "hp": 28, "attack": 12, "defense": 4},
        {"name": "Bog Beast", "hp": 40, "attack": 10, "defense": 8},
        {"name": "Poison Drake", "hp": 32, "attack": 14, "defense": 5},
    ],
    "Dragon's Peak": [
        {"name": "Fire Elemental", "hp": 35, "attack": 15, "defense": 6},
        {"name": "Wyvern", "hp": 45, "attack": 13, "defense": 9},
        {"name": "Ancient Dragon", "hp": 60, "attack": 18, "defense": 12},
        {"name": "Dragon Knight", "hp": 50, "attack": 16, "defense": 10},
    ],
}

LOOT_TABLE: dict[str, list[dict]] = {
    "Peaceful Meadow": [
        {"name": "Wooden Shield", "rarity": "common"},
        {"name": "Healing Herb", "rarity": "common"},
    ],
    "Whispering Woods": [
        {"name": "Iron Sword", "rarity": "common"},
        {"name": "Leather Armor", "rarity": "common"},
        {"name": "Forest Amulet", "rarity": "uncommon"},
    ],
    "Dark Forest": [
        {"name": "Steel Blade", "rarity": "uncommon"},
        {"name": "Iron Shield", "rarity": "uncommon"},
        {"name": "Shadow Cloak", "rarity": "rare"},
    ],
    "Cursed Swamp": [
        {"name": "Venom Dagger", "rarity": "uncommon"},
        {"name": "Swamp Boots", "rarity": "uncommon"},
        {"name": "Witch's Staff", "rarity": "rare"},
    ],
    "Dragon's Peak": [
        {"name": "Dragon Scale Armor", "rarity": "rare"},
        {"name": "Flame Sword", "rarity": "rare"},
        {"name": "Dragon's Heart", "rarity": "legendary"},
    ],
}

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
        monsters = MONSTER_TABLE.get(zone_name, MONSTER_TABLE["Peaceful Meadow"])
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
    current_idx = next(
        (i for i, z in enumerate(ZONES) if z["name"] == current_zone), 0
    )
    if character_attack >= (current_idx + 1) * 5 and current_idx < len(ZONES) - 1:
        return ZONES[current_idx + 1]["name"]
    return current_zone


def generate_hardcoded_quest(zone_name: str) -> dict:
    monsters = MONSTER_TABLE.get(zone_name, MONSTER_TABLE["Peaceful Meadow"])
    monster = random.choice(monsters)
    n = random.randint(3, 6)
    template = random.choice(QUEST_TEMPLATES)
    desc = template["desc"].format(n=n, monster=monster["name"], zone=zone_name)
    loot = LOOT_TABLE.get(zone_name, LOOT_TABLE["Peaceful Meadow"])
    reward_item = random.choice(loot)["name"] if random.random() < 0.5 else None
    return {
        "description": desc,
        "target": monster["name"],
        "goal": n,
        "reward_xp": n * 15 + (ZONES.index(next(z for z in ZONES if z["name"] == zone_name))) * 10,
        "reward_item": reward_item,
    }


def get_exploration_event() -> str:
    return random.choice(EXPLORATION_EVENTS)


def roll_loot(zone_name: str) -> dict | None:
    if random.random() < 0.2:
        loot = LOOT_TABLE.get(zone_name, LOOT_TABLE["Peaceful Meadow"])
        return random.choice(loot)
    return None

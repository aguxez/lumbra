from __future__ import annotations

import random

from config_loader import (
    EXPEDITION_DESTINATIONS,
    ZONES,
    get_expedition_destination,
    get_item,
    get_loot_for_mob,
    get_mobs_for_zone,
    get_npcs_for_zone,
)
from game_state import ActiveBuff, Enemy, Expedition, InventoryItem, NPCEncounter

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


# --- NPC System ---

NPC_DIALOGUE_FALLBACKS = {
    "merchant": [
        "I have wares if you have coin... or something to trade.",
        "Business is slow out here. Care to browse?",
        "Every adventurer needs supplies. Take a look.",
    ],
    "sage": [
        "The stars whisper of great change ahead.",
        "Knowledge is the sharpest blade, traveler.",
        "I sense potential within you. Let me share what I know.",
    ],
    "blacksmith": [
        "Steel sings when shaped by a worthy hand.",
        "I can temper your resolve... and your weapons.",
        "Bring me materials and I'll forge something fine.",
    ],
    "wanderer": [
        "The road is long, but the company is welcome.",
        "I've seen things in these lands you wouldn't believe.",
        "Stay sharp out there, friend.",
    ],
}


def _get_npc_dialogue(npc: dict) -> str:
    role = npc.get("role", "wanderer")
    lines = NPC_DIALOGUE_FALLBACKS.get(role, NPC_DIALOGUE_FALLBACKS["wanderer"])
    return random.choice(lines)


def roll_npc_encounter(state) -> NPCEncounter | None:
    if state.combat:
        return None
    if random.random() > 0.30:
        return None

    npcs = get_npcs_for_zone(state.zone)
    if not npcs:
        return None

    npc = random.choice(npcs)
    npc_name = npc["name"]
    affinity = state.npc_relationships.get(npc_name, 0)

    dialogue = _get_npc_dialogue(npc)

    # Pick interaction based on affinity
    if affinity >= 30 and npc.get("trades"):
        trade = random.choice(npc["trades"])
        interaction_type = "trade"
        encounter = NPCEncounter(
            npc_name=npc_name,
            npc_role=npc["role"],
            dialogue=dialogue,
            interaction_type=interaction_type,
            offer_item=trade["offer"],
            request_item=trade.get("request"),
        )
    elif affinity >= 15 and npc.get("buffs"):
        buff = random.choice(npc["buffs"])
        interaction_type = "buff"
        encounter = NPCEncounter(
            npc_name=npc_name,
            npc_role=npc["role"],
            dialogue=dialogue,
            interaction_type=interaction_type,
            buff_type=buff["type"],
            buff_value=buff["value"],
            buff_ticks=buff["ticks"],
        )
    else:
        interaction_type = "lore"
        encounter = NPCEncounter(
            npc_name=npc_name,
            npc_role=npc["role"],
            dialogue=dialogue,
            interaction_type=interaction_type,
        )

    # Increase affinity
    state.npc_relationships[npc_name] = affinity + 5

    return encounter


def resolve_npc_interaction(state, encounter: NPCEncounter) -> list[str]:
    logs = []
    if encounter.interaction_type == "trade":
        # Check if player has the requested item (or request is None = free gift)
        if encounter.request_item:
            owned = next(
                (
                    i
                    for i in state.character.inventory
                    if i.name == encounter.request_item
                ),
                None,
            )
            if not owned:
                logs.append(
                    f"{encounter.npc_name} wanted "
                    f"{encounter.request_item}, "
                    "but you don't have it."
                )
                return logs
            state.character.inventory.remove(owned)
            logs.append(f"Gave {encounter.request_item} to {encounter.npc_name}.")

        # Add offered item
        if encounter.offer_item:
            item_data = get_item(encounter.offer_item)
            if item_data:
                item = InventoryItem.from_config(item_data)
            else:
                item = InventoryItem(name=encounter.offer_item)
            state.character.inventory.append(item)
            logs.append(f"Received {encounter.offer_item} from {encounter.npc_name}!")

    elif encounter.interaction_type == "buff":
        assert encounter.buff_type is not None
        buff = ActiveBuff(
            source=encounter.npc_name,
            buff_type=encounter.buff_type,
            value=encounter.buff_value,
            ticks_remaining=encounter.buff_ticks,
        )
        state.character.active_buffs.append(buff)
        logs.append(
            f"{encounter.npc_name} grants "
            f"+{encounter.buff_value} {encounter.buff_type} "
            f"for {encounter.buff_ticks} ticks!"
        )

    elif encounter.interaction_type == "lore":
        logs.append(f"{encounter.npc_name} shares ancient wisdom.")

    return logs


# --- Expedition System ---

EXPEDITION_EVENT_FALLBACKS = [
    "The scouts press deeper into uncharted territory.",
    "A faint glow illuminates the path ahead.",
    "The expedition encounters unusual rock formations.",
    "Strange sounds echo through the darkness.",
    "The scouts discover old campfire remains.",
    "A narrow passage opens into a vast chamber.",
    "The wind carries whispers from beyond the ridge.",
    "The expedition finds carved symbols on the walls.",
]


def create_expedition(zone_danger: int) -> Expedition | None:
    dest = get_expedition_destination(zone_danger)
    if not dest:
        return None

    dur_min, dur_max = dest["duration_range"]
    duration = random.randint(dur_min, dur_max)

    xp_min, xp_max = dest["xp_range"]
    reward_xp = random.randint(xp_min, xp_max)

    return Expedition(
        destination=dest["name"],
        description=dest.get("flavor", f"An expedition to {dest['name']}."),
        duration=duration,
        reward_xp=reward_xp,
        risk_level=dest["risk"],
    )


def resolve_expedition(expedition: Expedition) -> list[str]:
    logs = []
    risk = expedition.risk_level

    # Success chance decreases with risk: 75% at risk 1, 55% at risk 5
    success_chance = 0.75 - (risk - 1) * 0.05

    roll = random.random()

    # Find destination data for reward pool
    dest = next(
        (d for d in EXPEDITION_DESTINATIONS if d["name"] == expedition.destination),
        None,
    )
    reward_pool = dest["reward_pool"] if dest else []

    if roll < success_chance:
        # Full success
        num_items = random.randint(1, 2)
        if reward_pool:
            expedition.rewards = random.sample(
                reward_pool, min(num_items, len(reward_pool))
            )
        expedition.status = "completed"
        found = ", ".join(expedition.rewards) if expedition.rewards else "nothing"
        logs.append(
            f"Expedition to {expedition.destination} "
            f"succeeded! Found: {found}. "
            f"+{expedition.reward_xp} XP"
        )
    elif roll < success_chance + 0.15:
        # Partial success
        if reward_pool and random.random() < 0.5:
            expedition.rewards = [random.choice(reward_pool)]
        expedition.reward_xp = expedition.reward_xp // 2
        expedition.status = "completed"
        logs.append(
            f"Expedition to {expedition.destination} "
            f"partially succeeded. "
            f"+{expedition.reward_xp} XP"
        )
    else:
        # Failure
        expedition.rewards = []
        expedition.reward_xp = expedition.reward_xp // 4
        expedition.status = "failed"
        logs.append(
            f"Expedition to {expedition.destination} failed. "
            f"Scouts returned with little. "
            f"+{expedition.reward_xp} XP"
        )

    return logs


def get_expedition_event() -> str:
    return random.choice(EXPEDITION_EVENT_FALLBACKS)

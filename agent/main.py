import json
import random
import time

import requests

from combat import apply_stat_growth, resolve_round
from config_loader import ITEMS_BY_NAME, get_zone
from game_state import Combat, GameState, InventoryItem, Quest
from world import (
    create_expedition,
    generate_hardcoded_quest,
    get_expedition_event,
    get_exploration_event,
    pick_next_zone,
    resolve_expedition,
    resolve_npc_interaction,
    roll_encounter,
    roll_loot,
    roll_npc_encounter,
)


def auto_equip(character, item: InventoryItem):
    if item.item_type == "weapon" and item.attack > 0:
        current = next(
            (i for i in character.inventory if i.name == character.weapon), None
        )
        if not current or item.attack > current.attack:
            character.weapon = item.name
            return f"Equipped {item.name} as weapon! (+{item.attack} ATK)"
    elif item.item_type in ("armor", "shield") and item.defense > 0:
        current = next(
            (i for i in character.inventory if i.name == character.armor), None
        )
        if not current or item.defense > current.defense:
            character.armor = item.name
            return f"Equipped {item.name} as armor! (+{item.defense} DEF)"
    return None


SERVER_URL = "http://127.0.0.1:8234"
TICK_COMBAT = 6
TICK_EXPLORE = 12
TICK_IDLE = 15

# AI brain (loaded lazily in Phase 3)
ai_brain = None
tokenizer = None
model = None


def try_load_ai():
    global ai_brain, tokenizer, model
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        import ai_brain as _ai_brain

        model_id = "Qwen/Qwen3-0.6B"
        print(f"Loading {model_id}...")
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id)
        ai_brain = _ai_brain
        print("AI brain loaded.")
    except Exception as e:
        print(f"[warn] AI brain not available, using hardcoded decisions: {e}")


def get_combat_strategy(character_dict: dict, enemy_dict: dict) -> str:
    if ai_brain and tokenizer and model:
        return ai_brain.decide_combat_strategy(
            tokenizer, model, character_dict, enemy_dict
        )
    # Hardcoded fallback
    hp_pct = character_dict["hp"] / max(1, character_dict["max_hp"])
    if hp_pct < 0.2:
        return "flee"
    elif hp_pct < 0.4:
        return "defend"
    return "attack"


def get_quest(zone: str) -> dict:
    if ai_brain and tokenizer and model:
        return ai_brain.generate_quest(tokenizer, model, zone)
    return generate_hardcoded_quest(zone)


def get_exploration_text(zone: str) -> str:
    if ai_brain and tokenizer and model:
        return ai_brain.generate_exploration_event(tokenizer, model, zone)
    return get_exploration_event()


def get_npc_dialogue(
    npc_name: str, npc_role: str, zone: str, affinity: int
) -> str | None:
    if ai_brain and tokenizer and model:
        return ai_brain.generate_npc_dialogue(
            tokenizer, model, npc_name, npc_role, zone, affinity
        )
    return None


def get_expedition_text(destination: str, progress: int, duration: int) -> str | None:
    if ai_brain and tokenizer and model:
        return ai_brain.generate_expedition_event(
            tokenizer, model, destination, progress, duration
        )
    return None


def handle_death(state: GameState):
    state.character.hp = state.character.max_hp
    state.character.xp = max(0, int(state.character.xp * 0.9))
    state.zone = "Peaceful Meadow"
    state.combat = None
    state.quest = None
    state.add_log("You have fallen... You awaken in the Peaceful Meadow.")
    state.add_log(f"Lost 10% XP. Current XP: {state.character.xp}")


def tick_combat(state: GameState):
    combat = state.combat
    assert combat is not None
    strategy = get_combat_strategy(state.character.to_dict(), combat.to_dict())
    combat.ai_strategy = strategy

    logs = resolve_round(state.character, combat)
    for msg in logs:
        state.add_log(msg)

    if not state.character.is_alive():
        handle_death(state)
        return

    if not combat.enemy.is_alive():
        # Check if it was a flee (enemy HP zeroed as signal)
        if strategy == "flee":
            state.combat = None
            return

        # Victory
        growth_logs = apply_stat_growth(state.character)
        for msg in growth_logs:
            state.add_log(msg)

        # Quest progress
        if state.quest and state.quest.target == combat.enemy.name:
            state.quest.progress += 1
            state.add_log(f"Quest progress: {state.quest.progress}/{state.quest.goal}")

        # Loot drop
        loot = roll_loot(combat.enemy.name)
        if loot:
            item = InventoryItem.from_config(loot)
            state.character.inventory.append(item)
            state.add_log(f"Loot: {item.name} ({item.rarity})!")
            equip_msg = auto_equip(state.character, item)
            if equip_msg:
                state.add_log(equip_msg)

        state.combat = None


def tick_quest(state: GameState):
    # Roll for encounter
    enemy = roll_encounter(state.zone)
    if enemy:
        state.combat = Combat(enemy=enemy)
        state.add_log(f"A wild {enemy.name} appears!")
    else:
        # Try NPC encounter first
        encounter = roll_npc_encounter(state)
        if encounter:
            # Try AI dialogue
            affinity = state.npc_relationships.get(encounter.npc_name, 0)
            ai_dialogue = get_npc_dialogue(
                encounter.npc_name, encounter.npc_role, state.zone, affinity
            )
            if ai_dialogue:
                encounter.dialogue = ai_dialogue

            state.npc_encounter = encounter
            state.add_log(f"You meet {encounter.npc_name} ({encounter.npc_role}).")
            state.add_log(f'"{encounter.dialogue}"')

            # Resolve the interaction
            interaction_logs = resolve_npc_interaction(state, encounter)
            for msg in interaction_logs:
                state.add_log(msg)
        else:
            state.npc_encounter = None
            event = get_exploration_text(state.zone)
            state.add_log(event)


def tick_quest_complete(state: GameState):
    quest = state.quest
    assert quest is not None
    state.character.xp += quest.reward_xp
    state.add_log(f"Quest complete! Gained {quest.reward_xp} XP.")

    if quest.reward_item:
        item_data = ITEMS_BY_NAME.get(quest.reward_item)
        if item_data:
            item = InventoryItem.from_config(item_data, default_rarity="uncommon")
        else:
            item = InventoryItem(name=quest.reward_item, rarity="uncommon")
        state.character.inventory.append(item)
        state.add_log(f"Received: {quest.reward_item}!")
        equip_msg = auto_equip(state.character, item)
        if equip_msg:
            state.add_log(equip_msg)

    state.quest = None

    # Maybe launch an expedition on quest completion (25% chance)
    if random.random() < 0.25:
        zone_data = get_zone(state.zone)
        danger = zone_data["danger"] if zone_data else 1
        exp = create_expedition(danger)
        if exp and sum(1 for e in state.expeditions if e.status == "active") < 3:
            state.expeditions.append(exp)
            state.add_log(
                f"Scouts depart for {exp.destination}! "
                f"(risk {exp.risk_level}, "
                f"~{exp.duration} ticks)"
            )

    # Maybe move zones
    new_zone = pick_next_zone(state.zone, state.character.effective_attack)
    if new_zone != state.zone:
        state.zone = new_zone
        state.add_log(f"You venture into the {new_zone}!")


def tick_idle(state: GameState):
    quest_data = get_quest(state.zone)
    state.quest = Quest(**quest_data)
    state.add_log(f"New quest: {state.quest.description}")


def tick_buffs(state: GameState):
    expired = []
    for buff in state.character.active_buffs:
        buff.ticks_remaining -= 1
        if buff.ticks_remaining <= 0:
            expired.append(buff)
    for buff in expired:
        state.character.active_buffs.remove(buff)
        state.add_log(
            f"Buff from {buff.source} (+{buff.value} {buff.buff_type}) expired."
        )


def tick_expeditions(state: GameState):
    for exp in state.expeditions:
        if exp.status != "active":
            continue
        exp.progress += 1

        # Roll for flavor event (~30% chance)
        if random.random() < 0.30:
            ai_event = get_expedition_text(exp.destination, exp.progress, exp.duration)
            event = ai_event or get_expedition_event()
            exp.events.append(event)
            if len(exp.events) > 5:
                exp.events = exp.events[-5:]
            state.add_log(f"[{exp.destination}] {event}")

        # Check completion
        if exp.is_complete:
            logs = resolve_expedition(exp)
            for msg in logs:
                state.add_log(msg)
            # Grant XP and loot
            state.character.xp += exp.reward_xp
            for item_name in exp.rewards:
                item_data = ITEMS_BY_NAME.get(item_name)
                if item_data:
                    item = InventoryItem.from_config(item_data)
                    state.character.inventory.append(item)
                    equip_msg = auto_equip(state.character, item)
                    if equip_msg:
                        state.add_log(equip_msg)

    # Clean up finished expeditions (keep last 5 completed for history)
    state.expeditions = [e for e in state.expeditions if e.status == "active"]


def maybe_launch_expedition(state: GameState):
    active_count = sum(1 for e in state.expeditions if e.status == "active")
    if active_count >= 3:
        return
    if state.combat:
        return
    if random.random() > 0.10:
        return

    zone_data = get_zone(state.zone)
    danger = zone_data["danger"] if zone_data else 1
    exp = create_expedition(danger)
    if exp:
        state.expeditions.append(exp)
        state.add_log(
            f"Scouts depart for {exp.destination}! "
            f"(risk {exp.risk_level}, "
            f"~{exp.duration} ticks)"
        )


def send_state(state: GameState):
    payload = json.dumps(state.to_dict())
    try:
        response = requests.post(
            SERVER_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        return response.status_code
    except requests.ConnectionError:
        return None


def main():
    try_load_ai()

    state = GameState.load()
    char = state.character
    print(
        f"Game loaded: tick={state.tick}, zone={state.zone}, hp={char.hp}/{char.max_hp}"
    )

    while True:
        state.tick += 1
        state.log = []  # Fresh log per tick

        if state.combat:
            tick_combat(state)
            interval = TICK_COMBAT
        elif state.quest and state.quest.is_complete:
            tick_quest_complete(state)
            interval = TICK_EXPLORE
        elif state.quest:
            tick_quest(state)
            interval = TICK_EXPLORE
        else:
            tick_idle(state)
            interval = TICK_IDLE

        # Tick buffs and expeditions every tick
        tick_buffs(state)
        tick_expeditions(state)
        maybe_launch_expedition(state)

        # Clear NPC encounter if we're in combat now
        if state.combat:
            state.npc_encounter = None

        # Print tick summary
        char = state.character
        print(
            f"\n[tick {state.tick}] zone={state.zone} "
            f"hp={char.hp}/{char.max_hp} "
            f"atk={char.effective_attack} "
            f"def={char.effective_defense} "
            f"xp={char.xp}"
        )
        for msg in state.log:
            print(f"  {msg}")

        # Send to UI
        status = send_state(state)
        if status:
            print(f"  [sent] HTTP {status}")
        else:
            print("  [warn] UI not connected")

        # Save
        state.save()

        time.sleep(interval)


if __name__ == "__main__":
    main()

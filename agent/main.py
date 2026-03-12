import json
import time

import requests

from combat import apply_stat_growth, resolve_round
from config_loader import ITEMS_BY_NAME
from game_state import Combat, GameState, InventoryItem, Quest
from world import (
    generate_hardcoded_quest,
    get_exploration_event,
    pick_next_zone,
    roll_encounter,
    roll_loot,
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

        MODEL_ID = "Qwen/Qwen3-0.6B"
        print(f"Loading {MODEL_ID}...")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
        model = AutoModelForCausalLM.from_pretrained(MODEL_ID)
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
            item = InventoryItem(
                name=loot["name"],
                rarity=loot.get("rarity", "common"),
                item_type=loot.get("type", "accessory"),
                attack=loot.get("attack", 0),
                defense=loot.get("defense", 0),
                effect_type=loot.get("effect", {}).get("type")
                if loot.get("effect")
                else None,
                effect_value=loot.get("effect", {}).get("value", 0)
                if loot.get("effect")
                else 0,
            )
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
        event = get_exploration_text(state.zone)
        state.add_log(event)


def tick_quest_complete(state: GameState):
    quest = state.quest
    state.character.xp += quest.reward_xp
    state.add_log(f"Quest complete! Gained {quest.reward_xp} XP.")

    if quest.reward_item:
        item_data = ITEMS_BY_NAME.get(quest.reward_item)
        if item_data:
            item = InventoryItem(
                name=item_data["name"],
                rarity=item_data.get("rarity", "uncommon"),
                item_type=item_data.get("type", "accessory"),
                attack=item_data.get("attack", 0),
                defense=item_data.get("defense", 0),
                effect_type=item_data.get("effect", {}).get("type")
                if item_data.get("effect")
                else None,
                effect_value=item_data.get("effect", {}).get("value", 0)
                if item_data.get("effect")
                else 0,
            )
        else:
            item = InventoryItem(name=quest.reward_item, rarity="uncommon")
        state.character.inventory.append(item)
        state.add_log(f"Received: {quest.reward_item}!")
        equip_msg = auto_equip(state.character, item)
        if equip_msg:
            state.add_log(equip_msg)

    state.quest = None

    # Maybe move zones
    new_zone = pick_next_zone(state.zone, state.character.effective_attack)
    if new_zone != state.zone:
        state.zone = new_zone
        state.add_log(f"You venture into the {new_zone}!")


def tick_idle(state: GameState):
    quest_data = get_quest(state.zone)
    state.quest = Quest(**quest_data)
    state.add_log(f"New quest: {state.quest.description}")


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
    print(
        f"Game loaded: tick={state.tick}, zone={state.zone}, hp={state.character.hp}/{state.character.max_hp}"
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

        # Print tick summary
        print(
            f"\n[tick {state.tick}] zone={state.zone} hp={state.character.hp}/{state.character.max_hp} atk={state.character.effective_attack} def={state.character.effective_defense} xp={state.character.xp}"
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

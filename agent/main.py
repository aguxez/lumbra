import json
import random
import time

import requests

from combat import apply_stat_growth, resolve_round
from config_loader import (
    DAY_NIGHT,
    INTENT_CONFIG,
    ITEMS_BY_NAME,
    get_base_tier,
    get_next_base_tier,
    get_zone,
)
from game_state import (
    MAX_CONSUMABLE_PER_TYPE,
    ActiveBuff,
    Combat,
    GameState,
    InventoryItem,
    Quest,
)
from npc_autonomy import tick_npc_movement
from player_intent import generate_intent
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


def equip_or_stash(character, item: InventoryItem) -> list[str]:
    """Route an item to equipment slots or inventory. Returns log messages."""
    logs = []

    if item.item_type == "weapon":
        current = character.equipped_weapon
        if not current:
            character.equipped_weapon = item
            logs.append(f"Equipped {item.name} as weapon! (+{item.attack} ATK)")
        elif item.attack > current.attack:
            logs.append(
                f"Replaced {current.name} with {item.name}! (+{item.attack} ATK)"
            )
            character.equipped_weapon = item
        else:
            logs.append(f"Discarded {item.name} (weaker than {current.name}).")
        return logs

    if item.item_type in ("armor", "shield"):
        current = character.equipped_armor
        if not current:
            character.equipped_armor = item
            logs.append(f"Equipped {item.name} as armor! (+{item.defense} DEF)")
        elif item.defense > current.defense:
            logs.append(
                f"Replaced {current.name} with {item.name}! (+{item.defense} DEF)"
            )
            character.equipped_armor = item
        else:
            logs.append(f"Discarded {item.name} (weaker than {current.name}).")
        return logs

    if item.item_type == "accessory":
        current = character.equipped_accessory
        if not current:
            character.equipped_accessory = item
            stat = f"+{item.attack} ATK" if item.attack else f"+{item.defense} DEF"
            logs.append(f"Equipped {item.name} as accessory! ({stat})")
        else:
            new_power = item.attack + item.defense
            old_power = current.attack + current.defense
            if new_power > old_power:
                logs.append(f"Replaced {current.name} with {item.name}!")
                character.equipped_accessory = item
            else:
                logs.append(f"Discarded {item.name} (weaker than {current.name}).")
        return logs

    # Consumable or other item → inventory with cap
    if item.item_type == "consumable":
        count = sum(1 for i in character.inventory if i.name == item.name)
        if count >= MAX_CONSUMABLE_PER_TYPE:
            logs.append(
                f"Inventory full for {item.name} "
                f"(max {MAX_CONSUMABLE_PER_TYPE}). Discarded."
            )
            return logs

    character.inventory.append(item)
    logs.append(f"Stashed {item.name} in inventory.")
    return logs


SERVER_URL = "http://127.0.0.1:8234"
TICK_COMBAT = 6
TICK_EXPLORE = 12
TICK_IDLE = 15
TICK_BASE = 8

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


def _intent_log(state: GameState, intent):
    """Add a [Thinking] log entry if configured."""
    if INTENT_CONFIG.get("show_thinking_in_log", True) and intent.reason:
        state.add_log(f"[Thinking] {intent.reason}")


def tick_day_night(state: GameState):
    if state.cycle_length <= 0:
        return

    # Dawn/dusk announcements (Step 2: robust detection via was_night)
    is_night_now = state.is_night
    if state.was_night and not is_night_now:
        state.add_log("The sun rises. A new day begins.")
        # Dawn intent
        intent = generate_intent(
            "dawn",
            state,
            tokenizer=tokenizer,
            model=model,
            ai_brain=ai_brain,
        )
        state._current_intent = intent.to_dict()
        _intent_log(state, intent)
    elif not state.was_night and is_night_now:
        state.add_log("Darkness falls. The night creatures stir...")
    state.was_night = is_night_now

    # Track fatigue while exploring (Step 3: permanent until rest)
    if state.location == "exploring":
        state.ticks_exploring += 1
        threshold = DAY_NIGHT.get("fatigue_threshold", 30)
        if state.ticks_exploring >= threshold:
            # Apply fatigue debuff if not already active
            has_fatigue = any(
                b.source == "Fatigue" for b in state.character.active_buffs
            )
            if not has_fatigue:
                debuff_val = DAY_NIGHT.get("fatigue_debuff_value", 3)
                state.character.active_buffs.append(
                    ActiveBuff(
                        source="Fatigue",
                        buff_type="defense",
                        value=-debuff_val,
                        ticks_remaining=-1,
                    )
                )
                state.add_log(
                    f"Exhaustion sets in! Defense reduced by {debuff_val} "
                    f"until you rest at base."
                )


def tick_location(state: GameState):
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    threshold = DAY_NIGHT.get("fatigue_threshold", 30)

    if state.location == "exploring":
        # Go home if: night+low HP, fatigue threshold,
        # or night+decent base+moderate HP
        should_return = (
            (state.is_night and hp_pct < 0.4)
            or state.ticks_exploring >= threshold
            or (state.is_night and state.base.tier >= 1 and hp_pct < 0.7)
        )

        if should_return and not state.combat:
            state.location = "at_base"
            state.add_log(f"You return to your {state.base.name} to rest.")
    else:
        # Stay at base until dawn (no leaving at full HP during night)
        if not state.is_night:
            # Check dawn intent — stay_rest keeps us at base
            dawn_intent = state._current_intent
            if (
                dawn_intent
                and dawn_intent.get("trigger") == "dawn"
                and dawn_intent.get("decision") == "stay_rest"
            ):
                state.add_log("Resting a bit longer before heading out.")
                state._current_intent = None  # Consumed, will leave next tick
                return
            state._current_intent = None
            state.location = "exploring"
            state.ticks_exploring = 0
            state.add_log("You set out to explore once more.")


def tick_at_base(state: GameState):
    char = state.character
    tier_data = get_base_tier(state.base.tier)
    rest_pct = tier_data["rest_bonus_hp_pct"] if tier_data else 0.10

    # Heal per tick
    heal = int(char.max_hp * rest_pct)
    if heal > 0 and char.hp < char.max_hp:
        old_hp = char.hp
        char.hp = min(char.max_hp, char.hp + heal)
        healed = char.hp - old_hp
        state.add_log(f"Resting... healed {healed} HP ({char.hp}/{char.max_hp}).")

    # Reset fatigue
    state.ticks_exploring = 0
    # Remove fatigue debuffs
    fatigue_buffs = [b for b in char.active_buffs if b.source == "Fatigue"]
    for b in fatigue_buffs:
        char.active_buffs.remove(b)

    # Auto-manage storage
    _auto_manage_storage(state)


def _auto_manage_storage(state: GameState):
    char = state.character
    tier_data = get_base_tier(state.base.tier)
    max_slots = tier_data["storage_slots"] if tier_data else 0
    if max_slots <= 0:
        return

    current_stored = len(state.base.storage)

    # Stash excess consumables (keep 2 on hand)
    keep_on_hand = 2
    consumables_by_name: dict[str, list[int]] = {}
    for idx, item in enumerate(char.inventory):
        if item.item_type == "consumable":
            consumables_by_name.setdefault(item.name, []).append(idx)

    to_stash_indices: list[int] = []
    for _name, indices in consumables_by_name.items():
        if len(indices) > keep_on_hand:
            to_stash_indices.extend(indices[keep_on_hand:])

    # Stash items (reverse order to preserve indices)
    for idx in sorted(to_stash_indices, reverse=True):
        if current_stored >= max_slots:
            break
        item = char.inventory.pop(idx)
        state.base.storage.append(item)
        current_stored += 1
        state.add_log(f"Stashed {item.name} in storage.")

    # Retrieve potions when low on consumables
    consumable_count = sum(1 for i in char.inventory if i.item_type == "consumable")
    if consumable_count < keep_on_hand:
        for i in range(len(state.base.storage) - 1, -1, -1):
            if consumable_count >= keep_on_hand:
                break
            item = state.base.storage[i]
            if item.item_type == "consumable":
                state.base.storage.pop(i)
                char.inventory.append(item)
                consumable_count += 1
                state.add_log(f"Retrieved {item.name} from storage.")


def maybe_upgrade_base(state: GameState):
    next_tier = get_next_base_tier(state.base.tier)
    if not next_tier:
        return

    cost = next_tier.get("upgrade_cost")
    if not cost:
        return

    # Check XP requirement
    xp_cost = cost.get("xp", 0)
    if state.character.xp < xp_cost:
        return

    # Check item requirements
    required_items = cost.get("items", [])
    # Count available items across inventory + storage
    available: dict[str, int] = {}
    for item in state.character.inventory:
        available[item.name] = available.get(item.name, 0) + 1
    for item in state.base.storage:
        available[item.name] = available.get(item.name, 0) + 1

    needed: dict[str, int] = {}
    for item_name in required_items:
        needed[item_name] = needed.get(item_name, 0) + 1

    for item_name, count in needed.items():
        if available.get(item_name, 0) < count:
            return

    # Consume resources
    state.character.xp -= xp_cost
    for item_name, count in needed.items():
        remaining = count
        for item_list in (state.character.inventory, state.base.storage):
            while remaining > 0:
                idx = next(
                    (i for i, item in enumerate(item_list) if item.name == item_name),
                    None,
                )
                if idx is None:
                    break
                item_list.pop(idx)
                remaining -= 1

    # Upgrade
    state.base.tier = next_tier["tier"]
    state.base.name = next_tier["name"]
    state.add_log(
        f"Base upgraded to {next_tier['name']}! "
        f"(Tier {next_tier['tier']}, "
        f"{next_tier['storage_slots']} storage slots)"
    )


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

    # Low HP intent check
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    low_hp_threshold = INTENT_CONFIG.get("low_hp_threshold", 0.35)
    if hp_pct < low_hp_threshold and combat.ai_strategy != "flee":
        intent = generate_intent(
            "low_hp",
            state,
            tokenizer=tokenizer,
            model=model,
            ai_brain=ai_brain,
            enemy=combat.enemy,
        )
        state._current_intent = intent.to_dict()
        _intent_log(state, intent)
        strategy = "attack" if intent.decision == "press_on" else intent.decision
    else:
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
        loot = roll_loot(combat.enemy.name, is_night=state.is_night)
        if loot:
            item = InventoryItem.from_config(loot)
            state.add_log(f"Loot: {item.name} ({item.rarity})!")
            for msg in equip_or_stash(state.character, item):
                state.add_log(msg)

        state.combat = None


def tick_quest(state: GameState):
    # Roll for encounter
    enemy = roll_encounter(state.zone, is_night=state.is_night)
    if enemy:
        # Pre-engagement intent
        intent = generate_intent(
            "combat_start",
            state,
            tokenizer=tokenizer,
            model=model,
            ai_brain=ai_brain,
            enemy=enemy,
        )
        state._current_intent = intent.to_dict()
        _intent_log(state, intent)

        if intent.decision == "flee":
            state.add_log(f"You spot a {enemy.name} but decide to avoid it.")
            return  # Skip combat entirely

        state.combat = Combat(enemy=enemy)
        state.combat.ai_strategy = intent.decision  # "attack" or "defend"
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
        state.add_log(f"Received: {quest.reward_item}!")
        for msg in equip_or_stash(state.character, item):
            state.add_log(msg)

    state.quest = None

    # Quest complete intent decides zone/expedition behavior
    intent = generate_intent(
        "quest_complete",
        state,
        tokenizer=tokenizer,
        model=model,
        ai_brain=ai_brain,
    )
    state._current_intent = intent.to_dict()
    _intent_log(state, intent)

    if intent.decision == "advance":
        new_zone = pick_next_zone(state.zone, state.character.effective_attack)
        if new_zone != state.zone:
            state.zone = new_zone
            state.add_log(f"You venture into the {new_zone}!")
    elif intent.decision == "return_home":
        state.location = "at_base"
        state.add_log(f"You return to your {state.base.name} to recover.")
    elif intent.decision == "expedition":
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
        # Also try to advance
        new_zone = pick_next_zone(state.zone, state.character.effective_attack)
        if new_zone != state.zone:
            state.zone = new_zone
            state.add_log(f"You venture into the {new_zone}!")
    # "stay" = pick up next quest naturally, no zone change


def tick_idle(state: GameState):
    quest_data = get_quest(state.zone)
    state.quest = Quest(**quest_data)
    state.add_log(f"New quest: {state.quest.description}")


def tick_buffs(state: GameState):
    expired = []
    for buff in state.character.active_buffs:
        if buff.ticks_remaining < 0:
            continue  # Permanent buff (e.g. Fatigue) — managed by tick_at_base
        buff.ticks_remaining -= 1
        if buff.ticks_remaining <= 0:
            expired.append(buff)
    for buff in expired:
        state.character.active_buffs.remove(buff)
        sign = "+" if buff.value >= 0 else ""
        state.add_log(
            f"Buff from {buff.source} ({sign}{buff.value} {buff.buff_type}) expired."
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
                    for msg in equip_or_stash(state.character, item):
                        state.add_log(msg)

    # Clean up finished expeditions (keep last 5 completed for history)
    state.expeditions = [e for e in state.expeditions if e.status == "active"]


def maybe_launch_expedition(state: GameState):
    active_count = sum(1 for e in state.expeditions if e.status == "active")
    if active_count >= 3:
        return
    if state.combat:
        return
    spontaneous_chance = INTENT_CONFIG.get("expedition_chance_spontaneous", 0.03)
    if random.random() > spontaneous_chance:
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
        state._current_intent = None  # Reset intent each tick

        # IMPORTANT: tick_day_night must run before tick_location.
        # tick_day_night updates was_night and fatigue state;
        # tick_location reads is_night to decide exploring↔at_base transitions.
        tick_day_night(state)
        tick_npc_movement(state)
        tick_location(state)

        if state.location == "at_base":
            tick_at_base(state)
            interval = TICK_BASE
        elif state.combat:
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
        maybe_upgrade_base(state)

        # Clear NPC encounter if we're in combat now
        if state.combat:
            state.npc_encounter = None

        # Print tick summary
        char = state.character
        night_tag = " [NIGHT]" if state.is_night else ""
        loc_tag = f" @{state.location}"
        print(
            f"\n[tick {state.tick}]{night_tag}{loc_tag} zone={state.zone} "
            f"hp={char.hp}/{char.max_hp} "
            f"atk={char.effective_attack} "
            f"def={char.effective_defense} "
            f"xp={char.xp} "
            f"base={state.base.name}"
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

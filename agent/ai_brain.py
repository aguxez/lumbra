from __future__ import annotations

import random
import re

from config_loader import get_loot_for_mob, get_mobs_for_zone
from world import EXPLORATION_EVENTS, ZONES, generate_hardcoded_quest


def _truncate_sentence(text: str, max_len: int = 120) -> str | None:
    """Truncate text at the last sentence boundary within max_len.
    Returns None if no complete sentence is found."""
    if len(text) <= max_len:
        # Check it looks like a complete sentence
        if text.rstrip()[-1:] in ".!?\"'":
            return text.rstrip()
        return None
    # Find last sentence-ending punctuation within limit
    chunk = text[:max_len]
    for i in range(len(chunk) - 1, -1, -1):
        if chunk[i] in ".!?":
            return chunk[: i + 1]
    return None


def _generate(
    tokenizer, model, prompt: str, max_tokens: int = 80, temperature: float = 0.9
) -> str | None:
    """Shared LLM generate-decode-clean pipeline."""
    try:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(text, return_tensors="pt")
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=temperature,
        )
        generated = outputs[0][inputs["input_ids"].shape[1] :]
        result = tokenizer.decode(generated, skip_special_tokens=True).strip()
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        result = re.sub(r"<think>.*", "", result, flags=re.DOTALL).strip()
        return result if result else None
    except Exception as e:
        print(f"[ai_brain] generation error: {e}")
        return None


def _generate_text(
    tokenizer, model, prompt: str, max_tokens: int = 80, temperature: float = 0.9
) -> str | None:
    """Generate text and truncate to a complete sentence. Returns None on failure."""
    result = _generate(
        tokenizer, model, prompt, max_tokens=max_tokens, temperature=temperature
    )
    if result and len(result) > 5:
        truncated = _truncate_sentence(result)
        if truncated:
            return truncated
    return None


def decide_combat_strategy(
    tokenizer, model, character_dict: dict, enemy_dict: dict
) -> str:
    hp_pct = character_dict["hp"] / max(1, character_dict["max_hp"])
    c = character_dict
    e = enemy_dict
    prompt = (
        f"You are a RPG adventurer with {c['hp']}/{c['max_hp']} HP, "
        f"{c['attack']} ATK, {c['defense']} DEF.\n"
        f"Fighting: {e['enemy_name']} "
        f"with {e['enemy_hp']}/{e['enemy_max_hp']} HP, "
        f"{e['enemy_attack']} ATK, {e['enemy_defense']} DEF.\n"
        f"Choose ONE strategy:\n"
        f"1. attack\n"
        f"2. defend\n"
        f"3. flee\n"
        f"Reply with just the number."
    )

    result = _generate(tokenizer, model, prompt, max_tokens=40, temperature=0.7)
    if result:
        first_digit = re.search(r"[123]", result)
        if first_digit:
            return {"1": "attack", "2": "defend", "3": "flee"}[first_digit.group()]

    # Fallback: low HP → defend, very low → flee
    if hp_pct < 0.2:
        return "flee"
    elif hp_pct < 0.4:
        return "defend"
    return "attack"


def generate_quest(tokenizer, model, zone_name: str) -> dict:
    monsters = get_mobs_for_zone(zone_name)
    if not monsters:
        monsters = get_mobs_for_zone("Peaceful Meadow")
    monster_names = ", ".join(m["name"] for m in monsters)

    prompt = (
        f"You are a quest giver in the {zone_name}.\n"
        f"Monsters here: {monster_names}.\n"
        "Give a quest. Use EXACTLY this format "
        "(one short complete sentence for description, "
        "end with a period):\n"
        "TARGET: <monster name from the list above>\n"
        "COUNT: <number 3-6>\n"
        "DESCRIPTION: <one complete sentence, "
        "under 80 characters, ending with a period>"
    )

    result = _generate(tokenizer, model, prompt, max_tokens=120, temperature=0.8)
    if result:
        target_match = re.search(r"TARGET:\s*(.+)", result)
        count_match = re.search(r"COUNT:\s*(\d+)", result)
        desc_match = re.search(r"DESCRIPTION:\s*(.+)", result)

        if target_match and count_match and desc_match:
            target = target_match.group(1).strip()
            count = int(count_match.group(1).strip())
            raw_desc = desc_match.group(1).strip()
            desc = _truncate_sentence(raw_desc)
            if not desc:
                # Incomplete sentence — fall back to hardcoded quest
                return generate_hardcoded_quest(zone_name)

            # Validate target exists in zone
            valid_names = [m["name"] for m in monsters]
            if target not in valid_names:
                target = random.choice(valid_names)

            count = max(3, min(6, count))

            zone_idx = next(
                (i for i, z in enumerate(ZONES) if z["name"] == zone_name), 0
            )
            loot_items = get_loot_for_mob(target)
            reward_item = (
                random.choice(loot_items)["name"]
                if loot_items and random.random() < 0.5
                else None
            )

            return {
                "description": desc,
                "target": target,
                "goal": count,
                "reward_xp": count * 15 + zone_idx * 10,
                "reward_item": reward_item,
            }

    return generate_hardcoded_quest(zone_name)


def generate_exploration_event(tokenizer, model, zone_name: str) -> str:
    prompt = (
        f"You are exploring the {zone_name}. "
        "Describe one brief thing you see or experience "
        "(one complete sentence, under 80 characters, "
        "ending with a period)."
    )
    text = _generate_text(tokenizer, model, prompt)
    if text:
        return text
    return random.choice(EXPLORATION_EVENTS)


def generate_npc_dialogue(
    tokenizer, model, npc_name: str, npc_role: str, zone: str, affinity: int
) -> str | None:
    prompt = (
        f"You are {npc_name}, a {npc_role} in the {zone}. "
        f"The adventurer visits you (friendship level: {affinity}). "
        "Say one brief line in character "
        "(one complete sentence, under 80 characters, "
        "ending with a period)."
    )
    return _generate_text(tokenizer, model, prompt)


def decide_intent(
    tokenizer, model, trigger: str, state_summary: str, options: list[str], config: dict
) -> tuple[str, str] | None:
    """Ask the LLM to pick a numbered option for a decision trigger."""
    numbered = "\n".join(f"{i + 1}. {opt}" for i, opt in enumerate(options))
    prompt = (
        f"You are an RPG adventurer deciding what to do.\n"
        f"Situation: {trigger.replace('_', ' ')}.\n"
        f"Your status: {state_summary}\n"
        f"Choose ONE option:\n{numbered}\n"
        f"Reply with just the number."
    )

    temperature = config.get("llm_temperature", 0.7)
    result = _generate(tokenizer, model, prompt, max_tokens=40, temperature=temperature)
    if result:
        valid_digits = set(str(i + 1) for i in range(len(options)))
        first_digit = re.search(r"[" + "".join(valid_digits) + r"]", result)
        if first_digit:
            idx = int(first_digit.group()) - 1
            decision = options[idx]
            # Try to extract a short reason from the response
            reason_match = re.search(r"[.!]\s*(.+)", result)
            reason = reason_match.group(1).strip()[:80] if reason_match else ""
            return (decision, reason)
    return None


def generate_boss_taunt(
    tokenizer, model, boss_name: str, zone: str, phase: int
) -> str | None:
    """Generate a boss taunt line when boss spawns or changes phase."""
    phase_desc = {
        0: "confident and threatening",
        1: "wounded but furious",
        2: "desperate and enraged",
    }
    mood = phase_desc.get(phase, "menacing")
    prompt = (
        f"You are {boss_name}, a powerful boss monster guarding the {zone}. "
        f"You are {mood}. "
        "Say one brief intimidating line in character "
        "(one complete sentence, under 80 characters, ending with a period)."
    )
    return _generate_text(tokenizer, model, prompt, max_tokens=60, temperature=0.9)


def generate_boss_victory_text(
    tokenizer, model, boss_name: str, zone: str, next_zone: str
) -> str | None:
    """Generate a celebration message when the boss is defeated."""
    prompt = (
        f"The adventurer has defeated {boss_name} in the {zone} "
        f"and can now enter {next_zone}. "
        "Describe this victory in one dramatic sentence "
        "(under 80 characters, ending with a period)."
    )
    return _generate_text(tokenizer, model, prompt, max_tokens=60, temperature=0.8)


def generate_boss_defeat_text(
    tokenizer, model, boss_name: str, zone: str
) -> str | None:
    """Generate a defeat message when the player dies to a boss."""
    prompt = (
        f"The adventurer was defeated by {boss_name} in the {zone} and must retreat. "
        "Describe this defeat in one brief sentence "
        "(under 80 characters, ending with a period)."
    )
    return _generate_text(tokenizer, model, prompt, max_tokens=60, temperature=0.8)


def decide_trade_action(
    tokenizer,
    model,
    state_summary: str,
    gold: int,
    options: list[tuple[str, str, int]],
) -> tuple[str, str] | None:
    """Ask the LLM to pick a trade action (buy/sell/skip).

    options: list of (action, item_name, price) tuples.
    Returns (action, item_name) or None on failure.
    """
    numbered_lines = []
    for i, (action, item_name, price) in enumerate(options):
        if action == "buy":
            numbered_lines.append(f"{i + 1}. buy {item_name} ({price}g)")
        elif action == "sell":
            numbered_lines.append(f"{i + 1}. sell {item_name} (for {price}g)")
        else:
            numbered_lines.append(f"{i + 1}. skip (save gold)")
    numbered = "\n".join(numbered_lines)

    prompt = (
        f"You are an RPG adventurer visiting a merchant's shop.\n"
        f"Your status: {state_summary}\n"
        f"Your gold: {gold}\n"
        f"Choose ONE action:\n{numbered}\n"
        f"Reply with just the number."
    )

    result = _generate(tokenizer, model, prompt, max_tokens=40, temperature=0.7)
    if result:
        valid_digits = set(str(i + 1) for i in range(len(options)))
        first_digit = re.search(r"[" + "".join(valid_digits) + r"]", result)
        if first_digit:
            idx = int(first_digit.group()) - 1
            action, item_name, _ = options[idx]
            return (action, item_name)
    return None


def generate_expedition_event(
    tokenizer, model, destination: str, progress: int, duration: int
) -> str | None:
    pct = int(progress / max(1, duration) * 100)
    prompt = (
        f"An expedition is exploring {destination} ({pct}% complete). "
        "Describe one brief event the scouts encounter "
        "(one complete sentence, under 80 characters, "
        "ending with a period)."
    )
    return _generate_text(tokenizer, model, prompt)

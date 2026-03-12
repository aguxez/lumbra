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
    result = _generate(tokenizer, model, prompt)
    if result and len(result) > 5:
        truncated = _truncate_sentence(result)
        if truncated:
            return truncated
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
    result = _generate(tokenizer, model, prompt)
    if result and len(result) > 5:
        truncated = _truncate_sentence(result)
        if truncated:
            return truncated
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
    result = _generate(tokenizer, model, prompt)
    if result and len(result) > 5:
        truncated = _truncate_sentence(result)
        if truncated:
            return truncated
    return None

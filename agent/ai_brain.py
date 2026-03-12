import re
import random
from world import MONSTER_TABLE, LOOT_TABLE, ZONES, generate_hardcoded_quest, EXPLORATION_EVENTS


def decide_combat_strategy(tokenizer, model, character_dict: dict, enemy_dict: dict) -> str:
    hp_pct = character_dict["hp"] / max(1, character_dict["max_hp"])
    prompt = (
        f"You are a RPG adventurer with {character_dict['hp']}/{character_dict['max_hp']} HP, "
        f"{character_dict['attack']} ATK, {character_dict['defense']} DEF.\n"
        f"Fighting: {enemy_dict['enemy_name']} with {enemy_dict['enemy_hp']}/{enemy_dict['enemy_max_hp']} HP, "
        f"{enemy_dict['enemy_attack']} ATK, {enemy_dict['enemy_defense']} DEF.\n"
        f"Choose ONE strategy:\n"
        f"1. attack\n"
        f"2. defend\n"
        f"3. flee\n"
        f"Reply with just the number."
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(text, return_tensors="pt")
        outputs = model.generate(
            **inputs, max_new_tokens=40, do_sample=True, temperature=0.7,
        )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        result = tokenizer.decode(generated, skip_special_tokens=True).strip()
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        result = re.sub(r"<think>.*", "", result, flags=re.DOTALL).strip()

        first_digit = re.search(r"[123]", result)
        if first_digit:
            return {"1": "attack", "2": "defend", "3": "flee"}[first_digit.group()]
    except Exception as e:
        print(f"[ai_brain] combat strategy error: {e}")

    # Fallback: low HP → defend, very low → flee
    if hp_pct < 0.2:
        return "flee"
    elif hp_pct < 0.4:
        return "defend"
    return "attack"


def generate_quest(tokenizer, model, zone_name: str) -> dict:
    monsters = MONSTER_TABLE.get(zone_name, MONSTER_TABLE["Peaceful Meadow"])
    monster_names = ", ".join(m["name"] for m in monsters)

    prompt = (
        f"You are a quest giver in the {zone_name}.\n"
        f"Monsters here: {monster_names}.\n"
        f"Give a quest. Format:\n"
        f"TARGET: <monster name>\n"
        f"COUNT: <number 3-6>\n"
        f"DESCRIPTION: <one sentence quest description>"
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(text, return_tensors="pt")
        outputs = model.generate(
            **inputs, max_new_tokens=80, do_sample=True, temperature=0.8,
        )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        result = tokenizer.decode(generated, skip_special_tokens=True).strip()
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        result = re.sub(r"<think>.*", "", result, flags=re.DOTALL).strip()

        target_match = re.search(r"TARGET:\s*(.+)", result)
        count_match = re.search(r"COUNT:\s*(\d+)", result)
        desc_match = re.search(r"DESCRIPTION:\s*(.+)", result)

        if target_match and count_match and desc_match:
            target = target_match.group(1).strip()
            count = int(count_match.group(1).strip())
            desc = desc_match.group(1).strip()[:100]

            # Validate target exists in zone
            valid_names = [m["name"] for m in monsters]
            if target not in valid_names:
                target = random.choice(valid_names)

            count = max(3, min(6, count))

            zone_idx = next((i for i, z in enumerate(ZONES) if z["name"] == zone_name), 0)
            loot = LOOT_TABLE.get(zone_name, LOOT_TABLE["Peaceful Meadow"])
            reward_item = random.choice(loot)["name"] if random.random() < 0.5 else None

            return {
                "description": desc,
                "target": target,
                "goal": count,
                "reward_xp": count * 15 + zone_idx * 10,
                "reward_item": reward_item,
            }
    except Exception as e:
        print(f"[ai_brain] quest generation error: {e}")

    return generate_hardcoded_quest(zone_name)


def generate_exploration_event(tokenizer, model, zone_name: str) -> str:
    prompt = (
        f"You are exploring the {zone_name}. "
        f"Describe one brief thing you see or experience (one sentence, under 100 characters)."
    )

    try:
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer(text, return_tensors="pt")
        outputs = model.generate(
            **inputs, max_new_tokens=60, do_sample=True, temperature=0.9,
        )
        generated = outputs[0][inputs["input_ids"].shape[1]:]
        result = tokenizer.decode(generated, skip_special_tokens=True).strip()
        result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()
        result = re.sub(r"<think>.*", "", result, flags=re.DOTALL).strip()

        if result and len(result) > 5:
            return result[:100]
    except Exception as e:
        print(f"[ai_brain] exploration event error: {e}")

    return random.choice(EXPLORATION_EVENTS)

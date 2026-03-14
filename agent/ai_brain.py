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
    options: list[tuple[str, str, int, bool]],
) -> tuple[str, str] | None:
    """Ask the LLM to pick a trade action (buy/sell/skip).

    options: list of (action, item_name, price, is_upgrade) tuples.
    Returns (action, item_name) or None on failure.
    """
    numbered_lines = []
    for i, (action, item_name, price, is_upgrade) in enumerate(options):
        if action == "buy":
            tag = " [UPGRADE]" if is_upgrade else ""
            numbered_lines.append(f"{i + 1}. buy {item_name} ({price}g){tag}")
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
            action, item_name, _, _ = options[idx]
            return (action, item_name)
    return None


def evaluate_market_prices(
    tokenizer,
    model,
    trade_history: list[dict],
    merchant_summaries: list[dict],
    world_context: str,
) -> tuple[dict[str, float], str] | None:
    """AI evaluates economy and returns (price_adjustments, market_news)."""

    # Sanitize item/merchant names to prevent prompt injection
    def _sanitize(name: str) -> str:
        return re.sub(r"(ADJUST:|NEWS:)", "", name).strip()

    # Format trade history
    trade_lines = []
    for t in trade_history[-8:]:
        trade_lines.append(
            f"tick {t['tick']}: player {t['action']} {_sanitize(t['item_name'])} "
            f"from/to {_sanitize(t['merchant_name'])} for {t['price']}g"
        )
    trades_str = "\n".join(trade_lines) if trade_lines else "No recent trades."

    # Format merchant stock
    stock_lines = []
    for m in merchant_summaries:
        if m["items"]:
            items_str = ", ".join(_sanitize(i) for i in m["items"])
        else:
            items_str = "empty"
        name = _sanitize(m["name"])
        stock_lines.append(
            f"{name} ({m['role']}): {m['gold']}g gold, items: {items_str}"
        )
    stock_str = "\n".join(stock_lines)

    # Collect all known item names from merchant inventories
    known_items: set[str] = set()
    for m in merchant_summaries:
        for item_name in m["items"]:
            known_items.add(item_name)

    prompt = (
        "You are the market oracle in a fantasy RPG. Analyze supply and demand.\n\n"
        f"Recent trades:\n{trades_str}\n\n"
        f"Merchant stock:\n{stock_str}\n\n"
        f"World: {world_context}\n\n"
        "Rules for pricing:\n"
        "- HIGH DEMAND (item bought often, few merchants stock it): "
        "raise price (1.1 to 2.0)\n"
        "- LOW DEMAND (item not traded recently, many merchants stock it): "
        "lower price (0.5 to 0.9)\n"
        "- NORMAL (balanced): keep at 1.0 (omit from list)\n\n"
        "Adjust prices for up to 3 items. Use this EXACT format:\n"
        "ADJUST: item_name = multiplier\n"
        "NEWS: one sentence about the market (under 80 chars, ending with period)"
    )

    result = _generate(tokenizer, model, prompt, max_tokens=120, temperature=0.7)
    if not result:
        return None

    # Parse ADJUST lines
    adjustments: dict[str, float] = {}
    for match in re.finditer(r"ADJUST:\s*(.+?)\s*=\s*(-?\d*\.?\d+)", result):
        item_name = match.group(1).strip()
        try:
            mult = float(match.group(2))
        except ValueError:
            continue
        # Clamp to [0.5, 2.0] and validate item exists
        mult = max(0.5, min(2.0, mult))
        if item_name in known_items:
            adjustments[item_name] = mult

    # Parse NEWS line
    news = ""
    news_match = re.search(r"NEWS:\s*(.+)", result)
    if news_match:
        raw_news = news_match.group(1).strip()
        truncated = _truncate_sentence(raw_news, max_len=80)
        news = truncated if truncated else raw_news[:80]

    if not adjustments and not news:
        return None

    return (adjustments, news)


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


def evaluate_npc_needs(
    tokenizer,
    model,
    npc_name: str,
    role: str,
    zone: str,
    inventory_summary: str,
    gold: int,
    is_night: bool,
    nearby_npcs: list[str],
) -> list[tuple[str, int, str]] | None:
    """Ask the LLM what an NPC needs. Returns list of (item_type, priority, reason)."""
    time_str = "night" if is_night else "day"
    nearby = ", ".join(nearby_npcs) if nearby_npcs else "no one"
    prompt = (
        f"You are {npc_name}, a {role} in the {zone}. It is {time_str}.\n"
        f"Your inventory: {inventory_summary}\n"
        f"Your gold: {gold}g\n"
        f"Nearby NPCs: {nearby}\n"
        "What do you need? Pick 1-2 from: "
        "consumable, weapon, armor, accessory, shield.\n"
        "Reply with numbered lines, each: TYPE PRIORITY REASON\n"
        "PRIORITY is 1-10 (10=urgent). REASON is a short phrase.\n"
        "Example:\n1. consumable 8 need healing supplies for the dangerous road\n"
        "2. weapon 5 looking for a better blade"
    )

    result = _generate(tokenizer, model, prompt, max_tokens=80, temperature=0.8)
    if not result:
        return None

    valid_types = {"consumable", "weapon", "armor", "accessory", "shield"}
    needs: list[tuple[str, int, str]] = []
    for line in result.strip().split("\n"):
        # Match: optional number/dot, then type, priority, reason
        m = re.match(r"\d*\.?\s*(\w+)\s+(\d+)\s+(.*)", line.strip())
        if m:
            item_type = m.group(1).lower()
            if item_type in valid_types:
                priority = max(1, min(10, int(m.group(2))))
                reason = m.group(3).strip()[:80]
                needs.append((item_type, priority, reason))
    return needs if needs else None


def npc_make_offer(
    tokenizer,
    model,
    buyer_name: str,
    buyer_role: str,
    zone: str,
    buyer_gold: int,
    need_reason: str,
    seller_name: str,
    item_name: str,
    fair_price: int,
) -> tuple[str, int, str] | None:
    """Buyer NPC proposes a deal or skips.

    Returns ("offer", price, reason) or ("skip", 0, reason) or None.
    """
    prompt = (
        f"You are {buyer_name}, a {buyer_role} in the {zone}.\n"
        f"{seller_name} has: {item_name}.\n"
        f"You need it because: {need_reason}\n"
        f"You have {buyer_gold}g. The fair price is ~{fair_price}g.\n"
        "Make an offer or skip.\n"
        "Reply: OFFER <price>g REASON <why>\n"
        "Or: SKIP REASON <why>"
    )

    result = _generate(tokenizer, model, prompt, max_tokens=60, temperature=0.7)
    if not result:
        return None

    upper = result.upper()
    if "SKIP" in upper:
        reason_match = re.search(r"REASON\s+(.+)", result, re.IGNORECASE)
        reason = (
            reason_match.group(1).strip()[:80] if reason_match else "not interested"
        )
        return ("skip", 0, reason)

    if "OFFER" in upper:
        price_match = re.search(r"OFFER\s+(\d+)", result, re.IGNORECASE)
        reason_match = re.search(r"REASON\s+(.+)", result, re.IGNORECASE)
        if price_match:
            price = int(price_match.group(1))
            price = max(1, min(price, buyer_gold))
            reason = reason_match.group(1).strip()[:80] if reason_match else "fair deal"
            return ("offer", price, reason)

    return None


def npc_respond_offer(
    tokenizer,
    model,
    seller_name: str,
    seller_role: str,
    zone: str,
    seller_gold: int,
    seller_item_count: int,
    buyer_name: str,
    item_name: str,
    offered_price: int,
    fair_price: int,
) -> tuple[str, int, str] | None:
    """Seller NPC responds to an offer.

    Returns ("accept", price, reason) or ("counter", price, reason)
    or ("refuse", 0, reason) or None.
    """
    prompt = (
        f"You are {seller_name}, a {seller_role} in the {zone}.\n"
        f"{buyer_name} offers {offered_price}g for your {item_name}.\n"
        f"The fair price is ~{fair_price}g. You have {seller_gold}g "
        f"and {seller_item_count} items.\n"
        "Reply: ACCEPT\n"
        "Or: COUNTER <price>g REASON <why>\n"
        "Or: REFUSE REASON <why>"
    )

    result = _generate(tokenizer, model, prompt, max_tokens=60, temperature=0.7)
    if not result:
        return None

    upper = result.upper()
    if "ACCEPT" in upper:
        return ("accept", offered_price, "deal accepted")

    if "COUNTER" in upper:
        price_match = re.search(r"COUNTER\s+(\d+)", result, re.IGNORECASE)
        reason_match = re.search(r"REASON\s+(.+)", result, re.IGNORECASE)
        if price_match:
            price = int(price_match.group(1))
            price = max(1, price)
            reason = (
                reason_match.group(1).strip()[:80] if reason_match else "counter offer"
            )
            return ("counter", price, reason)

    if "REFUSE" in upper:
        reason_match = re.search(r"REASON\s+(.+)", result, re.IGNORECASE)
        reason = (
            reason_match.group(1).strip()[:80]
            if reason_match
            else "not worth parting with it"
        )
        return ("refuse", 0, reason)

    return None

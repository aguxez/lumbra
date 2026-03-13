from __future__ import annotations

import random
from dataclasses import dataclass, field

from config_loader import INTENT_CONFIG, get_zone


@dataclass
class PlayerIntent:
    trigger: str
    decision: str
    reason: str
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "trigger": self.trigger,
            "decision": self.decision,
            "reason": self.reason,
        }


# Decision options per trigger
TRIGGER_OPTIONS: dict[str, list[str]] = {
    "quest_complete": ["advance", "stay", "return_home", "expedition"],
    "dawn": ["explore", "stay_rest", "cautious"],
    "combat_start": ["attack", "defend", "flee"],
    "at_base": ["rest", "upgrade", "resupply"],
    "low_hp": ["flee", "defend", "press_on"],
}


def build_state_summary(state) -> str:
    """Compact state string for LLM prompts (~200 chars)."""
    char = state.character
    hp_pct = int(char.hp / max(1, char.max_hp) * 100)
    night = "night" if state.is_night else "day"
    return (
        f"HP {char.hp}/{char.max_hp} ({hp_pct}%), "
        f"ATK {char.effective_attack}, DEF {char.effective_defense}, "
        f"XP {char.xp}, zone {state.zone}, {night}, "
        f"fatigue {state.ticks_exploring} ticks, base tier {state.base.tier}"
    )


# --- Fallback heuristics per trigger ---


def _fallback_quest_complete(state, **kwargs) -> tuple[str, str]:
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    zone_data = get_zone(state.zone)
    danger = zone_data["danger"] if zone_data else 1
    can_advance = char.effective_attack >= danger * 10
    advance_threshold = INTENT_CONFIG.get("advance_hp_threshold", 0.6)
    return_threshold = INTENT_CONFIG.get("return_home_hp_threshold", 0.4)
    exp_chance = INTENT_CONFIG.get("expedition_chance_on_advance", 0.30)

    if hp_pct < return_threshold:
        return ("return_home", "Too wounded to continue.")

    if can_advance and hp_pct >= advance_threshold:
        if random.random() < exp_chance:
            return ("expedition", "Strong enough to send scouts ahead.")
        return ("advance", "Ready for a greater challenge.")

    if hp_pct < advance_threshold:
        return ("stay", "Need to recover before pushing forward.")

    return ("stay", "Consolidating strength in this area.")


def _fallback_combat_start(state, **kwargs) -> tuple[str, str]:
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    enemy = kwargs.get("enemy")
    flee_threshold = INTENT_CONFIG.get("power_ratio_flee_threshold", 0.5)
    is_boss = enemy and enemy.is_boss

    if enemy and not is_boss:
        power_ratio = char.effective_attack / max(1, enemy.attack)
        if power_ratio < flee_threshold and hp_pct < 0.5:
            return ("flee", "This foe is too dangerous right now.")
        if power_ratio < flee_threshold:
            return ("defend", "Better to fight cautiously here.")

    has_potions = any(i.effect_type == "heal" for i in char.inventory)

    if hp_pct < 0.3 and not has_potions:
        if is_boss:
            return ("defend", "No potions left, must hold the line against the boss!")
        return ("flee", "Too weak and no potions left.")

    if is_boss:
        return ("attack", "The boss must fall!")

    return ("attack", "Ready for battle!")


def _fallback_low_hp(state, **kwargs) -> tuple[str, str]:
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    enemy = kwargs.get("enemy")
    has_potions = any(i.effect_type == "heal" for i in char.inventory)
    is_boss = enemy and enemy.is_boss

    if enemy and enemy.hp < enemy.max_hp * 0.2:
        return ("press_on", "The enemy is almost defeated!")

    if is_boss:
        if has_potions:
            return ("defend", "Hold the line against the boss and use potions.")
        return ("press_on", "No retreat from the boss! Fight to the end!")

    if hp_pct < 0.15 and not has_potions:
        return ("flee", "Must retreat before it's too late!")

    if has_potions:
        return ("defend", "Hold the line and use potions.")

    return ("flee", "No potions and too wounded to continue.")


def _fallback_dawn(state, **kwargs) -> tuple[str, str]:
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)
    caution_threshold = INTENT_CONFIG.get("night_caution_hp_threshold", 0.7)

    if hp_pct < 0.5:
        return ("stay_rest", "Need more rest before heading out.")

    if hp_pct < caution_threshold:
        return ("cautious", "Feeling wary, will proceed carefully.")

    return ("explore", "A new day, time to explore!")


def _fallback_at_base(state, **kwargs) -> tuple[str, str]:
    char = state.character
    hp_pct = char.hp / max(1, char.max_hp)

    if hp_pct < 0.8:
        return ("rest", "Need to finish healing up.")

    return ("rest", "Resting at base.")


_FALLBACKS = {
    "quest_complete": _fallback_quest_complete,
    "combat_start": _fallback_combat_start,
    "low_hp": _fallback_low_hp,
    "dawn": _fallback_dawn,
    "at_base": _fallback_at_base,
}


def generate_intent(
    trigger: str,
    state,
    *,
    tokenizer=None,
    model=None,
    ai_brain=None,
    **kwargs,
) -> PlayerIntent:
    """Generate a PlayerIntent for the given trigger.

    Tries LLM first (if available), falls back to heuristics.
    """
    if not INTENT_CONFIG.get("enabled", True):
        # Intent system disabled — use neutral defaults
        defaults = {
            "quest_complete": ("stay", ""),
            "combat_start": ("attack", ""),
            "low_hp": ("defend", ""),
            "dawn": ("explore", ""),
            "at_base": ("rest", ""),
        }
        decision, reason = defaults.get(trigger, ("stay", ""))
        return PlayerIntent(trigger=trigger, decision=decision, reason=reason)

    options = TRIGGER_OPTIONS.get(trigger, [])
    decision = None
    reason = None

    # Try LLM path
    if ai_brain and tokenizer and model and options:
        result = ai_brain.decide_intent(
            tokenizer,
            model,
            trigger,
            build_state_summary(state),
            options,
            INTENT_CONFIG,
        )
        if result:
            decision, reason = result

    # Fallback to heuristics
    if decision is None:
        fallback_fn = _FALLBACKS.get(trigger)
        if fallback_fn:
            decision, reason = fallback_fn(state, **kwargs)
        else:
            decision = options[0] if options else "stay"
            reason = ""

    return PlayerIntent(
        trigger=trigger,
        decision=decision,
        reason=reason or "",
        parameters=kwargs,
    )

import random

from game_state import Character, Combat, Enemy


def calc_damage(attacker_attack: int, defender_defense: int) -> tuple[int, int]:
    base_damage = attacker_attack - defender_defense // 2
    dice_roll = random.randint(1, 6)
    final_damage = max(1, base_damage + dice_roll - 3)

    if dice_roll == 6:
        final_damage *= 2
    elif dice_roll == 1:
        final_damage = 0

    return final_damage, dice_roll


def check_boss_phase(enemy: Enemy) -> int | None:
    """Check if boss should transition phase. Returns new phase index if changed."""
    if not enemy.is_boss or not enemy.boss_phases:
        return None
    hp_pct = enemy.hp / max(1, enemy.max_hp)
    target_phase = 0
    for i, phase in enumerate(enemy.boss_phases):
        if hp_pct <= phase["threshold"]:
            target_phase = i
    if target_phase != enemy.boss_phase:
        enemy.boss_phase = target_phase
        return target_phase
    return None


def _get_boss_phase_bonuses(enemy: Enemy) -> tuple[int, int]:
    """Return (attack_bonus, defense_bonus) for the current boss phase."""
    if not enemy.is_boss or not enemy.boss_phases:
        return (0, 0)
    if enemy.boss_phase < len(enemy.boss_phases):
        phase = enemy.boss_phases[enemy.boss_phase]
        return (phase.get("attack_bonus", 0), phase.get("defense_bonus", 0))
    return (0, 0)


def resolve_round(character: Character, combat: Combat) -> list[str]:
    log = []
    enemy = combat.enemy
    strategy = combat.ai_strategy

    # Boss: override strategy with phase strategy & disable flee
    boss_is_defending = False
    if enemy.is_boss:
        if strategy == "flee":
            strategy = "attack"
            combat.ai_strategy = "attack"
        if enemy.boss_phases and enemy.boss_phase < len(enemy.boss_phases):
            phase = enemy.boss_phases[enemy.boss_phase]
            forced_strategy = phase.get("strategy")
            if forced_strategy == "defend":
                # Boss is defensive this phase — reduce boss attack damage later
                boss_is_defending = True

    # Player attacks
    if strategy == "flee":
        if random.random() < 0.5:
            log.append(f"You flee from the {enemy.name}!")
            combat.enemy.hp = 0  # signal flee success
            return log
        else:
            log.append(f"You failed to flee from the {enemy.name}!")
            # Take extra damage
            enemy_dmg, enemy_roll = calc_damage(
                enemy.attack, character.effective_defense
            )
            enemy_dmg = int(enemy_dmg * 1.5)
            character.hp = max(0, character.hp - enemy_dmg)
            if enemy_roll == 6:
                log.append(
                    f"The {enemy.name} critically strikes you for {enemy_dmg} damage!"
                )
            elif enemy_roll == 1:
                log.append(f"The {enemy.name} misses you!")
            else:
                log.append(
                    f"The {enemy.name} hits you for "
                    f"{enemy_dmg} damage while you stumble!"
                )
            combat.turn += 1
            return log

    player_dmg, player_roll = calc_damage(
        character.effective_attack, enemy.defense + _get_boss_phase_bonuses(enemy)[1]
    )

    if strategy == "defend":
        player_dmg = max(1, player_dmg // 2)

    if player_roll == 6:
        log.append(
            f"Critical hit! You strike the {enemy.name} for {player_dmg} damage!"
        )
    elif player_roll == 1:
        log.append(f"You miss the {enemy.name}!")
        player_dmg = 0
    else:
        log.append(f"You strike the {enemy.name} for {player_dmg} damage!")

    enemy.hp = max(0, enemy.hp - player_dmg)

    # Check boss phase transition
    new_phase = check_boss_phase(enemy)
    if new_phase is not None:
        log.append(f"[BOSS_PHASE:{new_phase}]")

    if not enemy.is_alive():
        log.append(f"The {enemy.name} is defeated!")
        return log

    # Enemy attacks — apply boss phase bonuses
    boss_atk_bonus, _ = _get_boss_phase_bonuses(enemy)
    if boss_is_defending:
        boss_atk_bonus //= 2
    enemy_dmg, enemy_roll = calc_damage(
        enemy.attack + boss_atk_bonus, character.effective_defense
    )

    if strategy == "defend":
        enemy_dmg = max(1, enemy_dmg // 2)

    if enemy_roll == 6:
        log.append(f"The {enemy.name} critically strikes you for {enemy_dmg} damage!")
    elif enemy_roll == 1:
        log.append(f"The {enemy.name} misses you!")
        enemy_dmg = 0
    else:
        log.append(f"The {enemy.name} hits you for {enemy_dmg} damage!")

    character.hp = max(0, character.hp - enemy_dmg)

    # Auto-use potion if HP is low
    if character.is_alive():
        potion_log = try_auto_potion(character)
        log.extend(potion_log)

    if not character.is_alive():
        log.append("You have been slain!")

    combat.turn += 1
    return log


def try_auto_potion(character: Character, threshold: float = 0.3) -> list[str]:
    log = []
    if character.max_hp <= 0:
        return log
    hp_pct = character.hp / character.max_hp
    if hp_pct < threshold:
        for item in character.inventory:
            if item.item_type == "consumable" and item.effect_type == "heal":
                heal_amount = min(item.effect_value, character.max_hp - character.hp)
                character.hp += heal_amount
                character.inventory.remove(item)
                log.append(
                    f"Auto-used {item.name}! "
                    f"Restored {heal_amount} HP. "
                    f"({character.hp}/{character.max_hp})"
                )
                break
    return log


def apply_stat_growth(character: Character) -> list[str]:
    log = []
    for stat_name in ("attack", "defense", "max_hp"):
        current = getattr(character, stat_name)
        chance = 1.0 / (1.0 + current * 0.1)
        if random.random() < chance:
            new_val = current + 1
            setattr(character, stat_name, new_val)
            display = stat_name.replace("_", " ").title()
            log.append(f"Your {display} increased to {new_val}!")
    return log

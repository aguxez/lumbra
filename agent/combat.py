import random
from game_state import Character, Enemy, Combat


def calc_damage(attacker_attack: int, defender_defense: int) -> tuple[int, int]:
    base_damage = attacker_attack - defender_defense // 2
    dice_roll = random.randint(1, 6)
    final_damage = max(1, base_damage + dice_roll - 3)

    if dice_roll == 6:
        final_damage *= 2
    elif dice_roll == 1:
        final_damage = 0

    return final_damage, dice_roll


def resolve_round(character: Character, combat: Combat) -> list[str]:
    log = []
    enemy = combat.enemy
    strategy = combat.ai_strategy

    # Player attacks
    if strategy == "flee":
        if random.random() < 0.5:
            log.append(f"You flee from the {enemy.name}!")
            combat.enemy.hp = 0  # signal flee success
            return log
        else:
            log.append(f"You failed to flee from the {enemy.name}!")
            # Take extra damage
            enemy_dmg, enemy_roll = calc_damage(enemy.attack, character.defense)
            enemy_dmg = int(enemy_dmg * 1.5)
            character.hp = max(0, character.hp - enemy_dmg)
            if enemy_roll == 6:
                log.append(f"The {enemy.name} critically strikes you for {enemy_dmg} damage!")
            elif enemy_roll == 1:
                log.append(f"The {enemy.name} misses you!")
            else:
                log.append(f"The {enemy.name} hits you for {enemy_dmg} damage while you stumble!")
            combat.turn += 1
            return log

    player_dmg, player_roll = calc_damage(character.attack, enemy.defense)

    if strategy == "defend":
        player_dmg = max(1, player_dmg // 2)

    if player_roll == 6:
        log.append(f"Critical hit! You strike the {enemy.name} for {player_dmg} damage!")
    elif player_roll == 1:
        log.append(f"You miss the {enemy.name}!")
        player_dmg = 0
    else:
        log.append(f"You strike the {enemy.name} for {player_dmg} damage!")

    enemy.hp = max(0, enemy.hp - player_dmg)

    if not enemy.is_alive():
        log.append(f"The {enemy.name} is defeated!")
        return log

    # Enemy attacks
    enemy_dmg, enemy_roll = calc_damage(enemy.attack, character.defense)

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

    if not character.is_alive():
        log.append("You have been slain!")

    combat.turn += 1
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

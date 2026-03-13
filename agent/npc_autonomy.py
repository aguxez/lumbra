"""NPC autonomy — movement between zones and dynamic offer filtering."""

from __future__ import annotations

import random

from config_loader import NPCS, ZONES, get_zone

# Zone name → danger level lookup
# Safe: ZONES is immutable after config load
_ZONE_DANGER: dict[str, int] = {z["name"]: z["danger"] for z in ZONES}


def tick_npc_movement(state) -> None:
    """Advance NPC movement each tick. Called from main loop."""
    for npc in NPCS:
        movement = npc.get("movement")
        if not movement or movement.get("pattern") == "home":
            continue

        npc_name = npc["name"]
        pace = movement.get("pace", 20)
        entry = state.npc_world.get(npc_name, {})
        last_move = entry.get("move_tick", 0)

        if state.tick - last_move < pace:
            continue

        current_zone = entry.get("current_zone", npc["zone"])

        # Night return check
        if movement.get("night_return") and state.is_night:
            if current_zone != npc["zone"]:
                _move_npc(state, npc, current_zone, npc["zone"])
            continue

        new_zone = _pick_destination(npc, movement, current_zone)
        if new_zone and new_zone != current_zone:
            _move_npc(state, npc, current_zone, new_zone)


def _move_npc(state, npc: dict, from_zone: str, to_zone: str) -> None:
    """Move an NPC and generate logs if the player is in an affected zone."""
    npc_name = npc["name"]
    state.npc_world[npc_name] = {
        "current_zone": to_zone,
        "move_tick": state.tick,
    }

    # Log arrival/departure if player is in the affected zone
    if state.zone == from_zone:
        state.add_log(f"{npc_name} departs from the {from_zone}.")
    if state.zone == to_zone:
        state.add_log(f"{npc_name} arrives in the {to_zone}.")


def _pick_destination(npc: dict, movement: dict, current_zone: str) -> str | None:
    """Dispatch to the appropriate movement pattern."""
    pattern = movement.get("pattern", "home")

    if pattern == "wander":
        return _wander_dest(npc["zone"], current_zone, movement.get("range", 3))
    elif pattern == "route":
        return _route_dest(movement.get("route", []), current_zone)
    elif pattern == "pilgrimage":
        return _pilgrimage_dest(
            npc["zone"], movement.get("destination", npc["zone"]), current_zone
        )
    return None


def _wander_dest(home_zone: str, current_zone: str, range_val: int) -> str:
    """Random zone within `range` danger levels of home, 40% bias to return home."""
    if random.random() < 0.4:
        return home_zone

    home_danger = _ZONE_DANGER.get(home_zone, 1)
    candidates = [
        z["name"]
        for z in ZONES
        if abs(z["danger"] - home_danger) <= range_val and z["name"] != current_zone
    ]
    if not candidates:
        return home_zone
    return random.choice(candidates)


def _route_dest(route: list[str], current_zone: str) -> str:
    """Next zone in a cyclic route."""
    if not route:
        return current_zone
    try:
        idx = route.index(current_zone)
        return route[(idx + 1) % len(route)]
    except ValueError:
        return route[0]


def _pilgrimage_dest(home_zone: str, far_zone: str, current_zone: str) -> str:
    """Return far_zone if at home, otherwise return home_zone (fallback-safe)."""
    if current_zone == home_zone:
        return far_zone
    return home_zone


# --- Dynamic offer helpers ---


def get_available_trades(
    npc: dict, zone: str, affinity: int, is_night: bool
) -> list[dict]:
    """Filter trades by zone danger, affinity, and time-of-day conditions."""
    zone_data = get_zone(zone)
    zone_danger = zone_data["danger"] if zone_data else 0

    available = []
    for trade in npc.get("trades", []):
        if affinity < trade.get("min_affinity", 0):
            continue
        if zone_danger < trade.get("zone_danger_min", 0):
            continue
        if trade.get("night_only") and not is_night:
            continue
        available.append(trade)
    return available


def scale_buff(buff: dict, affinity: int) -> int:
    """Compute effective buff value with affinity bonus scaling."""
    base = buff.get("value", 0)
    bonus_per_tier = buff.get("affinity_bonus", 0)
    # Bonus tiers: 0-29 = +0, 30-59 = +1, 60-89 = +2, etc.
    if bonus_per_tier and affinity > 0:
        base += (affinity // 30) * bonus_per_tier
    return base

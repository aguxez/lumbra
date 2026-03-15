"""NPC autonomy — movement between zones and dynamic offer filtering."""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING

from config_loader import NPCS, ZONES, get_npc, get_zone
from economy import (
    NPC_MAX_SPEND_RATIO,
    NPC_NEEDS_COOLDOWN,
    NPC_TRADE_COOLDOWN,
    NPCNeed,
    NPCTrade,
    base_price,
    execute_npc_trade,
    fallback_negotiate,
    fallback_npc_needs,
    find_trade_candidates,
)

if TYPE_CHECKING:
    from economy import EconomyState
    from game_state import GameState

logger = logging.getLogger(__name__)

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


def tick_npc_trades(
    state: GameState,
    economy: EconomyState,
    tokenizer=None,
    model=None,
    ai_brain_mod=None,
) -> list[str]:
    """Run NPC-to-NPC trading for co-located NPCs each tick."""
    logs: list[str] = []

    # Early exit: skip if all NPCs are still on cooldown
    if all(
        state.tick - economy.npc_last_trade_tick.get(npc["name"], 0)
        < NPC_TRADE_COOLDOWN
        for npc in NPCS
    ):
        return logs

    has_ai = tokenizer is not None and model is not None and ai_brain_mod is not None

    # 1. Compute needs per NPC
    needs_by_npc: dict[str, list[NPCNeed]] = {}
    for npc_cfg in NPCS:
        name = npc_cfg["name"]
        role = npc_cfg.get("role", "wanderer")
        ms = economy.merchant_states.get(name)
        if not ms:
            continue

        # Skip AI evaluation for NPCs still on trade cooldown
        if state.tick - economy.npc_last_trade_tick.get(name, 0) < NPC_TRADE_COOLDOWN:
            fallback = fallback_npc_needs(ms, role)
            if fallback:
                needs_by_npc[name] = fallback
            continue

        # Use cached needs if still fresh
        last_needs = economy.npc_last_needs_tick.get(name, 0)
        if (
            state.tick - last_needs < NPC_NEEDS_COOLDOWN
            and name in economy.npc_cached_needs
        ):
            cached = [
                NPCNeed(
                    item_type=d["item_type"],
                    priority=d["priority"],
                    max_price=d["max_price"],
                    reason=d["reason"],
                )
                for d in economy.npc_cached_needs[name]
            ]
            if cached:
                needs_by_npc[name] = cached
            continue

        ai_needs: list[NPCNeed] | None = None
        if has_ai:
            assert ai_brain_mod is not None
            try:
                # Build inventory summary
                type_counts: dict[str, int] = {}
                for item in ms.inventory:
                    type_counts[item.item_type] = type_counts.get(item.item_type, 0) + 1
                inv_summary = ", ".join(
                    f"{count} {t}" for t, count in type_counts.items()
                )
                if not inv_summary:
                    inv_summary = "empty"

                # Find nearby NPCs
                entry = state.npc_world.get(name, {})
                current_zone = entry.get("current_zone", npc_cfg.get("zone", ""))
                nearby: list[str] = []
                for other in NPCS:
                    if other["name"] == name:
                        continue
                    other_entry = state.npc_world.get(other["name"], {})
                    other_zone = other_entry.get("current_zone", other.get("zone", ""))
                    if other_zone == current_zone:
                        nearby.append(other["name"])

                result = ai_brain_mod.evaluate_npc_needs(
                    tokenizer,
                    model,
                    name,
                    role,
                    current_zone,
                    inv_summary,
                    ms.gold,
                    state.is_night,
                    nearby,
                )
                if result:
                    ai_needs = [
                        NPCNeed(
                            item_type=it,
                            priority=pri,
                            max_price=int(ms.gold * NPC_MAX_SPEND_RATIO),
                            reason=reason,
                        )
                        for it, pri, reason in result
                    ]
            except Exception:
                logger.debug("AI needs evaluation failed for %s", name, exc_info=True)

        computed = ai_needs or fallback_npc_needs(ms, role)

        if computed:
            needs_by_npc[name] = computed

        # Cache computed needs
        economy.npc_cached_needs[name] = [
            {
                "item_type": n.item_type,
                "priority": n.priority,
                "max_price": n.max_price,
                "reason": n.reason,
            }
            for n in computed
        ]
        economy.npc_last_needs_tick[name] = state.tick

    if not needs_by_npc:
        return logs

    # 2. Find trade candidates
    candidates = find_trade_candidates(
        economy, NPCS, state.npc_world, state.tick, needs_by_npc
    )

    # 3. Negotiate and execute each candidate
    for buyer_name, seller_name, item_name, need in candidates:
        buyer_ms = economy.merchant_states.get(buyer_name)
        seller_ms = economy.merchant_states.get(seller_name)
        if not buyer_ms or not seller_ms:
            continue

        # Find the item to get its fair price
        item = next((i for i in seller_ms.inventory if i.name == item_name), None)
        if not item:
            continue
        fair = base_price(item)

        # Negotiate
        final_action = "refuse"
        final_price = 0
        reason = need.reason

        if has_ai:
            assert ai_brain_mod is not None
            try:
                buyer_npc = get_npc(buyer_name)
                buyer_role = (
                    buyer_npc.get("role", "wanderer") if buyer_npc else "wanderer"
                )
                entry = state.npc_world.get(buyer_name, {})
                zone = entry.get("current_zone", "")

                offer_result = ai_brain_mod.npc_make_offer(
                    tokenizer,
                    model,
                    buyer_name,
                    buyer_role,
                    zone,
                    buyer_ms.gold,
                    need.reason,
                    seller_name,
                    item_name,
                    fair,
                )
                if offer_result:
                    action, price, offer_reason = offer_result
                    if action == "skip":
                        logs.append(
                            f"[NPC] {buyer_name} decided not to buy "
                            f"{item_name} from {seller_name} ({offer_reason})"
                        )
                        continue
                    if action == "offer" and price > 0:
                        seller_npc = get_npc(seller_name)
                        seller_role = (
                            seller_npc.get("role", "wanderer")
                            if seller_npc
                            else "wanderer"
                        )
                        response = ai_brain_mod.npc_respond_offer(
                            tokenizer,
                            model,
                            seller_name,
                            seller_role,
                            zone,
                            seller_ms.gold,
                            len(seller_ms.inventory),
                            buyer_name,
                            item_name,
                            price,
                            fair,
                        )
                        if response:
                            final_action, final_price, reason = response
                            if final_action == "counter" and final_price > 0:
                                # Accept counter if buyer can afford
                                if buyer_ms.gold >= final_price:
                                    final_action = "accept"
                                else:
                                    final_action = "refuse"
                                    reason = "can't afford counter price"
                            elif final_action == "accept":
                                final_price = price
                else:
                    # LLM returned None, fall back
                    final_action, final_price = fallback_negotiate(buyer_ms.gold, fair)
            except Exception:
                logger.debug(
                    "AI negotiation failed for %s -> %s",
                    buyer_name,
                    seller_name,
                    exc_info=True,
                )
                final_action, final_price = fallback_negotiate(buyer_ms.gold, fair)
        else:
            final_action, final_price = fallback_negotiate(buyer_ms.gold, fair)

        if final_action == "accept" and final_price > 0:
            trade = NPCTrade(
                buyer_name=buyer_name,
                seller_name=seller_name,
                item_name=item_name,
                price=final_price,
                barter_item=None,
                buyer_reason=reason,
            )
            logs.extend(execute_npc_trade(economy, trade, state.tick))
        else:
            logs.append(
                f"[NPC] {seller_name} refused to sell {item_name} "
                f"to {buyer_name} ({reason})"
            )

    return logs

"""Economy system — merchant shops, pricing, and player buy/sell."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from config_loader import ITEMS_BY_NAME, NPCS, get_item, get_npc
from game_state import InventoryItem, equip_or_stash

if TYPE_CHECKING:
    from game_state import Character

logger = logging.getLogger(__name__)

RARITY_MULTIPLIER: dict[str, int] = {
    "common": 1,
    "uncommon": 2,
    "rare": 4,
    "epic": 8,
    "legendary": 16,
    "mythic": 32,
}

ROLE_BASE_GOLD: dict[str, int] = {
    "merchant": 200,
    "blacksmith": 150,
    "sage": 80,
    "wanderer": 50,
}

ROLE_GOLD_CAP: dict[str, int] = {
    "merchant": 500,
    "blacksmith": 400,
    "sage": 200,
    "wanderer": 100,
}

# Items each role can stock beyond their configured trades
ROLE_STOCK_TYPES: dict[str, list[str]] = {
    "merchant": ["consumable", "accessory"],
    "blacksmith": ["weapon", "armor", "shield"],
    "sage": ["consumable", "accessory"],
    "wanderer": ["consumable"],
}

LOW_CONSUMABLE_THRESHOLD = 2

RESTOCK_INTERVAL = 30


@dataclass
class MerchantState:
    npc_name: str
    gold: int
    inventory: list[InventoryItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        npc = get_npc(self.npc_name)
        role = npc.get("role", "wanderer") if npc else "wanderer"
        gold_cap = ROLE_GOLD_CAP.get(role, 100)
        return {
            "npc_name": self.npc_name,
            "gold": self.gold,
            "gold_cap": gold_cap,
            "inventory": [
                {
                    "name": i.name,
                    "rarity": i.rarity,
                    "item_type": i.item_type,
                    "attack": i.attack,
                    "defense": i.defense,
                    "effect_type": i.effect_type,
                    "effect_value": i.effect_value,
                }
                for i in self.inventory
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> MerchantState:
        inventory = [
            InventoryItem(
                name=i["name"],
                rarity=i.get("rarity", "common"),
                item_type=i.get("item_type", "accessory"),
                attack=i.get("attack", 0),
                defense=i.get("defense", 0),
                effect_type=i.get("effect_type"),
                effect_value=i.get("effect_value", 0),
            )
            for i in data.get("inventory", [])
        ]
        return cls(
            npc_name=data["npc_name"],
            gold=data.get("gold", 0),
            inventory=inventory,
        )


@dataclass
class TradeRecord:
    tick: int
    merchant_name: str
    action: str  # "buy", "sell", "barter", "npc_buy", "npc_barter"
    item_name: str
    price: int

    def to_dict(self) -> dict:
        return {
            "tick": self.tick,
            "merchant_name": self.merchant_name,
            "action": self.action,
            "item_name": self.item_name,
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TradeRecord:
        return cls(
            tick=data["tick"],
            merchant_name=data["merchant_name"],
            action=data["action"],
            item_name=data["item_name"],
            price=data.get("price", 0),
        )


TRADE_HISTORY_CAP = 30

NPC_TRADE_COOLDOWN = 5

NPC_MAX_SPEND_RATIO = 0.6

ROLE_NEED_RULES: dict[str, list[tuple[str, int, int]]] = {
    # (item_type, threshold, priority)
    "blacksmith": [("consumable", 1, 6), ("weapon", 3, 4), ("armor", 3, 4)],
    "merchant": [("consumable", 2, 5), ("accessory", 1, 4), ("weapon", 1, 3)],
    "sage": [("consumable", 2, 6), ("accessory", 1, 4)],
    "wanderer": [("consumable", 1, 7)],
}


@dataclass
class NPCNeed:
    item_type: str
    priority: int
    max_price: int
    reason: str


@dataclass
class NPCTrade:
    buyer_name: str
    seller_name: str
    item_name: str
    price: int  # 0 for barter
    barter_item: str | None  # item given in exchange (barter only)
    buyer_reason: str


@dataclass
class EconomyState:
    merchant_states: dict[str, MerchantState] = field(default_factory=dict)
    last_restock_tick: int = 0
    trade_history: list[TradeRecord] = field(default_factory=list)
    price_adjustments: dict[str, float] = field(default_factory=dict)
    market_news: str = ""
    npc_last_trade_tick: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "merchant_states": {
                name: ms.to_dict() for name, ms in self.merchant_states.items()
            },
            "last_restock_tick": self.last_restock_tick,
            "trade_history": [t.to_dict() for t in self.trade_history],
            "price_adjustments": self.price_adjustments,
            "market_news": self.market_news,
            "npc_last_trade_tick": self.npc_last_trade_tick,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EconomyState:
        try:
            merchant_states = {
                name: MerchantState.from_dict(ms_data)
                for name, ms_data in data.get("merchant_states", {}).items()
            }
            trade_history = [
                TradeRecord.from_dict(t) for t in data.get("trade_history", [])
            ]
            return cls(
                merchant_states=merchant_states,
                last_restock_tick=data.get("last_restock_tick", 0),
                trade_history=trade_history,
                price_adjustments=data.get("price_adjustments", {}),
                market_news=data.get("market_news", ""),
                npc_last_trade_tick=data.get("npc_last_trade_tick", {}),
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Corrupt economy data, reinitializing: %s", e)
            return cls()


def base_price(item: InventoryItem) -> int:
    """Calculate the base price for an item based on stats and rarity."""
    stat_value = item.attack + item.defense + item.effect_value
    mult = RARITY_MULTIPLIER.get(item.rarity, 1)
    return max(5, stat_value * mult + mult * 3)


def buy_price(
    item: InventoryItem, price_adjustments: dict[str, float] | None = None
) -> int:
    """Price the player pays to buy from a merchant."""
    mult = (price_adjustments or {}).get(item.name, 1.0)
    return max(5, int(base_price(item) * mult))


def sell_price(
    item: InventoryItem, price_adjustments: dict[str, float] | None = None
) -> int:
    """Price the merchant pays the player for an item."""
    mult = (price_adjustments or {}).get(item.name, 1.0)
    return max(1, int(base_price(item) * 0.4 * mult))


def _get_role_items(role: str) -> list[dict]:
    """Get config items appropriate for a given NPC role."""
    allowed_types = ROLE_STOCK_TYPES.get(role, ["consumable"])
    return [
        item_data
        for item_data in ITEMS_BY_NAME.values()
        if item_data.get("type") in allowed_types
        and item_data.get("rarity", "common") in ("common", "uncommon", "rare")
    ]


def record_trade(
    economy: EconomyState,
    tick: int,
    merchant_name: str,
    action: str,
    item_name: str,
    price: int,
) -> None:
    """Append a trade record and cap history length."""
    economy.trade_history.append(
        TradeRecord(
            tick=tick,
            merchant_name=merchant_name,
            action=action,
            item_name=item_name,
            price=price,
        )
    )
    if len(economy.trade_history) > TRADE_HISTORY_CAP:
        economy.trade_history = economy.trade_history[-TRADE_HISTORY_CAP:]


def _init_merchant_for_npc(npc: dict) -> MerchantState:
    """Create a fresh MerchantState for one NPC config entry."""
    npc_name = npc["name"]
    role = npc.get("role", "wanderer")
    starting_gold = npc.get("base_gold", ROLE_BASE_GOLD.get(role, 50))

    inventory: list[InventoryItem] = []
    for trade in npc.get("trades", []):
        offer_name = trade.get("offer")
        if offer_name:
            item_data = get_item(offer_name)
            if item_data:
                inventory.append(InventoryItem.from_config(item_data))

    role_items = _get_role_items(role)
    if role_items:
        extras = random.sample(role_items, min(2, len(role_items)))
        for item_data in extras:
            if not any(i.name == item_data["name"] for i in inventory):
                inventory.append(InventoryItem.from_config(item_data))

    return MerchantState(npc_name=npc_name, gold=starting_gold, inventory=inventory)


def init_economy() -> EconomyState:
    """Initialize economy with merchant states for all NPCs."""
    economy = EconomyState()
    for npc in NPCS:
        economy.merchant_states[npc["name"]] = _init_merchant_for_npc(npc)
    return economy


def load_or_init_economy(economy_data: dict) -> EconomyState:
    """Load economy from saved data, or initialize fresh if empty."""
    if economy_data and economy_data.get("merchant_states"):
        economy = EconomyState.from_dict(economy_data)
        # If from_dict returned empty (corrupt data), reinitialize
        if not economy.merchant_states:
            return init_economy()
        # Reconcile: remove stale merchants, add missing ones
        npc_names = {npc["name"] for npc in NPCS}
        stale = [name for name in economy.merchant_states if name not in npc_names]
        for name in stale:
            del economy.merchant_states[name]
        for npc in NPCS:
            if npc["name"] not in economy.merchant_states:
                economy.merchant_states[npc["name"]] = _init_merchant_for_npc(npc)
        return economy
    return init_economy()


def restock_merchants(economy: EconomyState, tick: int) -> list[str]:
    """Periodically restock merchant inventories and add passive gold."""
    if tick - economy.last_restock_tick < RESTOCK_INTERVAL:
        return []

    economy.last_restock_tick = tick
    logs: list[str] = []

    for ms in economy.merchant_states.values():
        npc = get_npc(ms.npc_name)
        if not npc:
            continue

        role = npc.get("role", "wanderer")

        # Passive gold income (capped by role)
        cap = ROLE_GOLD_CAP.get(role, 100)
        gold_income = random.randint(5, 15)
        ms.gold = min(ms.gold + gold_income, cap)

        # Restock 1-2 items if inventory is low (< 4 items)
        if len(ms.inventory) < 4:
            role_items = _get_role_items(role)
            if role_items:
                new_item_data = random.choice(role_items)
                if not any(i.name == new_item_data["name"] for i in ms.inventory):
                    ms.inventory.append(InventoryItem.from_config(new_item_data))
                    logs.append(
                        f"[RESTOCK] {ms.npc_name} restocked: "
                        f"{new_item_data['name']} now available."
                    )

    return logs


def resolve_player_buy(
    character: Character,
    merchant: MerchantState,
    item_name: str,
    price_adjustments: dict[str, float] | None = None,
) -> list[str]:
    """Player buys an item from a merchant."""
    logs: list[str] = []

    # Find the item in merchant inventory
    item_idx = next(
        (i for i, item in enumerate(merchant.inventory) if item.name == item_name),
        None,
    )
    if item_idx is None:
        logs.append(f"{merchant.npc_name} doesn't have {item_name}.")
        return logs

    item = merchant.inventory[item_idx]
    price = buy_price(item, price_adjustments)

    if character.gold < price:
        logs.append(
            f"Not enough gold for {item_name} ({price}g). You have {character.gold}g."
        )
        return logs

    # Execute purchase
    character.gold -= price
    merchant.gold += price
    bought_item = merchant.inventory.pop(item_idx)
    mult = (price_adjustments or {}).get(item_name, 1.0)
    msg = f"[TRADE] Bought {item_name} from {merchant.npc_name} for {price}g!"
    if abs(mult - 1.0) > 1e-6:
        msg += f" Market rate: {mult:.0%} of base."
    logs.append(msg)
    logs.extend(equip_or_stash(character, bought_item))
    return logs


def resolve_player_sell(
    character: Character,
    merchant: MerchantState,
    item_name: str,
    price_adjustments: dict[str, float] | None = None,
) -> list[str]:
    """Player sells an item to a merchant."""
    logs: list[str] = []

    # Find item in player inventory (not equipped items — don't sell equipped gear)
    item_idx = next(
        (i for i, item in enumerate(character.inventory) if item.name == item_name),
        None,
    )
    if item_idx is None:
        logs.append(f"You don't have {item_name} to sell.")
        return logs

    item = character.inventory[item_idx]
    price = sell_price(item, price_adjustments)

    if merchant.gold < price:
        logs.append(f"{merchant.npc_name} can't afford to buy {item_name}.")
        return logs

    # Execute sale
    sold_item = character.inventory.pop(item_idx)
    character.gold += price
    merchant.gold -= price
    merchant.inventory.append(sold_item)
    mult = (price_adjustments or {}).get(item_name, 1.0)
    msg = f"[TRADE] Sold {item_name} to {merchant.npc_name} for {price}g!"
    if abs(mult - 1.0) > 1e-6:
        msg += f" Market rate: {mult:.0%} of base."
    logs.append(msg)
    return logs


def is_upgrade(item: InventoryItem, character: Character) -> bool:
    """Check if an item would be an upgrade over current equipment."""
    if item.item_type == "weapon":
        cur = character.equipped_weapon
        current_atk = cur.attack if cur else 0
        return item.attack > current_atk
    if item.item_type in ("armor", "shield"):
        cur = character.equipped_armor
        current_def = cur.defense if cur else 0
        return item.defense > current_def
    if item.item_type == "accessory":
        current_power = 0
        if character.equipped_accessory:
            current_power = (
                character.equipped_accessory.attack
                + character.equipped_accessory.defense
            )
        return (item.attack + item.defense) > current_power
    if item.item_type == "consumable":
        count = sum(1 for i in character.inventory if i.item_type == "consumable")
        return count < LOW_CONSUMABLE_THRESHOLD
    return False


def get_trade_options(
    character: Character,
    merchant: MerchantState,
    price_adjustments: dict[str, float] | None = None,
) -> list[tuple[str, str, int, bool]]:
    """Build list of (action, item_name, price, is_upgrade) options for AI trade.

    Returns up to 3 options: best buy, best sell, skip.
    """
    options: list[tuple[str, str, int, bool]] = []

    # Find best buyable item (highest stat value the player can afford)
    affordable = [
        (item, p)
        for item in merchant.inventory
        if (p := buy_price(item, price_adjustments)) <= character.gold
    ]
    if affordable:
        best = max(
            affordable,
            key=lambda x: x[0].attack + x[0].defense + x[0].effect_value,
        )
        upgrade = is_upgrade(best[0], character)
        options.append(("buy", best[0].name, best[1], upgrade))

    # Find best sellable item (lowest value non-equipped item)
    consumable_count = sum(
        1 for i in character.inventory if i.item_type == "consumable"
    )
    sellable = [
        (item, sp)
        for item in character.inventory
        if (
            item.item_type != "consumable"
            or consumable_count > LOW_CONSUMABLE_THRESHOLD
        )
        and (sp := sell_price(item, price_adjustments)) <= merchant.gold
    ]
    if sellable:
        worst = min(
            sellable,
            key=lambda x: x[0].attack + x[0].defense + x[0].effect_value,
        )
        options.append(("sell", worst[0].name, worst[1], False))

    options.append(("skip", "", 0, False))
    return options


def fallback_trade_decision(
    character: Character,
    merchant: MerchantState,
    price_adjustments: dict[str, float] | None = None,
) -> tuple[str, str, str]:
    """Heuristic trade decision. Returns (action, item_name, reason)."""
    # 1. Buy potions if low on consumables
    consumable_count = sum(
        1 for i in character.inventory if i.item_type == "consumable"
    )
    if consumable_count < LOW_CONSUMABLE_THRESHOLD:
        for item in merchant.inventory:
            if item.item_type == "consumable" and item.effect_type == "heal":
                price = buy_price(item, price_adjustments)
                if character.gold >= price:
                    reason = (
                        f"Need healing supplies"
                        f" — only {consumable_count}"
                        f" potions left."
                        f" {item.name} for {price}g."
                    )
                    return ("buy", item.name, reason)

    # 2. Buy weapon upgrade if affordable
    cur_w = character.equipped_weapon
    current_atk = cur_w.attack if cur_w else 0
    cur_w_name = cur_w.name if cur_w else "bare fists"
    for item in merchant.inventory:
        if item.item_type == "weapon" and item.attack > current_atk:
            price = buy_price(item, price_adjustments)
            if character.gold >= price:
                reason = (
                    f"Found {item.name}"
                    f" (+{item.attack} ATK)"
                    f" — upgrade from {cur_w_name}"
                    f" (+{current_atk} ATK)"
                    f" for {price}g."
                )
                return ("buy", item.name, reason)

    # 3. Buy armor upgrade if affordable
    cur_a = character.equipped_armor
    current_def = cur_a.defense if cur_a else 0
    cur_a_name = cur_a.name if cur_a else "no armor"
    for item in merchant.inventory:
        if item.item_type in ("armor", "shield") and item.defense > current_def:
            price = buy_price(item, price_adjustments)
            if character.gold >= price:
                reason = (
                    f"Found {item.name}"
                    f" (+{item.defense} DEF)"
                    f" — upgrade from {cur_a_name}"
                    f" (+{current_def} DEF)"
                    f" for {price}g."
                )
                return ("buy", item.name, reason)

    # 4. Sell junk (non-equipped, non-consumable items with low stats)
    for item in character.inventory:
        if item.item_type == "consumable":
            continue
        is_worse_weapon = (
            item.item_type == "weapon"
            and character.equipped_weapon
            and item.attack <= character.equipped_weapon.attack
        )
        is_worse_armor = (
            item.item_type in ("armor", "shield")
            and character.equipped_armor
            and item.defense <= character.equipped_armor.defense
        )
        if (is_worse_weapon or is_worse_armor) and (
            sp := sell_price(item, price_adjustments)
        ) <= merchant.gold:
            return (
                "sell",
                item.name,
                f"Selling {item.name} — weaker than equipped gear. +{sp}g.",
            )

    return ("skip", "", "Nothing worth trading.")


def build_merchant_summaries(economy: EconomyState) -> list[dict[str, object]]:
    """Build merchant summary dicts for AI market evaluation."""
    summaries: list[dict[str, object]] = []
    for ms in economy.merchant_states.values():
        npc = get_npc(ms.npc_name)
        role = npc.get("role", "wanderer") if npc else "wanderer"
        summaries.append(
            {
                "name": ms.npc_name,
                "role": role,
                "gold": ms.gold,
                "items": [i.name for i in ms.inventory],
            }
        )
    return summaries


def total_system_gold(character: Character, economy: EconomyState) -> int:
    """Sum all gold in the system (player + all merchants). Trade-only invariant."""
    total = character.gold
    for ms in economy.merchant_states.values():
        total += ms.gold
    return total


def fallback_npc_needs(merchant: MerchantState, role: str) -> list[NPCNeed]:
    """Generate NPC needs using static role-based rules."""
    rules = ROLE_NEED_RULES.get(role, [("consumable", 1, 5)])
    needs: list[NPCNeed] = []
    for item_type, threshold, priority in rules:
        count = sum(1 for i in merchant.inventory if i.item_type == item_type)
        if count < threshold:
            max_price = int(merchant.gold * NPC_MAX_SPEND_RATIO)
            reason = f"Running low on {item_type}s (have {count}, want {threshold})"
            needs.append(NPCNeed(item_type, priority, max_price, reason))
    return needs


def fallback_negotiate(buyer_gold: int, fair_price: int) -> tuple[str, int]:
    """Hardcoded negotiation: buyer offers 70% of fair price."""
    offered = max(1, int(fair_price * 0.7))
    floor = max(1, int(fair_price * 0.5))
    if offered >= floor and buyer_gold >= offered:
        return ("accept", offered)
    return ("refuse", 0)


def find_trade_candidates(
    economy: EconomyState,
    npc_configs: list[dict],
    npc_world: dict[str, dict],
    tick: int,
    needs_by_npc: dict[str, list[NPCNeed]],
) -> list[tuple[str, str, str, NPCNeed]]:
    """Find NPC pairs where one has what the other needs.

    Returns (buyer_name, seller_name, item_name, need) sorted by priority.
    Each NPC appears in at most one candidate (greedy assignment).
    """
    # Group NPCs by current zone
    zone_npcs: dict[str, list[str]] = {}
    for npc in npc_configs:
        name = npc["name"]
        entry = npc_world.get(name, {})
        zone = entry.get("current_zone", npc.get("zone", ""))
        zone_npcs.setdefault(zone, []).append(name)

    raw_candidates: list[tuple[str, str, str, NPCNeed]] = []

    for _zone, names in zone_npcs.items():
        if len(names) < 2:
            continue
        for buyer_name in names:
            # Skip if on cooldown
            last = economy.npc_last_trade_tick.get(buyer_name, 0)
            if tick - last < NPC_TRADE_COOLDOWN:
                continue
            buyer_needs = needs_by_npc.get(buyer_name, [])
            if not buyer_needs:
                continue
            buyer_ms = economy.merchant_states.get(buyer_name)
            if not buyer_ms or buyer_ms.gold <= 0:
                continue
            for seller_name in names:
                if seller_name == buyer_name:
                    continue
                last_s = economy.npc_last_trade_tick.get(seller_name, 0)
                if tick - last_s < NPC_TRADE_COOLDOWN:
                    continue
                seller_ms = economy.merchant_states.get(seller_name)
                if not seller_ms or not seller_ms.inventory:
                    continue
                for need in buyer_needs:
                    for item in seller_ms.inventory:
                        if item.item_type == need.item_type:
                            price = base_price(item)
                            if price <= need.max_price and price <= buyer_ms.gold:
                                raw_candidates.append(
                                    (buyer_name, seller_name, item.name, need)
                                )
                                break
                    else:
                        continue
                    break

    # Sort by priority (highest first) and greedily assign
    raw_candidates.sort(key=lambda c: c[3].priority, reverse=True)
    used: set[str] = set()
    result: list[tuple[str, str, str, NPCNeed]] = []
    for buyer, seller, item_name, need in raw_candidates:
        if buyer not in used and seller not in used:
            result.append((buyer, seller, item_name, need))
            used.add(buyer)
            used.add(seller)
    return result


def execute_npc_trade(economy: EconomyState, trade: NPCTrade, tick: int) -> list[str]:
    """Execute an NPC-to-NPC trade: move item and gold, record history."""
    buyer_ms = economy.merchant_states.get(trade.buyer_name)
    seller_ms = economy.merchant_states.get(trade.seller_name)
    if not buyer_ms or not seller_ms:
        return []

    # Find item in seller inventory
    item_idx = next(
        (i for i, it in enumerate(seller_ms.inventory) if it.name == trade.item_name),
        None,
    )
    if item_idx is None:
        return []

    logs: list[str] = []
    item = seller_ms.inventory.pop(item_idx)

    if trade.barter_item:
        # Barter: swap items
        barter_idx = next(
            (
                i
                for i, it in enumerate(buyer_ms.inventory)
                if it.name == trade.barter_item
            ),
            None,
        )
        if barter_idx is None:
            # Buyer doesn't have the barter item — abort trade, return item to seller
            seller_ms.inventory.append(item)
            return []
        barter_item = buyer_ms.inventory.pop(barter_idx)
        seller_ms.inventory.append(barter_item)
        buyer_ms.inventory.append(item)
        action = "npc_barter"
        logs.append(
            f"[NPC TRADE] {trade.buyer_name} traded {trade.barter_item} "
            f"to {trade.seller_name} for {trade.item_name} "
            f"({trade.buyer_reason})"
        )
    else:
        # Gold purchase
        buyer_ms.gold -= trade.price
        seller_ms.gold += trade.price
        buyer_ms.inventory.append(item)
        action = "npc_buy"
        logs.append(
            f"[NPC TRADE] {trade.buyer_name} bought {trade.item_name} "
            f"from {trade.seller_name} for {trade.price}g "
            f"({trade.buyer_reason})"
        )

    # Record in trade history
    record_trade(economy, tick, trade.seller_name, action, trade.item_name, trade.price)

    # Update cooldowns
    economy.npc_last_trade_tick[trade.buyer_name] = tick
    economy.npc_last_trade_tick[trade.seller_name] = tick

    return logs

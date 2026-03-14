"""Economy system — merchant shops, pricing, and player buy/sell."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from config_loader import ITEMS_BY_NAME, NPCS, get_item
from game_state import InventoryItem

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

# Items each role can stock beyond their configured trades
ROLE_STOCK_TYPES: dict[str, list[str]] = {
    "merchant": ["consumable", "accessory"],
    "blacksmith": ["weapon", "armor", "shield"],
    "sage": ["consumable", "accessory"],
    "wanderer": ["consumable"],
}

RESTOCK_INTERVAL = 30


@dataclass
class MerchantState:
    npc_name: str
    gold: int
    inventory: list[InventoryItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "npc_name": self.npc_name,
            "gold": self.gold,
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
class EconomyState:
    merchant_states: dict[str, MerchantState] = field(default_factory=dict)
    last_restock_tick: int = 0

    def to_dict(self) -> dict:
        return {
            "merchant_states": {
                name: ms.to_dict() for name, ms in self.merchant_states.items()
            },
            "last_restock_tick": self.last_restock_tick,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EconomyState:
        merchant_states = {
            name: MerchantState.from_dict(ms_data)
            for name, ms_data in data.get("merchant_states", {}).items()
        }
        return cls(
            merchant_states=merchant_states,
            last_restock_tick=data.get("last_restock_tick", 0),
        )


def base_price(item: InventoryItem) -> int:
    """Calculate the base price for an item based on stats and rarity."""
    stat_value = item.attack + item.defense + item.effect_value
    mult = RARITY_MULTIPLIER.get(item.rarity, 1)
    return max(5, stat_value * mult + mult * 3)


def buy_price(item: InventoryItem) -> int:
    """Price the player pays to buy from a merchant."""
    return base_price(item)


def sell_price(item: InventoryItem) -> int:
    """Price the merchant pays the player for an item."""
    return max(1, int(base_price(item) * 0.4))


def _get_role_items(role: str) -> list[dict]:
    """Get config items appropriate for a given NPC role."""
    allowed_types = ROLE_STOCK_TYPES.get(role, ["consumable"])
    return [
        item_data
        for item_data in ITEMS_BY_NAME.values()
        if item_data.get("type") in allowed_types
        and item_data.get("rarity", "common") in ("common", "uncommon", "rare")
    ]


def init_economy() -> EconomyState:
    """Initialize economy with merchant states for all NPCs."""
    economy = EconomyState()

    for npc in NPCS:
        npc_name = npc["name"]
        role = npc.get("role", "wanderer")
        starting_gold = npc.get("base_gold", ROLE_BASE_GOLD.get(role, 50))

        # Seed inventory from configured trade offers
        inventory: list[InventoryItem] = []
        for trade in npc.get("trades", []):
            offer_name = trade.get("offer")
            if offer_name:
                item_data = get_item(offer_name)
                if item_data:
                    inventory.append(InventoryItem.from_config(item_data))

        # Add 1-2 role-appropriate items from config
        role_items = _get_role_items(role)
        if role_items:
            extras = random.sample(role_items, min(2, len(role_items)))
            for item_data in extras:
                # Avoid duplicates
                if not any(i.name == item_data["name"] for i in inventory):
                    inventory.append(InventoryItem.from_config(item_data))

        economy.merchant_states[npc_name] = MerchantState(
            npc_name=npc_name,
            gold=starting_gold,
            inventory=inventory,
        )

    return economy


def load_or_init_economy(economy_data: dict) -> EconomyState:
    """Load economy from saved data, or initialize fresh if empty."""
    if economy_data and economy_data.get("merchant_states"):
        return EconomyState.from_dict(economy_data)
    return init_economy()


def restock_merchants(economy: EconomyState, tick: int) -> list[str]:
    """Periodically restock merchant inventories and add passive gold."""
    if tick - economy.last_restock_tick < RESTOCK_INTERVAL:
        return []

    economy.last_restock_tick = tick
    logs: list[str] = []

    for ms in economy.merchant_states.values():
        npc = next((n for n in NPCS if n["name"] == ms.npc_name), None)
        if not npc:
            continue

        role = npc.get("role", "wanderer")

        # Passive gold income
        gold_income = random.randint(5, 15)
        ms.gold += gold_income

        # Restock 1-2 items if inventory is low (< 4 items)
        if len(ms.inventory) < 4:
            role_items = _get_role_items(role)
            if role_items:
                new_item_data = random.choice(role_items)
                if not any(i.name == new_item_data["name"] for i in ms.inventory):
                    ms.inventory.append(InventoryItem.from_config(new_item_data))
                    logs.append(
                        f"{ms.npc_name} restocked: "
                        f"{new_item_data['name']} now available."
                    )

    return logs


def resolve_player_buy(character, merchant: MerchantState, item_name: str) -> list[str]:
    """Player buys an item from a merchant."""
    from main import equip_or_stash

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
    price = buy_price(item)

    if character.gold < price:
        logs.append(
            f"Not enough gold for {item_name} ({price}g). You have {character.gold}g."
        )
        return logs

    # Execute purchase
    character.gold -= price
    merchant.gold += price
    bought_item = merchant.inventory.pop(item_idx)
    logs.append(f"Bought {item_name} from {merchant.npc_name} for {price}g!")
    logs.extend(equip_or_stash(character, bought_item))
    return logs


def resolve_player_sell(
    character, merchant: MerchantState, item_name: str
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
    price = sell_price(item)

    if merchant.gold < price:
        logs.append(f"{merchant.npc_name} can't afford to buy {item_name}.")
        return logs

    # Execute sale
    sold_item = character.inventory.pop(item_idx)
    character.gold += price
    merchant.gold -= price
    merchant.inventory.append(sold_item)
    logs.append(f"Sold {item_name} to {merchant.npc_name} for {price}g!")
    return logs


def get_trade_options(character, merchant: MerchantState) -> list[tuple[str, str, int]]:
    """Build list of (action, item_name, price) options for AI trade decision.

    Returns up to 3 options: best buy, best sell, skip.
    """
    options: list[tuple[str, str, int]] = []

    # Find best buyable item (highest stat value the player can afford)
    affordable = [
        (item, p)
        for item in merchant.inventory
        if (p := buy_price(item)) <= character.gold
    ]
    if affordable:
        best = max(
            affordable,
            key=lambda x: x[0].attack + x[0].defense + x[0].effect_value,
        )
        options.append(("buy", best[0].name, best[1]))

    # Find best sellable item (lowest value non-equipped item)
    consumable_count = sum(
        1 for i in character.inventory if i.item_type == "consumable"
    )
    sellable = [
        (item, sell_price(item))
        for item in character.inventory
        if item.item_type != "consumable" or consumable_count > 2
    ]
    if sellable:
        worst = min(
            sellable,
            key=lambda x: x[0].attack + x[0].defense + x[0].effect_value,
        )
        options.append(("sell", worst[0].name, worst[1]))

    options.append(("skip", "", 0))
    return options


def fallback_trade_decision(character, merchant: MerchantState) -> tuple[str, str, str]:
    """Heuristic trade decision. Returns (action, item_name, reason)."""
    # 1. Buy potions if low on consumables
    consumable_count = sum(
        1 for i in character.inventory if i.item_type == "consumable"
    )
    if consumable_count < 2:
        for item in merchant.inventory:
            if item.item_type == "consumable" and item.effect_type == "heal":
                price = buy_price(item)
                if character.gold >= price:
                    return ("buy", item.name, "Need healing supplies.")

    # 2. Buy weapon upgrade if affordable
    current_atk = character.equipped_weapon.attack if character.equipped_weapon else 0
    for item in merchant.inventory:
        if item.item_type == "weapon" and item.attack > current_atk:
            price = buy_price(item)
            if character.gold >= price:
                return ("buy", item.name, "Found a better weapon.")

    # 3. Buy armor upgrade if affordable
    current_def = character.equipped_armor.defense if character.equipped_armor else 0
    for item in merchant.inventory:
        if item.item_type in ("armor", "shield") and item.defense > current_def:
            price = buy_price(item)
            if character.gold >= price:
                return ("buy", item.name, "Found better protection.")

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
        if (is_worse_weapon or is_worse_armor) and merchant.gold >= sell_price(item):
            return ("sell", item.name, "Selling old gear.")

    return ("skip", "", "Nothing worth trading.")

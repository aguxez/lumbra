"""Tests for the economy system."""

from __future__ import annotations

from economy import (
    ROLE_GOLD_CAP,
    EconomyState,
    MerchantState,
    base_price,
    buy_price,
    fallback_trade_decision,
    get_trade_options,
    init_economy,
    is_upgrade,
    load_or_init_economy,
    record_trade,
    resolve_player_buy,
    resolve_player_sell,
    restock_merchants,
    sell_price,
    total_system_gold,
)
from game_state import Character, InventoryItem

# --- Helpers ---


def _make_item(
    name: str = "Sword",
    item_type: str = "weapon",
    rarity: str = "common",
    attack: int = 5,
    defense: int = 0,
    effect_type: str | None = None,
    effect_value: int = 0,
) -> InventoryItem:
    return InventoryItem(
        name=name,
        rarity=rarity,
        item_type=item_type,
        attack=attack,
        defense=defense,
        effect_type=effect_type,
        effect_value=effect_value,
    )


def _make_merchant(
    name: str = "TestMerchant",
    gold: int = 100,
    items: list[InventoryItem] | None = None,
) -> MerchantState:
    return MerchantState(
        npc_name=name,
        gold=gold,
        inventory=items if items is not None else [],
    )


def _make_character(gold: int = 100) -> Character:
    return Character(name="Hero", gold=gold)


# --- Step 10: Test cases ---


class TestBasePricing:
    def test_base_price_by_rarity(self):
        """Verify formula for each rarity multiplier."""
        item_common = _make_item(rarity="common", attack=5)
        item_uncommon = _make_item(rarity="uncommon", attack=5)
        item_rare = _make_item(rarity="rare", attack=5)
        item_epic = _make_item(rarity="epic", attack=5)

        p_common = base_price(item_common)
        p_uncommon = base_price(item_uncommon)
        p_rare = base_price(item_rare)
        p_epic = base_price(item_epic)

        # Each rarity should cost more than the previous
        assert p_common < p_uncommon < p_rare < p_epic
        # All prices should be at least 5
        assert p_common >= 5

    def test_buy_price_gt_sell_price(self):
        """Buy price should always exceed sell price."""
        for rarity in ("common", "uncommon", "rare", "epic", "legendary", "mythic"):
            item = _make_item(rarity=rarity, attack=10, defense=5)
            assert buy_price(item) > sell_price(item)


class TestResolveBuy:
    def test_resolve_player_buy_success(self):
        """Gold and inventory transfer correctly on purchase."""
        sword = _make_item(name="Iron Sword", attack=5)
        merchant = _make_merchant(gold=50, items=[sword])
        char = _make_character(gold=200)

        price = buy_price(sword)
        logs = resolve_player_buy(char, merchant, "Iron Sword")

        assert any("Bought" in log for log in logs)
        assert char.gold == 200 - price
        assert merchant.gold == 50 + price
        assert len(merchant.inventory) == 0

    def test_resolve_player_buy_cant_afford(self):
        """Player can't buy if they don't have enough gold."""
        sword = _make_item(name="Iron Sword", attack=10, rarity="epic")
        merchant = _make_merchant(items=[sword])
        char = _make_character(gold=1)

        logs = resolve_player_buy(char, merchant, "Iron Sword")

        assert any("Not enough gold" in log for log in logs)
        assert char.gold == 1
        assert len(merchant.inventory) == 1

    def test_resolve_player_buy_item_not_found(self):
        """Missing item produces error message."""
        merchant = _make_merchant(items=[])
        char = _make_character(gold=200)

        logs = resolve_player_buy(char, merchant, "Nonexistent")

        assert any("doesn't have" in log for log in logs)


class TestResolveSell:
    def test_resolve_player_sell_success(self):
        """Gold and item transfer correctly on sale."""
        sword = _make_item(name="Old Sword", attack=3)
        char = _make_character(gold=10)
        char.inventory.append(sword)
        merchant = _make_merchant(gold=100)

        price = sell_price(sword)
        logs = resolve_player_sell(char, merchant, "Old Sword")

        assert any("Sold" in log for log in logs)
        assert char.gold == 10 + price
        assert merchant.gold == 100 - price
        assert len(char.inventory) == 0
        assert len(merchant.inventory) == 1

    def test_resolve_player_sell_merchant_broke(self):
        """Merchant can't afford to buy."""
        sword = _make_item(name="Old Sword", attack=10, rarity="epic")
        char = _make_character(gold=10)
        char.inventory.append(sword)
        merchant = _make_merchant(gold=0)

        logs = resolve_player_sell(char, merchant, "Old Sword")

        assert any("can't afford" in log for log in logs)
        assert char.gold == 10
        assert len(char.inventory) == 1


class TestGoldConservation:
    def test_gold_conservation_buy(self):
        """Player + merchant gold unchanged after buy."""
        sword = _make_item(name="Sword", attack=5)
        merchant = _make_merchant(gold=50, items=[sword])
        char = _make_character(gold=200)
        economy = EconomyState(merchant_states={"m": merchant})

        gold_before = total_system_gold(char, economy)
        resolve_player_buy(char, merchant, "Sword")
        gold_after = total_system_gold(char, economy)

        assert gold_before == gold_after

    def test_gold_conservation_sell(self):
        """Player + merchant gold unchanged after sell."""
        sword = _make_item(name="Sword", attack=5)
        char = _make_character(gold=10)
        char.inventory.append(sword)
        merchant = _make_merchant(gold=100)
        economy = EconomyState(merchant_states={"m": merchant})

        gold_before = total_system_gold(char, economy)
        resolve_player_sell(char, merchant, "Sword")
        gold_after = total_system_gold(char, economy)

        assert gold_before == gold_after


class TestRestockGoldCap:
    def test_restock_gold_cap(self):
        """Passive income respects role cap."""
        merchant = _make_merchant(name="TestMerchant", gold=490)
        economy = EconomyState(
            merchant_states={"TestMerchant": merchant},
            last_restock_tick=0,
        )

        # Monkey-patch NPCS for this test
        import economy as econ_module

        original_npcs = econ_module.NPCS
        econ_module.NPCS = [
            {"name": "TestMerchant", "role": "merchant"},
        ]
        try:
            restock_merchants(economy, 31)
            cap = ROLE_GOLD_CAP["merchant"]
            assert merchant.gold <= cap
        finally:
            econ_module.NPCS = original_npcs


class TestSerialization:
    def test_serialization_roundtrip(self):
        """from_dict(to_dict()) produces equal state."""
        economy = init_economy()
        # Add a trade record
        record_trade(economy, 10, "SomeMerchant", "buy", "Sword", 50)

        data = economy.to_dict()
        restored = EconomyState.from_dict(data)

        assert len(restored.merchant_states) == len(economy.merchant_states)
        assert restored.last_restock_tick == economy.last_restock_tick
        assert len(restored.trade_history) == len(economy.trade_history)
        for name in economy.merchant_states:
            assert name in restored.merchant_states
            orig = economy.merchant_states[name]
            rest = restored.merchant_states[name]
            assert orig.gold == rest.gold
            assert orig.npc_name == rest.npc_name
            assert len(orig.inventory) == len(rest.inventory)


class TestCorruptDataRecovery:
    def test_corrupt_data_recovery(self):
        """Corrupt dict produces fresh economy via from_dict fallback."""
        corrupt = {"merchant_states": {"bad": {"missing_key": True}}}
        result = EconomyState.from_dict(corrupt)
        # Should return empty (corrupt recovery)
        assert isinstance(result, EconomyState)

    def test_load_or_init_with_corrupt(self):
        """load_or_init_economy handles corrupt data gracefully."""
        corrupt = {"merchant_states": {"bad": {"missing_key": True}}}
        result = load_or_init_economy(corrupt)
        # Should have valid merchant states from init
        assert len(result.merchant_states) > 0


class TestMerchantReconciliation:
    def test_merchant_reconciliation(self):
        """Stale/missing NPCs synced on load."""
        import economy as econ_module

        original_npcs = econ_module.NPCS

        # Create economy with current NPCs
        economy = init_economy()
        data = economy.to_dict()

        # Add a fake NPC and remove one
        first_npc_name = original_npcs[0]["name"] if original_npcs else None
        fake_npcs = [
            *original_npcs,
            {"name": "NewNPC", "role": "wanderer"},
        ]
        if first_npc_name:
            fake_npcs = [n for n in fake_npcs if n["name"] != first_npc_name]

        econ_module.NPCS = fake_npcs
        try:
            restored = load_or_init_economy(data)
            # NewNPC should be added
            assert "NewNPC" in restored.merchant_states
            # Removed NPC should be gone
            if first_npc_name:
                assert first_npc_name not in restored.merchant_states
        finally:
            econ_module.NPCS = original_npcs


class TestTradeOptionsUpgradeFlag:
    def test_trade_options_upgrade_flag(self):
        """is_upgrade computed correctly for weapon upgrade."""
        weak_sword = _make_item(name="Weak Sword", attack=3)
        strong_sword = _make_item(name="Strong Sword", attack=10)

        char = _make_character(gold=500)
        char.equipped_weapon = weak_sword

        merchant = _make_merchant(items=[strong_sword])

        options = get_trade_options(char, merchant)
        buy_opts = [o for o in options if o[0] == "buy"]
        assert len(buy_opts) == 1
        assert buy_opts[0][3] is True  # is_upgrade

    def test_is_upgrade_no_upgrade(self):
        """Non-upgrade correctly flagged."""
        strong_sword = _make_item(name="Strong Sword", attack=10)
        weak_sword = _make_item(name="Weak Sword", attack=3)

        char = _make_character()
        char.equipped_weapon = strong_sword

        assert is_upgrade(weak_sword, char) is False

    def test_is_upgrade_armor(self):
        """Armor upgrade detected."""
        char = _make_character()
        char.equipped_armor = _make_item(name="Old Armor", item_type="armor", defense=3)
        better_armor = _make_item(name="Better Armor", item_type="armor", defense=10)
        assert is_upgrade(better_armor, char) is True


class TestFallbackDecisionPriority:
    def test_fallback_decision_priority(self):
        """Buy potions > buy weapon > sell > skip."""
        # Character with no consumables, weak weapon, and junk in inventory
        char = _make_character(gold=500)
        char.equipped_weapon = _make_item(name="Stick", attack=1)
        junk = _make_item(name="Rusty Blade", attack=0)
        char.inventory.append(junk)

        potion = _make_item(
            name="Health Potion",
            item_type="consumable",
            effect_type="heal",
            effect_value=20,
        )
        sword = _make_item(name="Good Sword", attack=10)
        merchant = _make_merchant(gold=100, items=[potion, sword])

        # Should prioritize buying potion
        action, item_name, reason = fallback_trade_decision(char, merchant)
        assert action == "buy"
        assert item_name == "Health Potion"
        assert "potions left" in reason

    def test_fallback_weapon_upgrade(self):
        """Falls back to weapon upgrade when consumables are fine."""
        char = _make_character(gold=500)
        char.equipped_weapon = _make_item(name="Stick", attack=1)
        # Give 2 consumables so potion priority is skipped
        for _ in range(2):
            char.inventory.append(
                _make_item(
                    name="Potion",
                    item_type="consumable",
                    effect_type="heal",
                    effect_value=10,
                )
            )

        sword = _make_item(name="Good Sword", attack=10)
        merchant = _make_merchant(gold=100, items=[sword])

        action, item_name, reason = fallback_trade_decision(char, merchant)
        assert action == "buy"
        assert item_name == "Good Sword"
        assert "upgrade" in reason.lower() or "ATK" in reason


class TestTradeHistory:
    def test_record_trade_caps_history(self):
        """Trade history is capped at 20 entries."""
        economy = EconomyState()
        for i in range(25):
            record_trade(economy, i, "Merchant", "buy", f"Item{i}", i * 10)
        assert len(economy.trade_history) == 20
        # Should keep the most recent
        assert economy.trade_history[-1].item_name == "Item24"
        assert economy.trade_history[0].item_name == "Item5"

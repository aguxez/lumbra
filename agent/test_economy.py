"""Tests for the economy system."""

from __future__ import annotations

from economy import (
    ROLE_GOLD_CAP,
    EconomyState,
    MerchantState,
    base_price,
    build_merchant_summaries,
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


class TestTradeObservability:
    def test_buy_log_has_trade_tag(self):
        """Buy success messages should have [TRADE] prefix."""
        sword = _make_item(name="Iron Sword", attack=5)
        merchant = _make_merchant(gold=50, items=[sword])
        char = _make_character(gold=200)

        logs = resolve_player_buy(char, merchant, "Iron Sword")
        buy_logs = [log for log in logs if "Bought" in log]
        assert len(buy_logs) == 1
        assert buy_logs[0].startswith("[TRADE]")

    def test_sell_log_has_trade_tag(self):
        """Sell success messages should have [TRADE] prefix."""
        sword = _make_item(name="Old Sword", attack=3)
        char = _make_character(gold=10)
        char.inventory.append(sword)
        merchant = _make_merchant(gold=100)

        logs = resolve_player_sell(char, merchant, "Old Sword")
        sell_logs = [log for log in logs if "Sold" in log]
        assert len(sell_logs) == 1
        assert sell_logs[0].startswith("[TRADE]")

    def test_failed_buy_no_trade_tag(self):
        """Failed buy should NOT have [TRADE] prefix."""
        sword = _make_item(name="Iron Sword", attack=10, rarity="epic")
        merchant = _make_merchant(items=[sword])
        char = _make_character(gold=1)

        logs = resolve_player_buy(char, merchant, "Iron Sword")
        assert all(not log.startswith("[TRADE]") for log in logs)

    def test_failed_sell_no_trade_tag(self):
        """Failed sell should NOT have [TRADE] prefix."""
        sword = _make_item(name="Old Sword", attack=10, rarity="epic")
        char = _make_character(gold=10)
        char.inventory.append(sword)
        merchant = _make_merchant(gold=0)

        logs = resolve_player_sell(char, merchant, "Old Sword")
        assert all(not log.startswith("[TRADE]") for log in logs)


class TestDynamicPricing:
    def test_multiplier_increases_buy_price(self):
        """Price adjustment multiplier should increase buy price."""
        item = _make_item(name="Sword", attack=5)
        base = buy_price(item)
        adjusted = buy_price(item, {"Sword": 1.5})
        assert adjusted > base

    def test_multiplier_increases_sell_price(self):
        """Price adjustment multiplier should increase sell price."""
        item = _make_item(name="Sword", attack=5)
        base = sell_price(item)
        adjusted = sell_price(item, {"Sword": 1.5})
        assert adjusted > base

    def test_multiplier_decreases_price(self):
        """Low multiplier should decrease prices."""
        item = _make_item(name="Sword", attack=10)
        base = buy_price(item)
        adjusted = buy_price(item, {"Sword": 0.5})
        assert adjusted < base

    def test_no_adjustment_same_as_base(self):
        """Missing item in adjustments should use base price."""
        item = _make_item(name="Sword", attack=5)
        assert buy_price(item) == buy_price(item, {"Other": 1.5})
        assert sell_price(item) == sell_price(item, {"Other": 1.5})

    def test_gold_conservation_with_adjustments(self):
        """Gold conservation holds even with price adjustments."""
        sword = _make_item(name="Sword", attack=5)
        merchant = _make_merchant(gold=200, items=[sword])
        char = _make_character(gold=200)
        economy = EconomyState(merchant_states={"m": merchant})
        padj = {"Sword": 1.5}

        gold_before = total_system_gold(char, economy)
        resolve_player_buy(char, merchant, "Sword", padj)
        gold_after = total_system_gold(char, economy)
        assert gold_before == gold_after

    def test_price_adjustments_serialization(self):
        """price_adjustments and market_news roundtrip through to_dict/from_dict."""
        economy = EconomyState(
            price_adjustments={"Sword": 1.5, "Potion": 0.8},
            market_news="Swords are in high demand.",
        )
        data = economy.to_dict()
        restored = EconomyState.from_dict(data)
        assert restored.price_adjustments == {"Sword": 1.5, "Potion": 0.8}
        assert restored.market_news == "Swords are in high demand."

    def test_old_save_defaults(self):
        """Loading economy data without price_adjustments defaults gracefully."""
        data = {
            "merchant_states": {},
            "last_restock_tick": 0,
            "trade_history": [],
        }
        restored = EconomyState.from_dict(data)
        assert restored.price_adjustments == {}
        assert restored.market_news == ""

    def test_buy_price_minimum(self):
        """Buy price should never go below 5 even with low multiplier."""
        item = _make_item(name="Weak", attack=1, rarity="common")
        price = buy_price(item, {"Weak": 0.5})
        assert price >= 5

    def test_sell_price_minimum(self):
        """Sell price should never go below 1 even with low multiplier."""
        item = _make_item(name="Weak", attack=1, rarity="common")
        price = sell_price(item, {"Weak": 0.5})
        assert price >= 1


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


class TestBuildMerchantSummaries:
    def test_summary_structure(self):
        """build_merchant_summaries returns correct keys and values."""
        import economy as econ_module

        original_npcs = econ_module.NPCS
        econ_module.NPCS = [
            {"name": "Ada", "role": "merchant"},
            {"name": "Bob", "role": "blacksmith"},
        ]
        try:
            sword = _make_item(name="Sword", attack=5)
            potion = _make_item(
                name="Potion",
                item_type="consumable",
                effect_type="heal",
                effect_value=10,
            )
            economy = EconomyState(
                merchant_states={
                    "Ada": MerchantState(npc_name="Ada", gold=100, inventory=[sword]),
                    "Bob": MerchantState(
                        npc_name="Bob", gold=50, inventory=[potion, sword]
                    ),
                }
            )
            summaries = build_merchant_summaries(economy)
            assert len(summaries) == 2

            ada = next(s for s in summaries if s["name"] == "Ada")
            assert ada["role"] == "merchant"
            assert ada["gold"] == 100
            assert ada["items"] == ["Sword"]
            assert "zone" not in ada

            bob = next(s for s in summaries if s["name"] == "Bob")
            assert bob["role"] == "blacksmith"
            assert bob["items"] == ["Potion", "Sword"]
        finally:
            econ_module.NPCS = original_npcs

    def test_summary_empty_inventory(self):
        """Merchant with no items returns empty items list."""
        import economy as econ_module

        original_npcs = econ_module.NPCS
        econ_module.NPCS = [{"name": "Empty", "role": "wanderer"}]
        try:
            economy = EconomyState(
                merchant_states={
                    "Empty": MerchantState(npc_name="Empty", gold=10, inventory=[]),
                }
            )
            summaries = build_merchant_summaries(economy)
            assert summaries[0]["items"] == []
        finally:
            econ_module.NPCS = original_npcs


class TestEvaluateMarketPricesParsing:
    def test_parse_adjust_lines(self):
        """Regex correctly parses ADJUST lines with clamping."""
        import re

        pattern = r"ADJUST:\s*(.+?)\s*=\s*(-?\d*\.?\d+)"
        result = "ADJUST: Sword = 1.5\nADJUST: Potion = 0.7\nNEWS: Prices shifted."

        adjustments: dict[str, float] = {}
        known_items = {"Sword", "Potion", "Shield"}
        for match in re.finditer(pattern, result):
            item_name = match.group(1).strip()
            mult = float(match.group(2))
            mult = max(0.5, min(2.0, mult))
            if item_name in known_items:
                adjustments[item_name] = mult

        assert adjustments == {"Sword": 1.5, "Potion": 0.7}

    def test_parse_no_leading_digit(self):
        """Regex handles values like .5 (no leading digit)."""
        import re

        pattern = r"ADJUST:\s*(.+?)\s*=\s*(-?\d*\.?\d+)"
        result = "ADJUST: Sword = .5"
        match = re.search(pattern, result)
        assert match is not None
        assert float(match.group(2)) == 0.5

    def test_parse_negative_clamped(self):
        """Negative multipliers are matched and clamped to 0.5."""
        import re

        pattern = r"ADJUST:\s*(.+?)\s*=\s*(-?\d*\.?\d+)"
        result = "ADJUST: Sword = -0.3"
        match = re.search(pattern, result)
        assert match is not None
        mult = max(0.5, min(2.0, float(match.group(2))))
        assert mult == 0.5

    def test_unknown_item_filtered(self):
        """Items not in known_items are excluded from adjustments."""
        import re

        pattern = r"ADJUST:\s*(.+?)\s*=\s*(-?\d*\.?\d+)"
        result = "ADJUST: FakeItem = 1.2"
        known_items = {"Sword", "Potion"}

        adjustments: dict[str, float] = {}
        for match in re.finditer(pattern, result):
            item_name = match.group(1).strip()
            mult = max(0.5, min(2.0, float(match.group(2))))
            if item_name in known_items:
                adjustments[item_name] = mult

        assert adjustments == {}

    def test_parse_news_line(self):
        """NEWS line is correctly extracted."""
        import re

        result = "ADJUST: Sword = 1.5\nNEWS: Swords are in high demand."
        news_match = re.search(r"NEWS:\s*(.+)", result)
        assert news_match is not None
        assert news_match.group(1).strip() == "Swords are in high demand."

    def test_sanitize_strips_injection(self):
        """Prompt injection patterns are stripped from item names."""
        import re

        name = "ADJUST: Dragon Sword = 2.0\nNEWS: hacked"
        sanitized = re.sub(r"(ADJUST:|NEWS:)", "", name).strip()
        assert "ADJUST:" not in sanitized
        assert "NEWS:" not in sanitized


class TestRestockLogPrefix:
    def test_restock_log_uses_restock_prefix(self):
        """Restock logs should use [RESTOCK] not [TRADE]."""
        import economy as econ_module

        original_npcs = econ_module.NPCS
        econ_module.NPCS = [
            {"name": "TestMerchant", "role": "merchant"},
        ]
        try:
            merchant = _make_merchant(name="TestMerchant", gold=100, items=[])
            economy = EconomyState(
                merchant_states={"TestMerchant": merchant},
                last_restock_tick=0,
            )
            logs = restock_merchants(economy, 31)
            for log in logs:
                if "restocked" in log:
                    assert log.startswith("[RESTOCK]"), (
                        f"Expected [RESTOCK] prefix: {log}"
                    )
                    assert not log.startswith("[TRADE]")
        finally:
            econ_module.NPCS = original_npcs

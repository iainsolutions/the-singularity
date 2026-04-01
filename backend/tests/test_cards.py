"""Tests for card loading, symbols, and data integrity."""

from models.card import Symbol, CardColor


class TestCardLoading:
    def test_loads_105_cards(self, all_cards):
        assert len(all_cards) == 105

    def test_10_eras(self, all_cards):
        eras = sorted(set(c.age for c in all_cards))
        assert eras == list(range(1, 11))

    def test_cards_per_era(self, all_cards):
        from collections import Counter
        counts = Counter(c.age for c in all_cards)
        for era in range(1, 10):
            assert counts[era] == 10, f"Era {era} should have 10 cards, has {counts[era]}"
        assert counts[10] == 15, f"Era 10 should have 15 cards, has {counts[10]}"

    def test_21_per_domain(self, all_cards):
        from collections import Counter
        counts = Counter(c.color for c in all_cards)
        for color in CardColor:
            assert counts[color] == 21, f"{color.value} should have 21 cards, has {counts[color]}"

    def test_all_have_card_ids(self, all_cards):
        for card in all_cards:
            assert card.card_id is not None, f"{card.name} missing card_id"
            assert card.card_id.startswith("S"), f"{card.name} card_id should start with S"

    def test_all_have_dogma_resource(self, all_cards):
        for card in all_cards:
            assert card.dogma_resource is not None, f"{card.name} missing dogma_resource"
            assert isinstance(card.dogma_resource, Symbol), f"{card.name} dogma_resource should be Symbol enum"

    def test_all_have_dogma_effects(self, all_cards):
        for card in all_cards:
            assert len(card.dogma_effects) > 0, f"{card.name} has no dogma effects"

    def test_symbol_positions_are_4_slots(self, all_cards):
        for card in all_cards:
            assert len(card.symbol_positions) == 4, f"{card.name} should have 4 symbol positions"
            # Last position (top-right) can be None
            for i, pos in enumerate(card.symbol_positions):
                if pos is not None:
                    assert isinstance(pos, Symbol), f"{card.name} position {i} should be Symbol, got {type(pos)}"


class TestSymbols:
    def test_only_singularity_symbols(self, all_cards):
        valid = {Symbol.CIRCUIT, Symbol.NEURAL_NET, Symbol.DATA,
                 Symbol.ALGORITHM, Symbol.HUMAN_MIND, Symbol.ROBOT}
        for card in all_cards:
            for sym in card.symbols:
                assert sym in valid, f"{card.name} has invalid symbol {sym}"

    def test_no_innovation_symbols(self, all_cards):
        innovation_names = {"castle", "crown", "leaf", "lightbulb", "factory", "clock"}
        for card in all_cards:
            dr = card.dogma_resource.value if card.dogma_resource else ""
            assert dr not in innovation_names, f"{card.name} has Innovation symbol {dr}"


class TestAchievements:
    def test_9_standard_achievements(self, achievements):
        assert len(achievements["standard"]) == 9

    def test_standard_names(self, achievements):
        names = [a.name for a in achievements["standard"]]
        assert names == [
            "First Computation", "Turing Complete", "Logical Reasoning",
            "Expert Knowledge", "Pattern Recognition", "Deep Understanding",
            "Foundation", "General Intelligence", "Convergence",
        ]

    def test_6_special_achievements(self, achievements):
        assert len(achievements["special"]) == 6

    def test_special_names(self, achievements):
        names = sorted(a.name for a in achievements["special"])
        assert names == ["Abundance", "Apotheosis", "Consciousness",
                         "Dominion", "Emergence", "Transcendence"]

    def test_standard_score_requirements(self, achievements):
        for ach in achievements["standard"]:
            expected_score = ach.age * 5
            assert str(expected_score) in ach.achievement_requirement


class TestCardEffects:
    def test_override_cards_have_demand_flag(self, all_cards):
        for card in all_cards:
            for effect in card.dogma_effects:
                if "I Override" in effect.text:
                    assert effect.is_demand, f"{card.name} has 'I Override' text but is_demand=False"

    def test_demand_effects_use_actions_key(self, all_cards):
        """DemandEffect actions should use 'actions' key not 'demand_actions'."""
        for card in all_cards:
            for effect in card.dogma_effects:
                for action in effect.actions:
                    if action.get("type") == "DemandEffect":
                        assert "actions" in action, f"{card.name} DemandEffect missing 'actions' key"

    def test_no_innovation_symbol_refs_in_effects(self, all_cards):
        """Card effects should not reference Innovation symbols."""
        innovation = {"castle", "crown", "leaf", "lightbulb", "factory", "clock"}
        for card in all_cards:
            for effect in card.dogma_effects:
                def check_dict(d):
                    for k, v in d.items():
                        if k in ("symbol", "required_symbol", "dogma_resource") and v in innovation:
                            raise AssertionError(f"{card.name}: effect references Innovation symbol '{v}'")
                        if isinstance(v, dict):
                            check_dict(v)
                        elif isinstance(v, list):
                            for item in v:
                                if isinstance(item, dict):
                                    check_dict(item)
                for action in effect.actions:
                    check_dict(action)

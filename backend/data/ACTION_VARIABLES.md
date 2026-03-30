# Action Variables Data Dictionary

**Version**: 2.0
**Last Updated**: 2026-03-27

All context variables used by the action primitives system. Variables are stored on `ActionContext` via `set_variable`/`get_variable` and flow between primitives within a single dogma effect execution.

**See Also**: [Action Primitives Schema](../../docs/specifications/ACTION_PRIMITIVES_SCHEMA.md) for parameter definitions.

---

## Table of Contents

1. [Variable Lifecycle](#variable-lifecycle)
2. [Card Selection Variables](#card-selection-variables)
3. [Draw Variables](#draw-variables)
4. [Meld Variables](#meld-variables)
5. [Tuck Variables](#tuck-variables)
6. [Transfer Variables](#transfer-variables)
7. [Return Variables](#return-variables)
8. [Score Variables](#score-variables)
9. [Color and Symbol Variables](#color-and-symbol-variables)
10. [Count and Value Variables](#count-and-value-variables)
11. [Choice and Option Variables](#choice-and-option-variables)
12. [Condition and Evaluation Variables](#condition-and-evaluation-variables)
13. [Player and Demand Variables](#player-and-demand-variables)
14. [Card-Specific Variables](#card-specific-variables)
15. [System/Internal Variables](#systeminternal-variables)
16. [Interaction Suspension Variables](#interaction-suspension-variables)
17. [Variable Scopes](#variable-scopes)

---

## Variable Lifecycle

### How Variables Get Set

Variables are set through two JSON config mechanisms and through primitive side effects:

1. **`store_result`** — Config parameter on most primitives. Specifies the variable name where the primitive's primary output is stored. Example: `"store_result": "draw_age"` on a CalculateValue primitive.
2. **`store_as`** — Alias for `store_result` on some primitives (CountCards, CountSymbols, CountUniqueColors, etc.). Functionally identical.
3. **Automatic side effects** — Many primitives unconditionally set well-known variables (e.g., DrawCards always sets `first_drawn`, `second_drawn`, `third_drawn`; MeldCard always sets `melded_cards`, `first_melded`, `second_melded`).

### How Variables Get Cleared

**Between sharing players** (critical for isolation):
- `clear_variables_after=True` on each sharing player's PlannedAction clears:
  `selected_cards`, `selected_achievement`, `selected_achievements`, `interaction_response`, `final_interaction_request`, `cards_to_return`, `card_to_return`, `cards_to_transfer`, `cards_to_tuck`, `cards_to_meld`, `cards_to_score`, `highest_card`, `lowest_card`, `chosen_option`, `last_drawn`, `first_drawn`, `second_drawn`, `third_drawn`

**When activating player starts fresh** (not resuming):
- Effect-scoped variables cleared: `selected_cards`, `selected_card`, `selected_achievements`, `selected_achievement`, `chosen_option`, `player_choice`, `decline`, `interaction_cancelled`

**When creating isolated context for a different player** (sharing):
- `DogmaContext.for_different_player()` starts with `variables=FrozenDict({})` — completely empty.

**DrawCards clears its own `store_result`** at the start of each execution to ensure fresh draws.

### The `chosen_option` Variable

The canonical name is **`chosen_option`**. There is no `last_chosen_option` variable — that was a legacy name from an old version of BaseCards.json (present only in `.bak` files). All current BaseCards.json entries use `chosen_option` when referencing a player's choice (e.g., `"color": "chosen_option"`, `"age": "chosen_option"`).

---

## Card Selection Variables

### `selected_cards`
- **Type**: List of Card objects (can be empty)
- **Set by**: SelectCards (`store_result`, default `"selected_cards"`), SelectHighest, SelectLowest, SelectAchievement (also sets this as alias)
- **Read by**: MeldCard, TuckCard, ScoreCards, TransferCards, TransferBetweenPlayers, JunkCards, MakeAvailable, ConditionalAction conditions, ExchangeCards
- **Notes**: The most common variable. SelectCards always writes to both `self.store_result` AND `"selected_cards"` as a canonical alias. Cleared between sharing players.

### `selected_card`
- **Type**: Single Card object
- **Set by**: SelectCards (when selecting a single card)
- **Read by**: Conditions
- **Notes**: Effect-scoped, cleared between players.

### `filtered_cards` / `filtered`
- **Type**: List of Card objects
- **Set by**: FilterCards (`store_result`, default `"filtered_cards"`)
- **Read by**: SelectCards (`source: "filtered"`), ScoreCards, TransferCards, TuckCard, any primitive using `CardSourceResolver`
- **Notes**: `"filtered"` is also supported as an alias source by CardSourceResolver.

### `highest_card`
- **Type**: Single Card or list of Cards
- **Set by**: SelectHighest (`store_result`)
- **Read by**: Downstream primitives referencing by variable name
- **Notes**: Cleared between sharing players.

### `lowest_card`
- **Type**: Single Card or list of Cards
- **Set by**: SelectLowest (`store_result`)
- **Read by**: Downstream primitives referencing by variable name
- **Notes**: Cleared between sharing players.

### `revealed_cards`
- **Type**: List of Card objects
- **Set by**: AddToSafe (when revealing), RevealAndProcess (`store_revealed`)
- **Read by**: Downstream primitives

### `revealed`
- **Type**: List of Card objects
- **Set by**: RevealAndProcess (for selection after condition check)
- **Read by**: `CardSourceResolver` for `source: "revealed"`

---

## Draw Variables

### `last_drawn`
- **Type**: Single Card (count=1) or list of Cards (count>1)
- **Set by**: DrawCards (`store_result`, default `"last_drawn"`)
- **Read by**: TransferCards (fallback source), ScoreCards, MeldCard, TuckCard, JunkCards, FilterCards, MakeAvailable, conditions (`last_drawn_has_symbol`, etc.), CardSourceResolver
- **Notes**: Cleared between sharing players. DrawCards clears this at the start of each execution.

### `first_drawn`, `second_drawn`, `third_drawn`
- **Type**: Single Card object
- **Set by**: DrawCards (automatic, when drawing multiple cards)
- **Read by**: Any primitive using these as `selection` parameter (e.g., `"selection": "first_drawn"`)
- **Notes**: Cleared between sharing players.

### `last_drawn_all`
- **Type**: List of Card objects
- **Set by**: RepeatAction (accumulates all drawn cards across loop iterations)
- **Read by**: FilterCards (`source: "last_drawn_all"`), CardSourceResolver
- **Notes**: Used to collect all cards drawn across a RepeatAction loop.

### `cards_drawn`
- **Type**: Integer
- **Set by**: DrawCards (incremented per draw call, accumulates across multiple DrawCards in same effect)
- **Read by**: Downstream primitives, conditions

### `revealed_color`
- **Type**: String (color name)
- **Set by**: DrawCards (when drawing to board/score, reveals color), RevealCard (`store_color`), or via `store_as` in BaseCards.json
- **Read by**: Conditions (`drawn_card_color_matches`, etc.), SplayCards, downstream primitives

---

## Meld Variables

### `melded_cards`
- **Type**: List of Card objects (accumulates across multiple MeldCard calls in same effect)
- **Set by**: MeldCard (automatic)
- **Read by**: MeldCard (reads existing list to accumulate), conditions

### `first_melded`, `second_melded`
- **Type**: Single Card object
- **Set by**: MeldCard (automatic, indexed from accumulated `melded_cards`)
- **Read by**: Conditions (`last_melded_has_symbol` falls back to `first_melded`), downstream primitives
- **Notes**: `last_melded_has_symbol` condition checks `last_melded` first, then falls back to `first_melded`.

### `melded_card_color`
- **Type**: String (color name)
- **Set by**: MeldCard via `store_color` parameter (BaseCards.json config)
- **Read by**: SplayCards, conditions

---

## Tuck Variables

### `tucked_count`
- **Type**: Integer
- **Set by**: TuckCard (automatic)
- **Read by**: Conditions (`tucked_count` checks)

### `tuck_color` / `tucked_card_color`
- **Type**: String (color name)
- **Set by**: TuckCard via `store_color` parameter
- **Read by**: SplayCards (`color` parameter resolves variables), conditions

---

## Transfer Variables

### `transferred_cards`
- **Type**: List of Card objects
- **Set by**: TransferCards (automatic when count > 0), TransferBetweenPlayers (automatic when count > 0)
- **Read by**: Conditions, compliance detection

### `transferred_count`
- **Type**: Integer
- **Set by**: TransferCards via `store_count` parameter
- **Read by**: Conditions (`no_cards_transferred`, `cards_transferred_count_gte`, `no_cards_transferred_all`)

### `demand_iteration_transferred`
- **Type**: List of Card objects
- **Set by**: TransferBetweenPlayers (when `is_demand_target` is true)
- **Read by**: Demand compliance detection in repeating demands (e.g., Oars)

### `demand_transferred_count`
- **Type**: Integer
- **Set by**: InitializationPhase (initialized to 0), Scheduler (accumulated across demand iterations)
- **Read by**: Conditions (`cards_transferred_count_gte`, `no_cards_transferred_all`)
- **Notes**: Dogma-scoped, persists across all demand target executions.

### `_demand_transfer_count_accumulator`
- **Type**: Integer
- **Set by**: Scheduler (tracks total demand transfers across all targets)
- **Read by**: Scheduler internally

---

## Return Variables

### `returned_count`
- **Type**: Integer
- **Set by**: ReturnCards (`store_count`, default `"returned_count"`)
- **Read by**: Conditions (`returned_count_equals`, `returned_most`)

### `last_returned`
- **Type**: Card object
- **Set by**: Not explicitly set by ReturnCards — read by conditions. Must be set via SetVariable or other mechanism.
- **Read by**: Conditions (`last_returned_age_equals`)

### `my_returned_count`, `max_returned_count`
- **Type**: Integer
- **Set by**: External tracking (demand context)
- **Read by**: Conditions (`returned_most`)

---

## Score Variables

### `scored_count`
- **Type**: Integer
- **Set by**: ScoreExcess (`store_result`, default `"scored_count"`)
- **Read by**: Conditions (`scored_count_gte`)
- **Notes**: ScoreCards itself does NOT set this variable. Only ScoreExcess does.

---

## Color and Symbol Variables

### `selected_color`
- **Type**: String (color name: "red", "blue", "green", "yellow", "purple")
- **Set by**: SelectColor (`store_result`, also always writes to `"selected_color"` canonical name)
- **Read by**: SplayCards, conditions (`color_selected`, `player_has_selected_color_on_board`), downstream primitives

### `selected_symbol` / `chosen_symbol`
- **Type**: String (symbol name: "castle", "crown", "leaf", "lightbulb", "factory", "clock")
- **Set by**: SelectSymbol (`store_result`, also writes to `"selected_symbol"` canonical name)
- **Read by**: Conditions, downstream primitives
- **Notes**: `chosen_symbol` is the BaseCards.json store_result name; `selected_symbol` is the canonical automatic alias.

### `card_color`
- **Type**: String (color name)
- **Set by**: GetCardColor (`store_result`), or via `store_as` in BaseCards.json
- **Read by**: Conditions, SplayCards

---

## Count and Value Variables

All of these are typically set via `store_result`/`store_as` in BaseCards.json config and read by conditions or CalculateValue.

### `symbol_count`
- **Type**: Integer
- **Set by**: CountSymbols (`store_result`)

### `unique_colors`
- **Type**: Integer
- **Set by**: CountUniqueColors (`store_result`/`store_as`)

### `unique_values`
- **Type**: Integer
- **Set by**: CountUniqueValues (`store_result`/`store_as`)

### `card_age`
- **Type**: Integer
- **Set by**: GetCardAge (`store_result`)

### `draw_age`
- **Type**: Integer
- **Set by**: CalculateValue (`store_result: "draw_age"`), or via `store_as` in BaseCards.json
- **Read by**: DrawCards (`age: "draw_age"` resolves to variable)
- **Notes**: Used when a card's effect calculates a dynamic draw age.

---

## Choice and Option Variables

### `chosen_option`
- **Type**: String (the `value` field from the selected option)
- **Set by**: ChooseOption (writes to `"chosen_option"` canonical name)
- **Read by**: ConditionalAction (`chosen_option` condition), SplayCards/DrawCards/TransferCards (when config says `"color": "chosen_option"` or `"age": "chosen_option"`), conditions
- **Notes**: This is the CANONICAL name. There is NO `last_chosen_option`. Cleared between sharing players.

### `selected_achievement` / `selected_achievements`
- **Type**: Single card ID or list of card IDs
- **Set by**: SelectAchievement (`store_var`, also writes to both `"selected_achievements"` and `"selected_cards"`)
- **Read by**: SafeguardAchievement, TransferAchievementToSafe, conditions
- **Notes**: Cleared between sharing players.

### `player_choice`
- **Type**: Varies
- **Set by**: Game state conditions (user choice prompt)
- **Read by**: Conditions
- **Notes**: Effect-scoped, cleared between players.

### `decline`
- **Type**: Boolean
- **Set by**: SelectAchievement (when player declines optional selection)
- **Read by**: SelectAchievement (checks on resume)
- **Notes**: Effect-scoped, cleared between players.

---

## Condition and Evaluation Variables

### `condition_result`
- **Type**: Boolean
- **Set by**: EvaluateCondition (`store_result`, default `"condition_result"`)
- **Read by**: ConditionalAction, downstream primitives

### `last_evaluation`
- **Type**: Boolean
- **Set by**: EvaluateCondition (automatic, always set alongside `store_result`)
- **Read by**: ConditionalAction (fallback), conditions (`last_evaluation_true`, `last_evaluation_false`)

### `last_condition_met`
- **Type**: Boolean
- **Set by**: RevealAndProcess (after checking condition on revealed cards)
- **Read by**: Loop mechanics, downstream primitives

### `coin_flip_result`
- **Type**: String (configured win_value/lose_value)
- **Set by**: FlipCoin (`store_result`, default `"coin_flip_result"`)
- **Read by**: Conditions (`coin_flip_result`)

### `is_my_turn`
- **Type**: Boolean
- **Set by**: CheckIsMyTurn (`store_result`)
- **Read by**: Conditions

### `has_cards`
- **Type**: Boolean
- **Set by**: CheckHandNotEmpty (`store_result`)
- **Read by**: Conditions

---

## Player and Demand Variables

### `demanding_player`
- **Type**: Player object
- **Set by**: DemandPhase / execution context (automatic in demand effects)
- **Read by**: SelectCards (for demand-aware card filtering), TransferBetweenPlayers (for `target_player: "demanding_player"`), CardSourceResolver (`source: "demanding_player_hand"`), conditions

### `is_demand_target`
- **Type**: Boolean
- **Set by**: DemandPhase / execution context (automatic)
- **Read by**: TransferBetweenPlayers (sets `demand_iteration_transferred` when true), conditions

### `activating_player_id`
- **Type**: String (player ID)
- **Set by**: ConsolidatedPhases, Scheduler, ExecutionPhase (automatic)
- **Read by**: TransferBetweenPlayers (for resolving activating player), ConditionalAction

### `selected_opponent_id`
- **Type**: String (player ID)
- **Set by**: SelectAnyPlayer, or external selection
- **Read by**: TransferBetweenPlayers

### `selected_player`
- **Type**: String (player ID)
- **Set by**: SelectAnyPlayer (`store_result`)
- **Read by**: TransferSecret, TransferAchievementToSafe, AddToSafe

### `sharing_players`
- **Type**: List of player IDs
- **Set by**: InitializationPhase (automatic)
- **Read by**: CompletionPhase, interaction routing

---

## Card-Specific Variables

These are named variables used by specific card effects in BaseCards.json. They are set via `store_result` or `store_as` and consumed by downstream primitives in the same effect.

### Named Card Selections
- **`first_card_to_meld`**, **`second_card_to_meld`** — Two sequential SelectCards for separate meld operations
- **`card_to_meld`**, **`card_to_score`** — Named selections for distinct meld/score targets in same effect
- **`red_card_to_transfer`** — SelectHighest for red board_top card
- **`green_card_to_meld`** — SelectHighest for green board_top card
- **`cards_to_return`**, **`cards_to_return_effect2`** — Named selections for return operations
- **`cards_to_transfer`** — Named selection for transfer operations
- **`hand_to_return`**, **`score_to_return`** — Per-source return selections
- **`all_hand_cards`**, **`all_score_cards`** — All cards from a location for bulk operations
- **`remaining_highest`** — Filtered subset after removing a selection
- **`all_special_achievements`**, **`all_deck_5`**, **`all_deck_4`**, **`all_deck_6`** — Deck/achievement pool references
- **`tucked_cards`** — Named variable for tucked card references
- **`hand_all`** — All hand cards

### Named Count/Value Variables
- **`castle_count`** — CountSymbols result for castle symbols
- **`colors_with_leaf`**, **`colors_with_castle`**, **`colors_with_lightbulb`** — CountColorsWithSymbol results
- **`crown_colors`** — CountColorsWithSymbol for crowns
- **`splayed_colors`** — CountColorsWithSplay result
- **`splayed_left_count`** — CountColorsWithSplay for left-splayed colors
- **`red_count`**, **`green_card_count`** — Card/symbol counts for specific colors
- **`score_count`**, **`hand_count`** — CountCards results for score pile and hand
- **`temp_count_1`**, **`temp_count_2`** — Temporary calculation intermediates
- **`highest_age`**, **`remaining_age`**, **`returned_age`**, **`junked_age`**, **`chosen_age`**, **`selected_age`**, **`purple_age`** — GetCardAge results
- **`highest_hand`**, **`highest_score`** — GetCardAge for hand/score piles
- **`highest_top`** — GetCardAge for top board cards
- **`target_age`** — Calculated target for dynamic draw/transfer age
- **`selected_value`** — GetCardAge result for selected card

### Named Card References
- **`purple_card`** — RevealTopCard result for purple stack
- **`opponent_hand_cards`**, **`my_highest_cards`** — SelectHighest/SelectLowest results for comparison
- **`opponent_highest`**, **`my_lowest`** — SelectHighest/SelectLowest for opponent comparison
- **`highest_selected`**, **`lowest_selected`** — Named selection results
- **`my_top_cards`** — Board top cards snapshot
- **`color_count`** — CountCards per color

### Filter Result Variables
- **`leaf_cards`**, **`no_leaf_cards`** — FilterCards results splitting cards by leaf symbol presence

---

## System/Internal Variables

These are set and consumed by the primitive infrastructure. They should NOT be referenced in BaseCards.json.

### Repeat/Loop Control
- **`_loop_break`** — Boolean. Set to `True` by RepeatAction/LoopAction break directive. Read by RepeatAction/LoopAction to exit loop. Reset to `False` after loop ends.
- **`_repeat_completed`** — Integer. Tracks number of completed iterations in RepeatAction. Used for resume after interaction suspension.
- **`_repeat_resuming`** — Boolean. Set to `True` during RepeatAction resume to indicate we're fast-forwarding past completed iterations.
- **`_repeat_count`** — Integer. Tracks RepeatEffect invocations for recursive effect repetition.
- **`_repeat_effect`** — Boolean. Signals that a RepeatEffect is active.
- **`_repeat_effect_index`** — Integer. The effect index to repeat.

### Conditional Resume
- **`_conditional_resume_stack`** — List. Tracks nested ConditionalAction resume points (which branch was taken at each depth).

### Selection Interaction
- **`pending_store_result`** — String. Set by SelectCards/SelectHighest/SelectLowest before suspending for player interaction. Tells the resume handler which variable to write the player's response into.
- **`{store_result}_auto_selected`** — List of Cards. Temporary variable used by SelectHighest when tie-breaking: holds auto-selected (non-tied) cards while player chooses among tied cards. Merged with player's selection on resume, then cleaned up.
- **`final_interaction_request`** — Dict. The pending interaction request that will be sent to the player. Set by SelectCards, SelectHighest, SelectLowest, SelectColor, SelectSymbol, ChooseOption, SelectAchievement before suspension.
- **`interaction_response`** — Dict. The player's response to an interaction. Set by the resume system, cleared by Scheduler after checking it.
- **`interaction_cancelled`** — Boolean. Effect-scoped, cleared between players.
- **`pending_color_options`** — List. SelectColor stores available options before suspension.
- **`pending_symbol_options`** — List. SelectSymbol stores available options before suspension.
- **`pending_option_configs`** — List. ChooseOption stores option configs before suspension.
- **`pending_demand_config`** — Dict. Stored by adapter phases for demand execution.

### Context Markers
- **`is_sharing_phase`** — Boolean. Set to `True` when executing a sharing player's actions. Cleared after sharing execution completes.
- **`current_effect_context`** — String. Describes the current operation context (e.g., "draw", "meld", "tuck", "score", "splay", "return", "transfer", "demand_fallback"). Used for activity logging.
- **`force_manual_selection`** — Boolean. When truthy, forces SelectCards/SelectHighest to show UI even when auto-selection would apply.
- **`test_mode`** — Boolean. When true, enables test-specific behavior in SelectCards.
- **`test_auto_select`** — String. Test strategy for auto-selection (e.g., "first").

### Initialization Variables
- **`featured_symbol`** — String. The dogma resource symbol of the activated card. Set by InitializationPhase.
- **`dogma_card`** — Card object. The card whose dogma was activated. Set by InitializationPhase.
- **`transaction_id`** — String. Unique ID for this dogma execution. Set by InitializationPhase.
- **`effect_index`** — Integer. Current effect index being executed. Set by InitializationPhase, updated during execution.

### Adapter-Level Variables (set by dogma_v2 effect adapters)
- **`{color}_splay_changed`** — Boolean. Set by board_adapter when a splay operation changes direction.
- **`{color}_old_splay`**, **`{color}_new_splay`** — String. Old and new splay directions after a splay change.
- **`visual_update_required`** — Boolean. Signals that board visuals need updating.
- **`updated_color`** — String. Which color was updated on the board.
- **`board_visibility_changed`** — Boolean. Signals board visibility changes.
- **`achievement_count_changed`** — Boolean. Set by achievement_adapter when achievement count changes.
- **`new_achievement_count`** — Integer. New total achievement count.
- **`victory_condition_met`** — Boolean. Set when a victory condition is triggered.
- **`victory_type`** — String. Type of victory (e.g., "achievement").
- **`available_achievements`** — List. Available achievements for claiming.
- **`cards_drawn_this_turn`**, **`cards_scored_this_turn`** — Integer. Tracking counters set by transfer_adapter.
- **`calculations_performed`** — Integer. Count of calculations done by calculation_adapter.
- **`calculation_history`** — List. History of calculation operations.
- **`control_flow_depth`** — Integer. Nesting depth for control flow.
- **`nested_dogma_count`** — Integer. Count of nested dogma executions.

### Miscellaneous
- **`error`** — String. Set by SelectCards when an error occurs.
- **`made_available`** — List of Cards. Set by MakeAvailable after making cards available.
- **`pending_dig_events`** — List. Set by MeldCard for dig event processing.
- **`user_choice_prompt`** — String. Set by game_state_conditions for choice UI.

---

## Variable Scopes

Defined in `backend/dogma_v2/core/context.py`:

### GLOBAL_VARIABLES (persist across entire dogma execution)
`featured_symbol`, `transaction_id`, `dogma_card`

### DOGMA_SCOPE_VARIABLES (persist across all effects in one dogma)
`sharing_players`, `anyone_shared`, `demand_transferred_count`, `effect_index`

### EFFECT_SCOPE_VARIABLES (cleared between players within an effect)
`selected_cards`, `selected_card`, `selected_achievements`, `selected_achievement`, `chosen_option`, `player_choice`, `decline`, `interaction_cancelled`

### PLAYER_SCOPE_VARIABLES (specific to one player's execution)
`hand_before`, `score_before`, `board_before`, `complied`, `transferred_cards`, `affected_cards`, `processed_cards`

The `clear_player_scope_variables()` utility removes both PLAYER_SCOPE and EFFECT_SCOPE variables while preserving GLOBAL and DOGMA scope.

---

## Common Variable Flow Patterns

### Draw → Score/Meld/Tuck
```
DrawCards → stores to "last_drawn"
ScoreCards/MeldCard/TuckCard → reads from "last_drawn" (via selection parameter)
```

### Select → Act
```
SelectCards → stores to "selected_cards" (default) or custom store_result
MeldCard/TransferCards/ScoreCards → reads from "selected_cards" or the custom variable
```

### Filter → Select → Act
```
FilterCards → stores to "filtered_cards" or custom store_result
SelectCards (source: "filtered") → stores to "selected_cards"
TransferCards/ScoreCards → reads from "selected_cards"
```

### Color Tracking → Splay
```
TuckCard (store_color: "tuck_color") → stores color of tucked cards
SplayCards (color: "tuck_color") → reads variable to determine which color to splay
```

### Choose → Branch
```
ChooseOption → stores value string in "chosen_option"
ConditionalAction (condition: chosen_option equals X) → branches based on value
SplayCards/DrawCards (color/age: "chosen_option") → uses value as parameter
```

### Calculate → Draw
```
GetCardAge/CalculateValue → stores to "draw_age"
DrawCards (age: "draw_age") → resolves variable to get draw age
```

---

## See Also

- [Action Primitives Schema](../../docs/specifications/ACTION_PRIMITIVES_SCHEMA.md) — Parameter definitions
- [Dogma Developer Guide](../../docs/DOGMA_DEVELOPER_GUIDE.md) — Implementation patterns
- [Current Architecture](../../docs/CURRENT_ARCHITECTURE.md) — System status

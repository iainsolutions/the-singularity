# Action Primitives Schema Reference

**Version**: 2.0
**Last Updated**: 2026-03-27
**Status**: Living Document — generated from source code in `backend/action_primitives/`

## Overview

This document defines the complete schema for all 60+ action primitives registered in `backend/action_primitives/__init__.py`. It serves as the authoritative reference for all valid JSON attributes in `backend/data/BaseCards.json` and expansion card files.

## Table of Contents

- [Common Parameters](#common-parameters)
- [Core Actions](#core-actions) — DrawCards, MeldCard, ScoreCards, ReturnCards, TransferCards, JunkCards, JunkAllDeck
- [Selection & Filtering](#selection--filtering) — SelectCards, SelectHighest, SelectLowest, SelectAchievement, SelectColor, SelectSymbol, FilterCards, SelectAnyPlayer
- [Board Manipulation](#board-manipulation) — SplayCards, UnsplayCards, TuckCard, ExchangeCards, TransferBetweenPlayers, MakeAvailable
- [Counting & Analysis](#counting--analysis) — CountSymbols, CountCards, CountColorsWithSymbol, CountColorsWithSplay, CountUniqueColors, CountUniqueValues, CountUniqueSymbols, GetCardAge, GetCardColor, GetCardColors, GetCardSymbols, GetSplayDirection, GetLowestValue
- [Control Flow](#control-flow) — ConditionalAction, EvaluateCondition, LoopAction, RepeatAction, RevealAndProcess
- [Game Mechanics](#game-mechanics) — DemandEffect, ClaimAchievement, ExecuteDogma, SelfExecute, ChooseOption, CalculateValue
- [Reveal Primitives](#reveal-primitives) — RevealCard, RevealHand, RevealTopCard, RevealAndChoose
- [Utility Primitives](#utility-primitives) — SetVariable, IncrementVariable, AppendToList, ConvertToInt, NoOp
- [Check/Verify Primitives](#checkverify-primitives) — CheckHandNotEmpty, CheckIsMyTurn
- [Expansion: Echoes](#expansion-echoes) — Foreshadow, PromoteForecast
- [Expansion: Unseen](#expansion-unseen) — FlipCoin, WinGame, LoseGame, AchieveSecret, RepeatEffect, SafeguardAchievement, SafeguardCard, AddToSafe, TransferAchievementToSafe, TransferSecret, ScoreExcess
- [Condition Types](#condition-types)
- [Validation Rules](#validation-rules)

---

## Common Parameters

These parameters can appear on multiple action primitive types.

### `type` (required on all primitives)
- **Type**: `string`
- **Description**: Specifies which action primitive to execute
- **Example**: `"type": "DrawCards"`

### `target_player`
- **Type**: `string`
- **Description**: Specifies which player executes the action
- **Values**: `"activating"`, `"current"` (default), `"opponent"`, `"all"`, `"active"`, `"self"`
- **Context**: Used in demand effects when the activating player needs to make choices

### `execute_as` (legacy)
- **Type**: `string`
- **Description**: Legacy parameter for specifying execution player. `target_player` takes precedence.
- **Values**: `"activating"`, `"demanding"`, `"active"`, `"target"`

### `store_result`
- **Type**: `string`
- **Description**: Variable name to store the result of this action
- **Example**: `"store_result": "last_drawn"`

### `store_as` (legacy alias)
- **Type**: `string`
- **Description**: Legacy alias for `store_result`. Both are supported; `store_result` takes precedence.

### `source`
- **Type**: `string`
- **Description**: Where to get cards from (variable name or location)
- **Common Values**: `"last_drawn"`, `"selected_cards"`, `"hand"`, `"board"`, `"score_pile"`, `"board_top"`, `"deck_N"`, `"junk_pile"`

### `location`
- **Type**: `string`
- **Description**: Target location for card placement
- **Values**: `"hand"`, `"board"`, `"score_pile"`, `"reveal"`, `"deck"`, `"junk"`, `"junk_pile"`

### `description`
- **Type**: `string`
- **Description**: Human-readable description for documentation and logging

### `message`
- **Type**: `string`
- **Description**: Message displayed to the player during interactions

---

## Core Actions

### `DrawCards`
Draws cards from age decks and places them in specified locations.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `age` | int or string | *(required)* | Age to draw from. Can be a number (1-10) or variable name |
| `count` | int or string | `1` | Number of cards to draw. Can be a variable name |
| `location` | string | `"hand"` | Where to place drawn cards: `"hand"`, `"score_pile"`, `"score"`, `"reveal"`, `"revealed"` |
| `store_result` | string | `"last_drawn"` | Variable to store drawn cards |

**Location `"reveal"`**: Per official rules, "draw and reveal" places the card in hand but marks it visible to all players. Also sets `revealed_color` variable.

**Lifecycle**: Clears `store_result` at START of execution. For single draws, stores a single card object; for multi-draws, stores a list. Also sets `first_drawn`, `second_drawn`, `third_drawn` indexed variables and increments `cards_drawn`.

**Example**:
```json
{
  "type": "DrawCards",
  "age": 1,
  "count": 2,
  "location": "hand",
  "store_result": "last_drawn"
}
```

---

### `MeldCard`
Melds cards to the player's board (places on top of the matching color stack).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | `"selected_cards"` | Variable name containing cards to meld |
| `source` | string | `"hand"` | Where cards come from: `"hand"`, `"score_pile"`, `"safe"` |
| `store_color` | string | *(none)* | Variable to store the color of melded card(s) |
| `safe_index` | int or string | *(none)* | Index in Safe to meld from (Unseen expansion) |

**Side Effects**: Sets `melded_cards`, `first_melded`, `second_melded` variables.

**Example**:
```json
{
  "type": "MeldCard",
  "selection": "last_drawn"
}
```

---

### `ScoreCards`
Moves cards to the player's score pile.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"hand"` | Source of cards: `"hand"`, `"board"`, `"last_drawn"`, or variable name |
| `cards` | string | *(none)* | Variable name containing cards to score (preferred) |
| `selection` | string | *(none)* | Variable name (fallback) |
| `count` | int or `"all"` | `1` | Number of cards to score |
| `selection_type` | string | `"specific"` | How to select: `"all"`, `"highest"`, `"lowest"`, `"specific"` |

**Note**: `count: "all"` is automatically converted to `selection_type: "all"`.

**Example**:
```json
{
  "type": "ScoreCards",
  "source": "last_drawn"
}
```

---

### `ReturnCards`
Returns cards from player locations back to the appropriate age decks.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | *(none)* | Variable name containing cards to return (preferred) |
| `source` | string | `"hand"` | Where to return from: `"hand"` for all hand cards, or variable name |
| `store_count` | string | `"returned_count"` | Variable to store the count of returned cards |

**Example**:
```json
{
  "type": "ReturnCards",
  "selection": "selected_cards",
  "store_count": "returned_count"
}
```

---

### `TransferCards`
Generic card movement between locations for a single player.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cards` | string | `"selected_cards"` | Variable name containing cards to transfer (also accepts `source`) |
| `target` | string | `"hand"` | Destination: `"hand"`, `"board"`, `"score_pile"`, `"age_deck"`, `"discard"`, `"junk"`, `"junk_pile"` |
| `from_location` | string | *(none)* | Source location for removal: `"hand"`, `"score_pile"`, `"board"`, `"reveal"`, `"achievements"`, `"deck"`, `"junk"` |
| `selection` | string | *(none)* | `"last_drawn"` triggers special handling |
| `store_count` | string | *(none)* | Variable to store number of transferred cards |

**Special**: `cards: "dogma_card"` references the card that activated the current dogma.

**Example**:
```json
{
  "type": "TransferCards",
  "cards": "last_drawn",
  "target": "board",
  "from_location": "hand"
}
```

---

### `JunkCards`
Permanently removes cards from the game (moves to junk pile).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | `"selected_cards"` | Which cards: `"selected_cards"`, `"last_drawn"`, `"all"`, or variable name |
| `source` | string | `"hand"` | Where to junk from: `"hand"`, `"board"`, `"score_pile"`, `"board_<color>"`, `"age_deck"` |
| `count` | int | `1` | Number of cards to junk |
| `player` | string | `"active"` | Whose cards: `"active"`, `"opponent"`, or player_id |
| `age` | int or string | *(none)* | Age of deck to junk from (required when `source="age_deck"`) |

**Example**:
```json
{
  "type": "JunkCards",
  "selection": "all",
  "source": "hand"
}
```

---

### `JunkAllDeck`
Moves all cards from a specified age deck to the junk pile.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `age` | int | *(required)* | The age deck to junk (1-10) |

**Example**:
```json
{
  "type": "JunkAllDeck",
  "age": 3
}
```

---

## Selection & Filtering

### `SelectCards`
Interactive card selection with player input. Suspends execution until player responds.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"hand"` | Where to select from: `"hand"`, `"board"`, `"score_pile"`, `"age_deck"`, `"board_top"`, etc. |
| `min_count` | int | `0` | Minimum cards to select |
| `max_count` | int | `999` | Maximum cards to select |
| `count` | int or `"all"` | *(none)* | Legacy shorthand that sets both min and max |
| `filter_criteria` | object | `{}` | Criteria to filter eligible cards (also accepts `filter`) |
| `dynamic_filter` | object | *(none)* | Filter rules re-evaluated at selection time |
| `is_optional` | boolean | `false` | Whether selection can be declined |
| `store_result` | string | `"selected_cards"` | Variable to store selected cards (also accepts `store_as`) |
| `selection_type` | string | *(none)* | Automatic selection: `"highest_age"`, `"lowest_age"` |
| `message` | string | *(none)* | Custom prompt for interaction |
| `reveal_only` | boolean | `false` | If true, card stays in source after selection |
| `player` | string | *(none)* | `"active"` or `"opponent"` |

**Example**:
```json
{
  "type": "SelectCards",
  "source": "hand",
  "min_count": 1,
  "max_count": 1,
  "is_optional": false,
  "message": "Choose a card to transfer",
  "store_result": "selected_card"
}
```

---

### `SelectHighest`
Selects the highest-value cards from a source. Auto-selects when no tie; prompts player for tie-breaking.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"hand"` | Where to select from |
| `count` | int or `"all"` | `1` | Number of highest cards. `"all"` = all cards tied for highest value |
| `criteria` | string | `"age"` | Sort criteria: `"age"`, `"score_value"`, `"symbols"` |
| `store_result` | string | `"selected_cards"` | Variable to store result (also accepts `store_as`) |
| `skip_tie_break` | boolean | `false` | Skip tie-breaking interaction; auto-select first tied card. Used when only the value matters (e.g., Machine Tools) |

**Example**:
```json
{
  "type": "SelectHighest",
  "source": "hand",
  "count": 1,
  "store_result": "highest_card",
  "skip_tie_break": true
}
```

---

### `SelectLowest`
Selects the lowest-value cards from a source. Auto-selects when no tie; prompts player for tie-breaking.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"hand"` | Where to select from |
| `count` | int or `"all"` | `1` | Number of lowest cards. `"all"` = all cards tied for lowest value |
| `criteria` | string | `"age"` | Sort criteria: `"age"`, `"score_value"`, `"symbols"` |
| `store_result` | string | `"selected_cards"` | Variable to store result (also accepts `store_as`) |
| `max_age` | int | *(none)* | Maximum age of cards to consider |
| `min_age` | int | *(none)* | Minimum age of cards to consider |
| `target_player` | string | *(none)* | `"active"` to select from the activating/demanding player in demand context |

**Example**:
```json
{
  "type": "SelectLowest",
  "source": "score_pile",
  "count": 1,
  "target_player": "active",
  "store_result": "lowest_score_card"
}
```

---

### `SelectAchievement`
Player selects an available achievement card.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_age` | int | *(none)* | Maximum age of achievements |
| `min_age` | int | `1` | Minimum age of achievements |
| `count` | int | `1` | Number of achievements to select |
| `is_optional` | boolean | `false` | Whether selection can be declined |
| `store_as` | string | *(auto)* | Variable name (defaults to `"selected_achievement"` for count=1, `"selected_achievements"` otherwise). Also accepts `store_result`. |

**Example**:
```json
{
  "type": "SelectAchievement",
  "max_age": 5,
  "is_optional": true,
  "store_as": "selected_achievement"
}
```

---

### `SelectColor`
Player chooses a color from available options.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"board_colors"` | Where to get options: `"board_colors"`, `"hand_colors"`, `"all_colors"`, or variable name |
| `available_colors` | array | `[]` | Explicit list of colors to choose from |
| `is_optional` | boolean | `false` | Whether selection can be declined |
| `store_result` | string | `"selected_color"` | Variable to store chosen color (also accepts `store_as`) |
| `filter_splayable_direction` | string | *(none)* | Filter to only colors that can be splayed in this direction: `"left"`, `"right"`, `"up"` |

**Example**:
```json
{
  "type": "SelectColor",
  "source": "board_colors",
  "filter_splayable_direction": "right",
  "store_result": "chosen_color"
}
```

---

### `SelectSymbol`
Player chooses a symbol type.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbols` | array | all 6 symbols | Available symbols (also accepts `available_symbols`) |
| `exclude_symbols` | array | `[]` | Symbols to exclude from selection |
| `description` | string | `"Select a symbol"` | Prompt text (also accepts `prompt`) |
| `store_result` | string | `"selected_symbol"` | Variable to store chosen symbol |
| `is_optional` | boolean | `false` | Whether selection can be declined |

**Valid symbols**: `"castle"`, `"leaf"`, `"lightbulb"`, `"crown"`, `"factory"`, `"clock"`

**Example**:
```json
{
  "type": "SelectSymbol",
  "target_player": "activating",
  "symbols": ["castle", "crown", "lightbulb", "factory", "clock"],
  "description": "Choose a symbol other than leaf",
  "store_result": "chosen_symbol"
}
```

---

### `FilterCards`
Non-interactive card filtering by criteria.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | `"hand"` | Cards to filter (variable name or location) |
| `criteria` | object | `{}` | Filtering criteria dict |
| `filter` | object | *(none)* | Nested filter format from card definitions |
| `store_result` | string | `"filtered"` | Variable to store filtered cards (also accepts `store_as`) |
| `target_player` | string | *(none)* | `"any_opponent"`, `"opponent"`, `"all"` for multi-player sources |

**Criteria keys**: `has_symbol`, `color`, `age`, `variable_age`, `min_age`, `max_age`, `highest`, `lowest`, `different_color_from_board`, `same_color_as_board`, `value`, `name`, `exclude_name`, `has_dogma`, `filter_func`

**Nested filter types**: `has_symbol`, `age_equals`, `not_name_equals`

**Example**:
```json
{
  "type": "FilterCards",
  "source": "hand",
  "filter": {
    "type": "age_equals",
    "age": "drawn_age"
  },
  "store_result": "matching_cards"
}
```

---

### `SelectAnyPlayer`
Player selects any player in the game (Unseen expansion).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `store_result` | string | `"selected_player"` | Variable to store selected player ID |
| `prompt` | string | `"Choose a player"` | Custom prompt text |
| `filter` | object | *(none)* | Filter: `has_card_age`, `has_achievement`, `has_color`, `min_score` |
| `exclude_self` | boolean | `false` | Exclude current player from selection |

---

## Board Manipulation

### `SplayCards`
Changes the splay direction of a color stack.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `color` | string | *(none)* | Color to splay, or variable name |
| `direction` | string | `"left"` | Splay direction: `"left"`, `"right"`, `"up"` |
| `is_optional` | boolean | `true` | Whether splaying can be declined |

**Note**: Requires at least 2 cards in the stack. Silently succeeds if already splayed in the requested direction.

**Example**:
```json
{
  "type": "SplayCards",
  "color": "blue",
  "direction": "right"
}
```

---

### `UnsplayCards`
Removes splay from color stacks (Unseen expansion).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `color` | string | *(none)* | Color to unsplay: `"red"`, `"blue"`, etc., `"all"`, or variable name |
| `target_player` | string | `"self"` | Whose board: `"self"`, `"opponent"`, `"all"` |
| `update_safeguards` | boolean | `true` | Whether to rebuild Safeguards after unsplaying |

---

### `TuckCard`
Places cards under (bottom of) existing board stacks.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cards` | string | `"selected_cards"` | Variable containing cards to tuck. `"hand"` = all hand cards |
| `from` | string | `"hand"` | Where to remove cards from |
| `color_filter` | string | *(none)* | Optional color restriction for tucking |
| `store_color` | string | *(none)* | Variable to store the color(s) tucked |
| `auto_splay` | boolean | `false` | Whether to automatically splay after tucking |
| `splay_direction` | string | `"left"` | Direction to splay if `auto_splay` is true |

**Side Effects**: Sets `tucked_count` variable. Tracks Monument special achievement.

**Example**:
```json
{
  "type": "TuckCard",
  "cards": "last_drawn",
  "auto_splay": true,
  "splay_direction": "left"
}
```

---

### `ExchangeCards`
Swaps cards between two locations.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_location` | string | `"hand"` | First location |
| `target_location` | string | `"score_pile"` | Second location |
| `selection_criteria` | string | `"highest_age"` | How to select: `"highest_age"`, `"lowest_age"`, `"all"` |
| `count` | int | *(none)* | Number of cards (none = all matching criteria) |
| `selection1` | string | *(none)* | Variable containing pre-selected cards for location 1 |
| `selection2` | string | *(none)* | Variable containing pre-selected cards for location 2 |

**Note**: When `selection1` and `selection2` are provided, uses those explicit selections instead of criteria-based selection.

**Example**:
```json
{
  "type": "ExchangeCards",
  "selection1": "highest_hand",
  "selection2": "highest_score"
}
```

---

### `TransferBetweenPlayers`
Moves cards between different players.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cards` | string | `"selected_cards"` | Variable containing cards (also accepts `selection`) |
| `source_player` | string | `"current"` | Source: `"current"`, `"demanding_player"`, `"active"`, `"opponent"`, `"opponent_any"`, `"target_player"`, or player_id (also accepts `from_player`) |
| `target_player` | string | `"demanding_player"` | Destination (same values as source_player) (also accepts `to_player`) |
| `source_location` | string | `"hand"` | Where to remove from (also accepts `from_location`) |
| `target_location` | string | `"score_pile"` | Where to place (also accepts `to_location`) |
| `filters` | array | `[]` | Filter conditions for `from_all_opponents` mode |
| `from_all_opponents` | boolean | `false` | Gather matching cards from all opponents |

**Side Effects**: Sets `transferred_cards` and `demand_iteration_transferred` variables.

**Example**:
```json
{
  "type": "TransferBetweenPlayers",
  "cards": "selected_cards",
  "source_player": "current",
  "target_player": "demanding_player",
  "source_location": "hand",
  "target_location": "score_pile"
}
```

---

### `MakeAvailable`
Makes cards available in a shared pool.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | `"selected_cards"` | Which cards (also accepts `cards`) |
| `source` | string | `"hand"` | Where cards come from: `"hand"`, `"board"`, `"score_pile"`, `"deck"` |
| `age` | int | *(none)* | If source is `"deck"`, which age to draw from |
| `count` | int | `1` | Number of cards |
| `pool_name` | string | `"available_cards"` | Name of the available pool |

**Special**: Handles special achievements by moving them from junk to available.

---

## Counting & Analysis

### `CountSymbols`
Counts symbols on a player's board.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | `"leaf"` | Symbol to count: `"castle"`, `"leaf"`, `"lightbulb"`, `"crown"`, `"factory"`, `"clock"` |
| `scope` | string | `"total_symbols"` | How to count: `"total_symbols"` or `"colors_with_symbol"` (unique colors) |
| `store_result` | string | `"symbol_count"` | Variable to store count (also accepts `store_as`) |
| `player` | string | `"self"` | Which player: `"self"`, `"target"` |

**Example**:
```json
{
  "type": "CountSymbols",
  "symbol": "crown",
  "store_result": "crown_count"
}
```

---

### `CountCards`
Counts cards in a specified location.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `location` | string | `"hand"` | Where to count: `"hand"`, `"score_pile"`, `"score"`, `"board"`, `"board_top"`, `"board_<color>"`, `"achievements"`, `"junk"`, `"junk_pile"` (also accepts `source`) |
| `player` | string | `"active"` | Which player: `"active"`, `"all"`, `"opponent"`, or player_id |
| `store_result` | string | `"card_count"` | Variable to store count (also accepts `store_as`) |
| `filter` | object | `{}` | Filter criteria: `color`, `age`, `has_symbol` |

**Example**:
```json
{
  "type": "CountCards",
  "location": "score_pile",
  "store_result": "score_count"
}
```

---

### `CountColorsWithSymbol`
Counts board colors containing a specific symbol.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | string | *(required)* | Symbol to look for |
| `cards` | string | *(none)* | Variable containing cards to check (if omitted, checks board) |
| `store_result` | string | `"color_count"` | Variable to store count (also accepts `store_as`) |

---

### `CountColorsWithSplay`
Counts colors that have a specific splay direction.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `direction` | string | `"any"` | Splay direction: `"left"`, `"right"`, `"up"`, `"aslant"`, `"any"` |
| `player` | string | `"active"` | Which player: `"active"`, `"opponent"`, or player_id |
| `store_result` | string | `"splay_count"` | Variable to store count |

---

### `CountUniqueColors`
Counts distinct colors on the board or in a card list.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cards` | string | *(none)* | Variable containing cards to count colors from |
| `source` | string | `"board"` | Source to count from |
| `compare_to` | string | *(none)* | `"opponents_boards"` for unique-to-player colors |
| `scope` | string | *(auto)* | `"from_cards"`, `"unique_to_player"`, `"total_colors"` |
| `store_result` | string | `"unique_color_count"` | Variable to store count (also accepts `store_as`) |

---

### `CountUniqueValues`
Counts distinct card ages/values.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | *(none)* | Variable containing cards (also accepts `source` or `cards`) |
| `criteria` | string | `"age"` | What to count: `"age"`, `"color"`, `"symbol_count"`, `"name"` |
| `store_result` | string | `"unique_count"` | Variable to store count |

---

### `CountUniqueSymbols`
Counts unique symbol types from cards or board.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | *(none)* | Variable containing cards (also accepts `cards`) |
| `scope` | string | `"cards"` | Where to count: `"card"`, `"cards"`, `"board"`, `"hand"`, `"all"` |
| `store_result` | string | `"unique_symbol_count"` | Variable to store count |

---

### `GetCardAge`
Retrieves the age of a card.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | *(required)* | Variable containing card(s) (also accepts `card`) |
| `store_result` | string | `"card_age"` | Variable to store the age (also accepts `store_as`) |

---

### `GetCardColor`
Gets the color of a card.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `card` | string | *(none)* | Variable containing the card |
| `source` | string | `"variable"` | How to find card: `"variable"`, `"last_drawn"`, `"top_card"` |
| `color` | string | *(none)* | If source is `"top_card"`, which color stack |
| `store_result` | string | `"card_color"` | Variable to store the color (also accepts `store_as`) |

---

### `GetCardColors`
Gets colors from one or more cards.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | *(required)* | Variable containing cards (also accepts `cards`) |
| `store_result` | string | `"card_colors"` | Variable to store the colors |
| `unique` | boolean | `false` | Return only unique colors |

---

### `GetCardSymbols`
Gets symbols from one or more cards.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | *(required)* | Variable containing cards (also accepts `cards`) |
| `store_result` | string | `"card_symbols"` | Variable to store symbols |
| `flatten` | boolean | `false` | Flatten symbols from multiple cards into one list |

---

### `GetSplayDirection`
Gets the current splay direction of a color stack.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `color` | string | *(required)* | Color to check (literal or variable reference) |
| `player` | string | *(none)* | Player to check (default: current player) |
| `store_result` | string | `"splay_direction"` | Variable to store direction |

---

### `GetLowestValue`
Finds the lowest value from a list of numbers or cards.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source` | string | *(required)* | Variable containing list (also accepts `list`) |
| `attribute` | string | `"age"` | Card attribute to compare |
| `store_result` | string | `"lowest_value"` | Variable to store lowest value |
| `store_item` | string | *(none)* | Variable to store the item with lowest value |

---

## Control Flow

### `ConditionalAction`
Executes actions based on conditions.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | object | `{}` | Condition to evaluate (see [Condition Types](#condition-types)) |
| `if_true` | array | *(none)* | Actions if true (also accepts `then_actions`, `true_action`) |
| `if_false` | array | *(none)* | Actions if false (also accepts `else_actions`, `false_action`) |

**Example**:
```json
{
  "type": "ConditionalAction",
  "condition": {
    "type": "variable_gt",
    "variable": "crown_count",
    "value": 3
  },
  "if_true": [
    { "type": "DrawCards", "age": 3, "count": 1 }
  ]
}
```

---

### `EvaluateCondition`
Evaluates a condition and stores the boolean result.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `condition` | object or string | *(required)* | Condition to evaluate |
| `store_result` | string | `"condition_result"` | Variable to store boolean result |

**Side Effects**: Always sets `last_evaluation` variable for use by `ConditionalAction`.

**String conditions**: Supports `>=`, `<=`, `>`, `<`, `==`, `!=` operators and `has_symbol` conditions.

---

### `LoopAction`
Repeats actions until a condition is met.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `actions` | array | `[]` | Actions to repeat (also accepts `action` for single) |
| `continue_condition` | object | *(none)* | Condition to check (also accepts `condition`) |
| `max_iterations` | int | `10` | Safety limit |
| `times` | string | *(none)* | Variable name for fixed iteration count |

---

### `RepeatAction`
Repeats actions a fixed number of times.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `count` | int or string | `1` | Number of repetitions (can be a variable name) |
| `actions` | array | `[]` | Actions to repeat (also accepts `action` for single) |

---

### `RevealAndProcess`
Draws/reveals cards and conditionally processes them. Supports two modes.

**Parameters (draw-based mode)**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_age` | int or string | `1` | Age to draw from |
| `count` | int | `1` | Number of cards to draw |
| `condition_check` | object | *(none)* | What to check on revealed cards |
| `success_action` | object | *(none)* | Action if condition met |
| `failure_action` | object | *(none)* | Action if condition not met |
| `store_revealed` | string | `"revealed_cards"` | Variable to store revealed cards |

**Parameters (selection-based mode)**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `selection` | string | *(none)* | Process existing selection |
| `actions` | array | `[]` | Nested actions to execute |

---

## Game Mechanics

### `DemandEffect`
Structural marker primitive for demand effects. **NOT directly executed** — demand routing is handled by ConsolidatedInitializationPhase and ConsolidatedSharingPhase.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `required_symbol` | string | *(none)* | Symbol for vulnerability check |
| `demand_actions` | array | `[]` | Actions vulnerable players execute |
| `repeat_on_compliance` | boolean | `false` | *(deprecated)* |
| `fallback_actions` | array | `[]` | *(deprecated)* |

---

### `ClaimAchievement`
Claims an achievement for the player.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `achievement` | string | *(none)* | Achievement name, or `"auto"` |
| `age` | int | *(none)* | Age of achievement to claim |
| `conditions` | array | `[]` | Additional conditions to check |
| `source` | string | `"auto"` | Where to achieve from: `"auto"`, `"board"`, `"safe"` (Unseen) |
| `safe_index` | int | *(none)* | Index in Safe (Unseen expansion) |

---

### `ExecuteDogma`
Recursively executes another card's dogma effect.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `card` | string | *(none)* | Variable containing card or card name |
| `source` | string | `"variable"` | How to find card: `"board_top"`, `"variable"`, `"specific"` |
| `color` | string | *(none)* | If source is `"board_top"`, which color stack |
| `player` | string | `"active"` | Which player's card |
| `effect_index` | int | *(none)* | Which effect to execute (default: all) |
| `execution_mode` | string | `"normal"` | `"normal"`, `"self"` (non-demand, no sharing), `"super"` (all effects, no sharing) |

---

### `SelfExecute`
Executes a card's non-demand dogma effects (Unseen expansion variant).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `card` | string | *(none)* | Card to execute |
| `card_variable` | string | *(none)* | Variable containing the card |
| `effect_index` | int | `0` | Which effect to execute |

---

### `ChooseOption`
Presents multiple-choice options to the player.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `options` | array | `[]` | List of option objects with `label`/`description`, `value`, and `actions` |
| `auto_select_single` | boolean | `true` | Auto-select if only one option |
| `filter_splayable` | string | *(none)* | Filter options by splay eligibility direction |

**Side Effects**: Stores chosen value in `"chosen_option"` variable.

**Option format**:
```json
{
  "label": "Draw a card",
  "value": "draw",
  "actions": [{ "type": "DrawCards", "age": 1, "count": 1 }]
}
```

---

### `CalculateValue`
Performs arithmetic operations on values.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `operation` | string | `"add"` | Operation: `"add"`, `"subtract"`, `"multiply"`, `"divide"` |
| `left` | any | *(none)* | Left operand: literal, variable name, or `{"type": "variable", "name": "..."}` (also accepts `operand1`, `value1`) |
| `right` | any | *(none)* | Right operand (same formats as left) (also accepts `operand2`, `value2`) |
| `store_result` | string | `"calculated_value"` | Variable to store result (also accepts `store_as`) |

**Example**:
```json
{
  "type": "CalculateValue",
  "operation": "add",
  "left": "crown_count",
  "right": 2,
  "store_result": "draw_age"
}
```

---

## Reveal Primitives

### `RevealCard`
Reveals a specific card to players.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `card` | string | *(none)* | Variable reference to card (also accepts `card_variable`) |
| `to_player` | string | *(none)* | Player who sees the card (default: all - public reveal) |
| `store_color` | string | *(none)* | Variable to store card's color |
| `store_age` | string | *(none)* | Variable to store card's age |
| `store_name` | string | *(none)* | Variable to store card's name |

---

### `RevealHand`
Reveals a player's hand to other players.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `player` | string | *(none)* | Player whose hand to reveal (default: current) |
| `to_player` | string | *(none)* | Who sees the hand (default: all - public) |
| `store_cards` | string | *(none)* | Variable to store revealed cards |
| `store_colors` | string | *(none)* | Variable to store card colors |

---

### `RevealTopCard`
Reveals (peeks at) the top card of a deck without drawing it.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `age` | int or string | *(required)* | Age of deck to reveal from |
| `store_result` | string | `"revealed_card"` | Variable to store card info |
| `store_color` | string | `"revealed_color"` | Variable to store card's color |
| `store_name` | string | `"revealed_name"` | Variable to store card's name |

---

### `RevealAndChoose`
Reveal cards from multiple sources and choose which to keep (Unseen expansion).

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reveal_sources` | array | `[]` | Sources to reveal from: `[{"type": "age_deck", "age": 7}, ...]` |
| `choose_count` | int | `1` | Number of cards to choose |
| `keep_action` | string | *(none)* | What to do with chosen cards: `"draw"`, `"meld"`, `"score"`, `"hand"` |
| `return_action` | string | *(none)* | What to do with unchosen cards: `"deck_bottom"`, `"deck_top"`, `"junk"` |
| `store_result` | string | *(none)* | Variable to store chosen cards |

---

## Utility Primitives

### `SetVariable`
Sets a variable in the action context.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `variable` | string | *(required)* | Variable name (also accepts `name`) |
| `value` | any | *(none)* | Value to set (literal or variable reference) |
| `from_variable` | string | *(none)* | Copy value from another variable |

---

### `IncrementVariable`
Increments a numeric variable.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `variable` | string | *(required)* | Variable to increment (also accepts `name`) |
| `amount` | int or string | `1` | Increment amount (can be a variable name) |
| `initialize` | int | `0` | Initial value if variable doesn't exist |

---

### `AppendToList`
Appends an item to a list variable.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `list_variable` | string | *(required)* | Name of the list variable (also accepts `list`, `variable`) |
| `item` | any | *(none)* | Item to append (also accepts `value`) |
| `from_variable` | string | *(none)* | Item from another variable |

---

### `ConvertToInt`
Converts a value to an integer.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `value` | any | *(none)* | Value to convert (literal or variable reference) |
| `from_variable` | string | *(none)* | Source variable |
| `store_result` | string | `"int_value"` | Variable to store result |
| `default` | int | `0` | Default if conversion fails |

---

### `NoOp`
Placeholder that does nothing. Used for unimplemented card effects.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `_metadata` | object | `{}` | Metadata about the intended primitive |
| `TODO` | string | *(none)* | Description of what needs implementation |
| `reason` | string | `"Not yet implemented"` | Reason for the no-op |

---

## Check/Verify Primitives

### `CheckHandNotEmpty`
Checks if a player's hand is not empty; stores boolean.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `player` | string | *(none)* | Player to check (default: current) |
| `store_result` | string | `"hand_not_empty"` | Variable to store boolean |

---

### `CheckIsMyTurn`
Checks if the current player is the active turn player; stores boolean.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `store_result` | string | `"is_my_turn"` | Variable to store boolean |

---

## Expansion: Echoes

### `Foreshadow`
Foreshadows a card (Echoes expansion). *Implementation pending.*

### `PromoteForecast`
Promotes a forecast card (Echoes expansion). *Implementation pending.*

---

## Expansion: Unseen

### `FlipCoin`
Random 50/50 coin flip.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `store_result` | string | `"flip_result"` | Variable to store result |
| `win_value` | string | `"win"` | Value stored for winning flip |
| `lose_value` | string | `"lose"` | Value stored for losing flip |
| `target_player` | string | *(none)* | Player flipping: `"opponent"` or default |

---

### `WinGame`
Immediately ends the game with a winner.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_player` | string | `"self"` | Who wins: `"self"`, `"opponent"`, `"demanding"` |

---

### `LoseGame`
Immediately ends the game with a loser.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_player` | string | `"self"` | Who loses: `"self"`, `"opponent"`, `"demanding"` |

---

### `AchieveSecret`
Achieves a secret from the player's safe as an achievement.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `secret_index` | int | *(none)* | Index of secret in safe (0-based) |
| `secret_age` | int | *(none)* | Age of secret to achieve (alternative to index) |
| `bypass_eligibility` | boolean | `false` | Achieve regardless of eligibility |
| `store_result` | string | `"achieved_secret"` | Variable to store achieved card |

---

### `RepeatEffect`
Signals that the current dogma effect should be repeated.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `effect_index` | int | *(none)* | Index of effect to repeat (default: current) |
| `max_repeats` | int | `1` | Maximum repeat count (-1 for unlimited) |

---

### `SafeguardAchievement`
Actively safeguards achievements via dogma effect.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `achievement_type` | string | *(none)* | Type: `"age"`, `"score"`, `"special"` |
| `value` | any | *(none)* | Specific value (e.g., 4 for age 4) |
| `achievement_variable` | string | *(none)* | Variable containing achievement ID |
| `count` | int | `1` | Number to safeguard (-1 for all) |
| `store_result` | string | `"safeguarded_achievements"` | Variable to store IDs |

---

### `SafeguardCard`
Safeguards achievements based on card conditions. **This IS a registered action primitive** with a full implementation.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `card_source` | string | *(none)* | Where to find cards: `"hand"`, `"board"`, `"score_pile"`, `"board_top"` |
| `condition` | object | *(none)* | Filter: `"color"`, `"age"`, `"has_symbol"` |
| `achievement_mapping` | string | *(none)* | How cards map to achievements: `"matching_age"`, `"matching_color"`, `"matching_value"` |
| `target_player` | string | *(none)* | Whose cards: `"self"`, `"opponent"`, `"all"` |
| `store_result` | string | *(none)* | Variable to store safeguarded achievement IDs |

---

### `AddToSafe`
Adds cards to a player's Safe as secrets.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cards` | string | `"drawn_cards"` | Variable containing cards (also accepts `source`) |
| `source` | string | *(none)* | Source location: `"hand"`, `"board_top"`, `"revealed"` |
| `target_player` | string | *(none)* | Whose Safe: `"self"`, `"opponent"`, `"selected_player"` |
| `count` | int | *(none)* | Number of cards (default: all in variable) |
| `store_result` | string | *(none)* | Variable to store count added |

---

### `TransferAchievementToSafe`
Transfers an achievement from one player to another player's Safe.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `achievement_id` | string | *(none)* | ID of achievement (e.g., `"age_5"`) |
| `achievement_variable` | string | *(none)* | Variable containing achievement ID |
| `source_player` | string | `"opponent"` | Who loses the achievement |
| `target_player` | string | `"self"` | Whose Safe gets it |
| `store_result` | string | `"transferred_achievement"` | Variable to store achievement |

---

### `TransferSecret`
Transfers a secret from one player's Safe to another location.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `source_player` | string | `"opponent"` | Whose Safe: `"self"`, `"opponent"`, `"selected_player"` |
| `secret_index` | int or string | `0` | Position: 0-based int, `"highest"`, `"lowest"`, `"random"` |
| `secret_age` | int | *(none)* | Alternative: find secret by age |
| `target` | string | `"achievements"` | Destination: `"achievements"`, `"opponent_safe"`, `"score_pile"`, `"hand"`, `"junk"` |
| `target_player` | string | *(none)* | Who receives the secret |
| `reveal` | boolean | `false` | Reveal card identity when transferring |
| `store_result` | string | *(none)* | Variable to store transferred card |

---

### `ScoreExcess`
Scores all but the top N cards of a color.

**Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `color` | string | *(required)* | Color of cards to score (or variable name) |
| `keep_top` | int | `5` | Number of cards to keep on top |
| `store_result` | string | `"scored_count"` | Variable to store count of scored cards |

---

## Condition Types

Conditions are used in `ConditionalAction`, `EvaluateCondition`, and `LoopAction`. They are organized into categories.

### Variable Conditions

| Type | Parameters | Description |
|------|-----------|-------------|
| `variable_exists` | `variable` | Variable exists and is not None |
| `variable_not_empty` | `variable` | Variable is a non-empty collection |
| `variable_true` | `variable` | Variable is truthy |
| `variable_false` | `variable` | Variable is falsy |
| `variable_equals` | `variable`, `value` | Variable equals value |
| `variable_gt` / `variable_greater_than` | `variable`, `value` | Variable > value |
| `variable_lt` | `variable`, `value` | Variable < value |
| `variable_gte` | `variable`, `value` | Variable >= value |
| `variable_lte` | `variable`, `value` | Variable <= value |
| `count_greater_than` | `variable`, `value` | Count of list > value |
| `count_less_than` | `variable`, `value` | Count of list < value |
| `count_equals` | `variable`, `value` | Count of list == value |
| `count_at_least` | `variable`, `value` | Count of list >= value |
| `last_evaluation_true` | *(none)* | Last EvaluateCondition was true |
| `compare` | `variable`, `operator`, `value` | Generic comparison |

**Example**:
```json
{ "type": "variable_gt", "variable": "crown_count", "value": 3 }
```

### Card Conditions

| Type | Parameters | Description |
|------|-----------|-------------|
| `cards_tucked` | `count` (default: 1) | Cards tucked >= count |
| `no_transfer` | *(none)* | No cards transferred |
| `cards_transferred` | `count` (default: 1) | Cards transferred >= count |
| `no_cards_transferred` | *(none)* | No cards transferred (checks both regular and demand) |
| `cards_selected` | *(none)* | Cards were selected |
| `cards_scored` | *(none)* | Cards were scored |
| `has_symbol` | `symbol`, `count` | Player has symbol on board |
| `card_color` | `color`, `variable` | Card matches color |
| `card_name` | `name`, `variable` | Card has specific name |
| `is_top_card` | `variable` | Card is a top card on board |
| `card_is_top_on_any_board` | `variable` | Card is top card on any player's board |
| `any_card_color` | `color`, `source` | Any card in source matches color |
| `at_least_n_same_color` | `count`, `source` | At least N cards share a color |
| `card_color_in_selected` | `color` | Selected cards include specific color |
| `cards_count_equals` | `variable`, `count` | Card list has exactly N items |
| `cards_are_top_on_any_board` | `variable` | All cards are top cards |
| `card_color_on_board` | `color` | Color exists on player's board |
| `last_drawn_color_equals` | `color` | Last drawn card matches color |
| `last_melded_has_symbol` | `symbol` | Last melded card has symbol |
| `last_returned_age_equals` | `age` | Last returned card matches age |
| `returned_count_equals` | `count` | Returned count matches |
| `returned_most_cards_this_action` | *(none)* | Player returned the most cards |

### Player Conditions

| Type | Parameters | Description |
|------|-----------|-------------|
| `has_cards` | `source`/`location`, `min_count` | Player has cards in location |
| `hand_not_empty` | *(none)* | Hand has at least 1 card |
| `hand_count_at_least` | `count` | Hand has >= N cards |
| `has_achievement` | `age` | Player has specific achievement |
| `has_twice_achievements_of_opponents` | *(none)* | Player has 2x opponents' achievements |
| `not_highest_score` | *(none)* | Player doesn't have highest score |
| `single_player_with_most_symbol` | `symbol` | Only player with most of symbol |
| `any_player_has_fewer_than_symbol` | `symbol`, `count` | Any player has < N of symbol |
| `no_player_has_more_symbol_than` | `symbol`, `count` | No player has > N of symbol |
| `only_player_with_condition` | `condition` | Only player meeting condition |
| `symbol_count` | `symbol`, `operator`, `value` | Symbol count comparison |
| `symbol_count_at_least` | `symbol`, `count` | Symbol count >= N |
| `all_non_color_top_cards_min_age` | `color`, `min_age` | All non-color top cards have min age |
| `all_top_cards_have_symbol` | `symbol` | All top cards have symbol |
| `color_on_board` | `color` | Color exists on board |
| `color_splayed` | `color`, `direction` | Color is splayed in direction |
| `color_splayed_aslant` | `color` | Color is splayed aslant |
| `color_not_splayed_aslant` | `color` | Color is NOT splayed aslant |
| `color_selected` | *(none)* | A color was selected |
| `color_count_at_least` | `count` | Board has >= N colors |

### Game State Conditions

| Type | Parameters | Description |
|------|-----------|-------------|
| `option_chosen` | `option` | Specific option was chosen |
| `user_choice` | `value` | User made specific choice |
| `true` | *(none)* | Always true |
| `tucked_under_age_11` | *(none)* | Card was tucked under age 11 |

### Logical Conditions

| Type | Parameters | Description |
|------|-----------|-------------|
| `and` | `conditions` (array) | All conditions must be true |
| `or` | `conditions` (array) | At least one must be true |
| `not` | `condition` (object) | Negates the inner condition |

**Example**:
```json
{
  "type": "and",
  "conditions": [
    { "type": "has_cards", "location": "hand", "min_count": 1 },
    { "type": "variable_gt", "variable": "score", "value": 10 }
  ]
}
```

### Expansion Conditions (Unseen + General)

High-frequency conditions used across expansion cards:

| Type | Parameters | Description |
|------|-----------|-------------|
| `choice_equals` | `choice`/`value` | Chosen option equals value |
| `card_selected` | `variable` | Card(s) selected in variable |
| `standard` | `achievement` | Achievement is standard (age 1-9) |
| `value_not_in_board_or_score` | `value` | Value not on board or in score pile |
| `color_is_splayed` | `color`, `direction` | Color has specific splay |
| `card_has_symbol` | `card`, `symbol` | Card has specific symbol |
| `value_equals` | `variable`, `value` | Value comparison |
| `value_at_least` | `variable`, `value` | Value >= threshold |
| `color_splayed_direction` | `color`, `direction` | Color splayed in direction |
| `color_not_on_board` | `color` | Color not present on board |
| `color_has_symbol` | `color`, `symbol` | Color stack has symbol |
| `color_equals` | `variable`, `color` | Variable equals color |
| `achievement_selected` | *(none)* | Achievement was selected |
| `coin_flip_result` | `expected` | Coin flip matches expected |
| `board_empty` | *(none)* | Player's board is empty |
| `card_exists` | `variable` | Card exists in variable |
| `is_current_turn` | *(none)* | It's the current player's turn |
| `greater_than` | `left`, `right` | Numeric comparison |
| `greater_than_or_equal` | `left`, `right` | Numeric comparison |
| `less_than` | `left`, `right` | Numeric comparison |
| `list_contains` | `list`, `item` | List contains item |
| `list_not_contains` | `list`, `item` | List doesn't contain item |

---

## Validation Rules

### Required Fields
- All action primitives MUST have a `"type"` field
- Card selection primitives MUST have either `"source"` or `"location"`
- Primitives that store results SHOULD have `"store_result"`

### Field Name Contracts
- **ALWAYS use `"eligible_cards"`** in StandardInteractionBuilder (never `"cards"`)
- **NEVER use underscore prefixes** on public fields (use `"store_result"` not `"_store_result"`)
- Use canonical location names: `"score_pile"` (not `"score"`), `"hand"` (not `"hands"`)

### Variable Lifecycle
- DrawCards clears `store_result` at START of execution
- LoopAction clears draw variables after iteration 1
- ScoreCards preserves `last_drawn` (next DrawCards will overwrite it)
- SelectCards removes cards from source location (move-object architecture)

### Parameter Precedence
- `target_player` takes precedence over `execute_as`
- `store_result` takes precedence over `store_as`
- `filter_criteria` and `filter` are both accepted (merged internally)
- Explicit values take precedence over variable references

---

## See Also

- [Action Variables Dictionary](../../backend/data/ACTION_VARIABLES.md) - Variable naming and storage patterns
- [Dogma Developer Guide](../DOGMA_DEVELOPER_GUIDE.md) - Implementation patterns
- [Current Architecture](../CURRENT_ARCHITECTURE.md) - System overview
- [BaseCards.json](../../backend/data/BaseCards.json) - Live card definitions

---

**Validation**: This schema is generated from source code. All parameters documented here correspond to `__init__` method config reads in the actual primitive classes.

**Updates**: When adding new primitives or parameters, update both the code and this document.

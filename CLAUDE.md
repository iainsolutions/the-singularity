# CLAUDE.md — The Singularity

A card game about the race to artificial superintelligence, re-themed from Innovation by Carl Chudyk.

## Quick Start

**Backend (FastAPI):**

```bash
python3 start_backend.py
```

**Frontend (React):**

```bash
./start_frontend.sh
```

**Run Tests:**

```bash
source venv/bin/activate && pytest test_scenarios/automation/ -v --timeout=120
```

## Architecture

- **Backend**: FastAPI + WebSockets + Redis
- **Frontend**: React + Vite
- **AI Player**: Anthropic Claude API (configurable difficulty)
- **Card Effects**: Declarative JSON (SingularityCards.json) + 40 action primitives

### Key Principles

- **Declarative Card Effects**: Card effects are data (JSON), not code
- **Action Primitives**: Modular building blocks for all card effects
- **eligible_cards Contract**: Always use `eligible_cards` field name for card selections
- **Board card ordering**: `[-1]` is the top card (deploy appends, archive inserts at 0)
- **Direct AI calls**: AI uses `perform_action()` directly, not HTTP self-calls
- **Symbols**: circuit, neural_net, data, algorithm, human_mind, robot
- **Domains**: Processing (blue), Labor (red), Ethics (green), Creativity (purple), Connection (yellow)

### Core Files

| File | Purpose |
| ------ | --------- |
| `backend/async_game_manager.py` | Game orchestration |
| `backend/dogma_v2/` | Dogma execution engine (8-phase pipeline) |
| `backend/action_primitives/` | 40 modular effect building blocks |
| `backend/data/SingularityCards.json` | 105 card definitions (declarative JSON) |
| `backend/services/ai_turn_executor.py` | AI player turn orchestration |
| `backend/services/ai_prompt_builder.py` | AI prompt construction |

### Documentation

- **[Action Primitives Schema](docs/specifications/ACTION_PRIMITIVES_SCHEMA.md)** — Complete parameter reference
- **[Action Variables](backend/data/ACTION_VARIABLES.md)** — Variable naming and lifecycle
- **[Game Rules](docs/RULES.md)** — Game rules reference

## Development Guidelines

- Use `eligible_cards` for card selections (never `cards` or `_eligible_cards`)
- Top card is `[-1]` in board stacks, bottom is `[0]`
- Use `logger.debug()` for debug info, not `logger.error()` or `logger.info()`
- No expansion code — base game only
- Run scenario tests after changes: `pytest test_scenarios/automation/ --timeout=120`

## Adding New Cards

All card data goes in `backend/data/SingularityCards.json`. No code changes needed.

1. Define card with action primitives
2. Run tests to verify
3. See ACTION_PRIMITIVES_SCHEMA.md for primitive reference

## AI Player

- 8 difficulty levels (novice → master) using different Claude models
- Temperature 0.3 for decisions, 1.0 when extended thinking enabled
- Minimal prompt: game state XML + available actions + concise rules
- Symbol hints on dogma actions (SHARED/DEMAND BLOCKED/DEMAND ACTIVE)

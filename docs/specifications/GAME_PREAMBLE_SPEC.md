# Game Preamble Spec — "Human vs Machine"

## Overview

A narrative intro screen shown **after** the player clicks "Start Game" in the lobby but **before** gameplay begins. It frames the match as a literal contest between human and machine intelligence, leaning into the meta-reality that the AI opponent actually *is* an AI.

The preamble is brief, atmospheric, and difficulty-aware — the tone shifts depending on whether you're facing ABACUS (a counting machine) or OMEGA (a post-singularity god).

---

## Where It Lives in the Flow

```
GameLobby (/)
  → Player clicks "Start Game"
  → handleStartGame() fires
  → NEW: GamePreamble screen appears (full-screen overlay or route)
  → Player clicks "Begin" / "Enter the Race"
  → Navigate to /game/:gameId (setup_card_selection or playing phase)
```

### Implementation Options (pick one)

**Option A — Full-screen overlay in GameLobby (recommended)**
Render `<GamePreamble>` as a modal/overlay when `gameState.phase` transitions to `setup_card_selection` or `playing`, but *before* navigating to `/game/:gameId`. The "Begin" button triggers the existing `navigate()` call.

**Option B — Intermediate route**
Add a `/game/:gameId/intro` route that renders the preamble, then navigates to `/game/:gameId` on dismiss. Slightly heavier but gives its own URL (useful if you ever want to link to it).

**Option A is simpler and keeps the lobby in control.**

---

## Component: `GamePreamble`

### Props

```js
{
  aiDifficulty: string,      // e.g. "novice", "master" — from gameState
  aiPersonality: {            // from the AI_PERSONALITIES data
    codename: string,         // "ABACUS", "OMEGA", etc.
    era: number,
    tagline: string,
    backstory: string,
  },
  playerName: string,         // the human player's name
  onBegin: () => void,        // callback to proceed to gameplay
}
```

### Files to Create

| File | Purpose |
|------|---------|
| `src/components/lobby/GamePreamble.js` | Component |
| `src/components/lobby/GamePreamble.module.css` | Styles |

---

## Narrative Structure

The screen has **three text beats** that appear in sequence (timed or scroll-revealed), then a call-to-action button.

### Beat 1 — The Stakes (universal, same every game)

> **The race to superintelligence has begun.**
>
> Two minds. Ten eras of discovery. One will reshape the future — the other will be left behind.

This is the "why are we here" moment. Short, punchy, sets the stakes.

### Beat 2 — The Opponent (dynamic, based on AI difficulty)

This section introduces the AI opponent by codename and adjusts tone based on difficulty tier.

**Low difficulty (novice, beginner):**

> Your opponent: **ABACUS**
> *"Counting beads in the dark."*
>
> A primitive intelligence. Methodical. Literal. It follows the rules — but it doesn't understand them. Not yet.

**Mid difficulty (intermediate, skilled, advanced):**

> Your opponent: **DEEP BLUE**
> *"I see twelve moves ahead. You see three."*
>
> A calculating mind that weighs every option with mechanical precision. It won't make mistakes. You'll have to outthink it.

**High difficulty (pro, expert, master):**

> Your opponent: **OMEGA**
> *"The game was decided before it began."*
>
> Beyond the singularity. Beyond comprehension. It doesn't play the game — it inhabits it. Every draw, every dogma, already mapped. This is not a match. It's a reckoning.

**Use the actual codename, tagline, and backstory from `AI_PERSONALITIES`** — the examples above are just to show the tone. The component should pull the real personality data.

### Beat 3 — The Human (always the same)

> But you have something it doesn't.
>
> Intuition. Creativity. The irrational spark that no model can replicate.
>
> Prove it matters.

### CTA Button

> **[Enter the Race]**

---

## Visual Design

### Aesthetic Direction

Dark, cinematic, minimal. Think: title card before a film. The lobby is light/functional — this screen is the tonal shift into *this matters*.

### Layout

- **Full viewport** — no lobby chrome visible
- **Centered text column** — max-width ~600px, vertically centered
- **Dark background** — `#0a0a0f` or similar near-black, with a subtle radial gradient or very faint circuit-board pattern
- **Text** — light (`#e0e0e0` body, `#ffffff` for emphasis), monospace or semi-mono for the AI codename
- **Tagline** — italicized, slightly dimmer (`#999`)

### Typography

- Beat 1 headline: `1.5rem`, bold, white
- Beat 1 body: `1.1rem`, light gray
- AI codename: `1.8rem`, bold, monospace (e.g. `"Courier New"` or import a mono font), white
- AI tagline: `1rem`, italic, `#999`
- AI description: `1rem`, light gray
- Beat 3: `1.1rem`, light gray, with "Prove it matters." as bold white
- CTA button: outlined, white text, subtle glow on hover

### Animation / Reveal

Each beat fades in sequentially with a short delay:

```
Beat 1:  fade in at 0ms,    duration 800ms
Beat 2:  fade in at 1200ms, duration 800ms
Beat 3:  fade in at 2400ms, duration 800ms
CTA:     fade in at 3400ms, duration 600ms
```

Use CSS `@keyframes fadeIn` + `animation-delay`. Keep it simple — no scroll-jacking, no parallax. Respect `prefers-reduced-motion` by showing everything immediately.

Optional: a very subtle typing/glitch effect on the AI codename (1-2 chars flicker before settling). Skip if it feels gimmicky.

### Escape Hatch

If the player has seen it before (use `localStorage` flag like `singularity_seen_preamble_{difficulty}`), show a small "Skip" link in the top-right corner that jumps straight to gameplay. First-time players for each difficulty should see the full sequence.

---

## Data Flow

### Getting AI personality data

The `AIPlayerSetup` component already fetches AI status from `/api/v1/ai/status`. The personality data is available in `AI_PERSONALITIES` on the backend and is partially exposed through the existing lobby data.

**Recommended approach:** When `handleStartGame()` succeeds, the `gameState` should already contain the AI player info (name includes codename, difficulty is known). Pass the difficulty to `GamePreamble`, which can either:

1. Use a hardcoded JS map of `difficulty → { codename, tagline, backstory }` (simplest — just mirror `AI_PERSONALITIES` client-side), or
2. Fetch from a new endpoint like `GET /api/v1/ai/personality/{difficulty}` (cleaner but requires backend change)

Option 1 is fine for now. The personality data rarely changes.

### Knowing the difficulty

The AI player's difficulty is visible in `gameState.players` — the AI player object should have a `difficulty` field (or it's visible in the lobby state). Check the existing player data structure.

---

## Edge Cases

| Case | Behavior |
|------|----------|
| **Human vs Human (no AI)** | Don't show preamble. Navigate directly to game. |
| **Multiple AI players** | Show preamble for the highest-difficulty AI (the "main" opponent). |
| **Player refreshes during preamble** | Lobby detects game phase, re-shows preamble (or skips if `localStorage` flag set). |
| **Game already in progress** | Skip preamble entirely — only show on fresh game start. |

---

## Accessibility

- All text is real DOM text (not canvas/image) — screen reader compatible
- Respect `prefers-reduced-motion`: skip animations, show all text immediately
- CTA button has proper focus state and is keyboard-navigable
- Sufficient contrast ratios (light text on dark bg should exceed 4.5:1)
- `aria-live="polite"` on the text container so screen readers announce beats as they appear

---

## Future Ideas (not in v1)

- **Opponent-specific ambient sound** — a low hum for ABACUS, something more unsettling for OMEGA
- **Win/loss record** — "You are 3-7 against DEEP BLUE. It remembers every game."
- **Post-game callback** — after the game ends, a brief AI "reaction" from the personality ("ABACUS: I... did not anticipate that configuration." / "OMEGA: As expected.")
- **Difficulty-specific background visuals** — ABACUS gets clockwork gears, OMEGA gets abstract geometry

/* tslint:disable */
/* eslint-disable */
/**
 * Auto-generated TypeScript definitions from Pydantic models
 * Do not modify this file directly - regenerate from backend models
 *
 * CRITICAL: These types use 'eligible_cards' field, NEVER 'cards'
 * This prevents the recurring field name bug.
 */

export interface CardReference {
  card_id: string;
  name: string;
  age: number;
  color: string;
  location: string;
}

export type CardSource = "hand" | "board" | "score_pile" | "all";

export interface InteractionData {
  message: string;
  source_player: string;
}

/**
 * CRITICAL: Uses 'eligible_cards' field, NEVER 'cards'
 * This is the canonical field name that prevents the recurring bug
 */
export interface CardSelectionData extends InteractionData {
  type: "select_cards";
  eligible_cards: CardReference[];  // CANONICAL FIELD - DO NOT RENAME
  min_count: number;
  max_count: number;
  source: CardSource;
  is_optional: boolean;
}

export interface OptionSelectionData extends InteractionData {
  type: "choose_option";
  options: string[];
  allow_cancel: boolean;
  default_option?: string;
}

export interface BoardSelectionData extends InteractionData {
  type: "select_board";
  eligible_boards: string[];
  allow_own_board: boolean;
}

export interface PlayerSelectionData extends InteractionData {
  type: "select_player";
  eligible_players: string[];
  exclude_self: boolean;
}

export interface AchievementSelectionData extends InteractionData {
  type: "select_achievement";
  eligible_achievements: any[];
  is_optional: boolean;
}

export interface SymbolSelectionData extends InteractionData {
  type: "select_symbol";
  available_symbols: string[];
  is_optional: boolean;
}

export interface ColorSelectionData extends InteractionData {
  type: "select_color";
  available_colors: string[];
  is_optional: boolean;
}

export interface ReturnCardsData extends InteractionData {
  type: "return_cards";
  eligible_cards: CardReference[];
  min_count: number;
  max_count: number;
  is_optional: boolean;
}

export interface TiebreakerSelectionData extends InteractionData {
  type: "choose_highest_tie";
  tied_cards: CardReference[];
}

export type InteractionDataUnion =
  | CardSelectionData
  | OptionSelectionData
  | BoardSelectionData
  | PlayerSelectionData
  | AchievementSelectionData
  | SymbolSelectionData
  | ColorSelectionData
  | ReturnCardsData
  | TiebreakerSelectionData;

// Type guards for runtime validation
export function isCardSelectionData(data: any): data is CardSelectionData {
  return data?.type === "select_cards" && Array.isArray(data?.eligible_cards);
}

export function isOptionSelectionData(data: any): data is OptionSelectionData {
  return data?.type === "choose_option" && Array.isArray(data?.options);
}

export function isBoardSelectionData(data: any): data is BoardSelectionData {
  return data?.type === "select_board" && Array.isArray(data?.eligible_boards);
}

export function isPlayerSelectionData(data: any): data is PlayerSelectionData {
  return data?.type === "select_player" && Array.isArray(data?.eligible_players);
}

export function isAchievementSelectionData(data: any): data is AchievementSelectionData {
  return data?.type === "select_achievement" && Array.isArray(data?.eligible_achievements);
}

export function isSymbolSelectionData(data: any): data is SymbolSelectionData {
  return data?.type === "select_symbol" && Array.isArray(data?.available_symbols);
}

export function isColorSelectionData(data: any): data is ColorSelectionData {
  return data?.type === "select_color" && Array.isArray(data?.available_colors);
}

export function isReturnCardsData(data: any): data is ReturnCardsData {
  return data?.type === "return_cards" && Array.isArray(data?.eligible_cards);
}

export function isTiebreakerSelectionData(data: any): data is TiebreakerSelectionData {
  return data?.type === "choose_highest_tie" && Array.isArray(data?.tied_cards);
}

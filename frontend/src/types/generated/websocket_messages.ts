/* tslint:disable */
/* eslint-disable */
/**
 * Auto-generated TypeScript definitions from Pydantic models
 * Do not modify this file directly - regenerate from backend models
 */

import { InteractionDataUnion } from './interaction_data';

export type MessageType = "game_state" | "dogma_interaction" | "player_action" | "error" | "connection";

export type InteractionType = "select_cards" | "choose_option" | "select_board" | "select_player";

export interface WebSocketMessage {
  type: MessageType;
  game_id: string;
  player_id?: string;
  timestamp: string;
  sequence_number?: number;
}

export interface DogmaInteractionRequest extends WebSocketMessage {
  type: "dogma_interaction";
  interaction_type: InteractionType;
  data: InteractionDataUnion;
  timeout_seconds?: number;
  can_cancel: boolean;
}

export interface InteractionResponse {
  interaction_id: string;
  selected_cards?: string[];
  chosen_option?: string;
  cancelled: boolean;
  timestamp: string;
}

export interface ErrorResponse extends WebSocketMessage {
  type: "error";
  error_code: string;
  error_category: string;
  message: string;
  details?: Record<string, any>;
  suggested_action?: string;
  retry_possible: boolean;
}

export interface GameStateUpdate extends WebSocketMessage {
  type: "game_state";
  game_state: Record<string, any>;
  updated_fields?: string[];
}

// Type guards
export function isDogmaInteractionRequest(data: any): data is DogmaInteractionRequest {
  return data?.type === "dogma_interaction" && data?.interaction_type && data?.data;
}

export function isInteractionResponse(data: any): data is InteractionResponse {
  return typeof data?.interaction_id === "string";
}

export function isErrorResponse(data: any): data is ErrorResponse {
  return data?.type === "error" && typeof data?.error_code === "string";
}

export function isGameStateUpdate(data: any): data is GameStateUpdate {
  return data?.type === "game_state" && typeof data?.game_state === "object";
}

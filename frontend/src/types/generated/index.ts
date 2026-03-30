/* tslint:disable */
/* eslint-disable */
/**
 * Auto-generated TypeScript definitions from Pydantic models
 * Do not modify this file directly - regenerate from backend models
 *
 * CRITICAL: These types use 'eligible_cards' field, NEVER 'cards'
 * This prevents the recurring field name bug.
 */

export * from './interaction_data';
export * from './websocket_messages';

// Re-export commonly used types
export type {
  CardSelectionData,
  CardReference
} from './interaction_data';

export type {
  DogmaInteractionRequest,
  InteractionResponse
} from './websocket_messages';

// Validation helpers
export {
  isCardSelectionData
} from './interaction_data';

export {
  isDogmaInteractionRequest,
  isInteractionResponse
} from './websocket_messages';

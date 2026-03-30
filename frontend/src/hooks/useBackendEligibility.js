import { useMemo } from "react";

/**
 * Custom hook to extract Phase 1A backend eligibility metadata from pending actions
 *
 * This hook encapsulates the logic for extracting eligibility information that the
 * backend now provides in StandardInteractionBuilder. This reduces duplication
 * across components and provides a single source of truth for accessing:
 * - eligible_card_ids: List of card IDs that are eligible for selection (O(1) lookup)
 * - clickable_locations: Which card sources are clickable (hand, board.red_cards, etc.)
 * - clickable_player_ids: Which player boards are clickable
 *
 * @param {Object} pendingAction - The pending action object from game state or dogma response
 * @returns {Object} Eligibility metadata with three arrays
 *
 * @example
 * const { eligibleCardIds, clickableLocations, clickablePlayerIds } =
 *   useBackendEligibility(pendingAction);
 *
 * // Check if a card is eligible (O(1) lookup)
 * const isEligible = eligibleCardIds.includes(card.card_id);
 *
 * // Check if hand is clickable
 * const handClickable = clickableLocations.includes('hand');
 *
 * // Check if this player's board is clickable
 * const boardClickable = clickablePlayerIds.includes(player.id);
 */
export function useBackendEligibility(pendingAction) {
  return useMemo(() => {
    // Extract interaction_data from the pending action
    // Check multiple possible paths due to varying message structures:
    // 1. pendingAction.context.interaction_data.data (dogma_v2 format)
    // 2. pendingAction.context.interaction_data (flattened format)
    // 3. pendingAction.context (direct context format)
    const interactionDataNested = pendingAction?.context?.interaction_data?.data;
    const interactionDataFlat = pendingAction?.context?.interaction_data;
    const contextDirect = pendingAction?.context;

    // Find eligible_card_ids from any available path
    const eligibleCardIds =
      interactionDataNested?.eligible_card_ids ||
      interactionDataFlat?.eligible_card_ids ||
      contextDirect?.eligible_card_ids ||
      [];

    // Find clickable_locations from any available path
    const clickableLocations =
      interactionDataNested?.clickable_locations ||
      interactionDataFlat?.clickable_locations ||
      contextDirect?.clickable_locations ||
      [];

    // Find clickable_player_ids from any available path
    const clickablePlayerIds =
      interactionDataNested?.clickable_player_ids ||
      interactionDataFlat?.clickable_player_ids ||
      contextDirect?.clickable_player_ids ||
      [];

    return {
      // Phase 1A: eligible_card_ids for O(1) lookup
      eligibleCardIds,

      // Phase 1A: clickable_locations (which card sources are clickable)
      clickableLocations,

      // Phase 1A: clickable_player_ids (which player boards are clickable)
      clickablePlayerIds,
    };
  }, [pendingAction]);
}

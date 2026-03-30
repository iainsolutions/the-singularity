/**
 * Game logic utility functions
 * Contains pure functions for game calculations and logic
 */

/**
 * Calculate the actual age that will be drawn (accounting for age skipping)
 */
export function calculateActualDrawAge(requestedAge, ageDeckSizes) {
  if (!ageDeckSizes) return null;

  // Skip through empty ages starting from requested age
  for (let age = requestedAge; age <= 10; age++) {
    if (ageDeckSizes[age] > 0) {
      return age;
    }
  }
  return null; // All ages exhausted - would trigger game end
}

/**
 * Check if player needs to respond to a dogma action
 */
export function playerNeedsToRespond(pendingDogmaAction, playerId, currentPlayer, allPlayers) {
  if (!pendingDogmaAction) return false;

  // For dogma_v2_interaction, target_player_id is in the context
  const targetPlayerId =
    pendingDogmaAction.target_player_id || pendingDogmaAction.context?.target_player_id;

  return (
    targetPlayerId === playerId ||
    // Also check if we're the target player by matching the current game player
    (currentPlayer &&
      allPlayers.some((p) => p.id === targetPlayerId && p.name === currentPlayer.name))
  );
}

/**
 * Get the message for a dogma response
 */
export function getDogmaResponseMessage(pendingAction) {
  if (!pendingAction) return "";

  const { action_type, card_name, type, context } = pendingAction;

  // For dogma v2 interactions, use the message from the backend
  if (action_type === "dogma_v2_interaction") {
    // The interaction data contains the actual message from the backend
    const interactionData = context?.interaction_data;
    if (interactionData?.message) {
      return interactionData.message;
    }
    // Also check the data object
    if (interactionData?.data?.message) {
      return interactionData.data.message;
    }
    // Check direct context message
    if (context?.message) {
      return context.message;
    }
    // Fallback if no message provided
    if (card_name === "Domestication") {
      return "Choose a lowest-age card from your hand to meld.";
    }
    return `${card_name || "Card"}: Select cards`;
  }

  // Legacy code path - should not be reached with v2 system
  // Handle choose_option type
  if (action_type === "choose_option" || type === "choose_option") {
    return pendingAction.message || "Choose an option:";
  }

  // Default fallback
  return `Respond to ${card_name || "dogma"} action`;
}

/**
 * Check if a dogma response can be declined
 */
export function canDeclineDogmaResponse(pendingAction) {
  if (!pendingAction) return false;

  const { action_type, context } = pendingAction;

  // For dogma v2 interactions, check the interaction data
  if (action_type === "dogma_v2_interaction") {
    const interactionData = context?.interaction_data;
    // CRITICAL FIX: Backend uses 'can_cancel' not 'is_optional'
    // Check both direct (interactionData.can_cancel) and wrapped (interactionData.data.can_cancel) structures
    return (
      interactionData?.can_cancel === true ||
      interactionData?.data?.can_cancel === true ||
      context?.can_cancel === true ||
      context?.is_optional === true
    );
  }

  // Legacy code path - should not be reached with v2 system
  return context?.is_optional === true || context?.can_decline === true;
}

/**
 * Get the decline button text for a dogma response
 */
export function getDeclineButtonText(pendingAction) {
  if (!pendingAction) return "Decline";

  const { action_type, context } = pendingAction;

  // For dogma v2 interactions, could have custom decline text
  if (action_type === "dogma_v2_interaction") {
    const interactionData = context?.interaction_data?.data;
    return interactionData?.decline_text || context?.decline_text || "Decline";
  }

  return "Decline";
}

/**
 * Get the highest age card from a list of cards
 */
export function getHighestAgeCard(cards) {
  if (!cards || cards.length === 0) return null;

  return cards.reduce((highest, card) => {
    return !highest || card.age > highest.age ? card : highest;
  }, null);
}

/**
 * Get cards of a specific color from a player's board
 */
export function getCardsOfColor(playerBoard, color) {
  if (!playerBoard || !color) return [];

  const colorMap = {
    blue: playerBoard.blue_cards || [],
    red: playerBoard.red_cards || [],
    green: playerBoard.green_cards || [],
    purple: playerBoard.purple_cards || [],
    yellow: playerBoard.yellow_cards || [],
  };

  return colorMap[color] || [];
}

/**
 * Check if a player has any cards of a specific color on their board
 */
export function hasColorOnBoard(playerBoard, color) {
  const cards = getCardsOfColor(playerBoard, color);
  return cards.length > 0;
}

/**
 * Get all unique colors on a player's board
 */
export function getBoardColors(playerBoard) {
  const colors = [];

  if (playerBoard?.blue_cards?.length > 0) colors.push("blue");
  if (playerBoard?.red_cards?.length > 0) colors.push("red");
  if (playerBoard?.green_cards?.length > 0) colors.push("green");
  if (playerBoard?.purple_cards?.length > 0) colors.push("purple");
  if (playerBoard?.yellow_cards?.length > 0) colors.push("yellow");

  return colors;
}

/**
 * Check if a card is eligible for dogma selection
 * Handles both StandardInteractionBuilder format and nested interaction_data
 * CRITICAL: Uses 'eligible_cards' field name (not 'cards')
 */
export function isCardEligibleForDogma(card, pendingAction) {
  if (!card || !pendingAction) {
    return false;
  }

  // Special case: Achievement selection should not allow hand/board card clicks
  const interactionType =
    pendingAction.context?.interaction_data?.data?.type ||
    pendingAction.context?.data?.type;
  if (interactionType === "select_achievement") {
    return false;
  }

  // Get eligible cards from various possible locations
  let eligibleCards = null;

  // Check StandardInteractionBuilder direct format
  if (pendingAction.context?.data?.eligible_cards) {
    eligibleCards = pendingAction.context.data.eligible_cards;
  }
  // Check nested interaction_data format
  else if (pendingAction.context?.interaction_data?.data?.eligible_cards) {
    eligibleCards = pendingAction.context.interaction_data.data.eligible_cards;
  }
  // Check flattened interaction_data format
  else if (pendingAction.context?.interaction_data?.eligible_cards) {
    eligibleCards = pendingAction.context.interaction_data.eligible_cards;
  }
  // Check enhancedPendingAction format with context.eligible_cards
  else if (pendingAction.context?.eligible_cards) {
    eligibleCards = pendingAction.context.eligible_cards;
  }

  if (!eligibleCards || !Array.isArray(eligibleCards)) {
    return false;
  }

  // Match by card_id or name
  return eligibleCards.some((eligibleCard) => {
    // Handle string IDs/names (e.g., ['test-card-123', 'other-card'] or ['Tools', 'Other'])
    if (typeof eligibleCard === "string") {
      return eligibleCard === card.card_id || eligibleCard === card.name;
    }

    // Handle card objects
    return (
      (eligibleCard.card_id && eligibleCard.card_id === card.card_id) ||
      (eligibleCard.name && eligibleCard.name === card.name)
    );
  });
}

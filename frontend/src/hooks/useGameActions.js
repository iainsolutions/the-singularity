import { useCallback, useEffect, useState } from "react";
import { createLogger } from "../utils/logger";

// Create logger for GameActions
const logger = createLogger("GameActions");

export function useGameActions(sendWebSocketMessage, pendingInteraction = null, gameState = null, playerId = null) {
  const [selectedCard, setSelectedCard] = useState(null);
  const [selectedCardLocation, setSelectedCardLocation] = useState(null);
  const [selectedAction, setSelectedAction] = useState(null);
  const [selectedAge, setSelectedAge] = useState(1);
  const [multiSelectedCards, setMultiSelectedCards] = useState([]);

  // Clear stale card selection when game state changes
  // Only for hand cards — board cards are selected for dogma, not meld
  useEffect(() => {
    if (!selectedCard || !selectedCardLocation || !gameState?.players || !playerId) return;
    if (selectedCardLocation !== "hand") return; // Only check hand selections
    const me = gameState.players.find((p) => p.id === playerId);
    if (!me) return;
    const hand = me.hand || [];
    // Use card_id for matching (unique), fall back to name+age for safety
    const stillInHand = hand.some((c) => {
      if (selectedCard.card_id && c.card_id) return c.card_id === selectedCard.card_id;
      return c.name === selectedCard.name && c.age === selectedCard.age;
    });
    if (!stillInHand) {
      logger.debug(`Clearing stale selection: ${selectedCard.name} no longer in hand`);
      setSelectedCard(null);
      setSelectedCardLocation(null);
      setMultiSelectedCards([]);
    }
  }, [gameState, selectedCard, selectedCardLocation, playerId]);

  // Unseen expansion: Meld source modal state
  const [meldSourceModalOpen, setMeldSourceModalOpen] = useState(false);
  const [meldSourceModalLoading, setMeldSourceModalLoading] = useState(false);
  const [meldSourceModalError, setMeldSourceModalError] = useState(null);
  const [pendingMeldCard, setPendingMeldCard] = useState(null);

  const handleDraw = useCallback(
    async (actualDrawAge) => {
      if (actualDrawAge === null) {
        logger.warn("Cannot draw: all ages exhausted");
        return;
      }

      try {
        sendWebSocketMessage({
          type: "game_action",
          data: {
            action_type: "draw",
          },
        });
        setSelectedAction(null);
      } catch (error) {
        logger.error("Draw action failed:", error);
      }
    },
    [sendWebSocketMessage],
  );

  const handleMeld = useCallback(
    async (card = null) => {
      const cardToMeld = card || selectedCard;
      if (!cardToMeld) {
        alert("Please select a card from your hand to meld");
        return;
      }

      // Check if Unseen expansion is enabled and player has cards in Safe
      const currentPlayer = gameState?.players?.find((p) => p.id === playerId);
      const unseenEnabled = gameState?.state?.expansion_config?.enabled_expansions?.includes("unseen");
      const hasSafeCards = currentPlayer?.safe && currentPlayer.safe.card_count > 0;

      if (unseenEnabled && hasSafeCards) {
        // Show MeldSourceModal to let player choose source (hand vs Safe)
        logger.debug("Unseen expansion enabled with Safe cards - showing source modal");
        setPendingMeldCard(cardToMeld);
        setMeldSourceModalOpen(true);
        return;
      }

      // Normal meld from hand
      try {
        // Use card_id instead of card_name for unique identification
        // Fall back to card_name if card_id not available
        sendWebSocketMessage({
          type: "game_action",
          data: {
            action_type: "meld",
            card_id: cardToMeld.card_id || cardToMeld.id,
            card_name: cardToMeld.name, // Include as fallback
          },
        });
        setSelectedCard(null);
        setSelectedCardLocation(null);
        setSelectedAction(null);
      } catch (error) {
        logger.error("Meld action failed:", error);
      }
    },
    [selectedCard, sendWebSocketMessage, gameState],
  );

  // Handle meld source confirmation (Unseen expansion)
  const handleMeldSourceConfirm = useCallback(
    async (source, selectedSafeIndex = null, cardFromHand = null) => {
      setMeldSourceModalLoading(true);
      setMeldSourceModalError(null);

      try {
        if (source === "safe") {
          // Meld from Safe
          if (selectedSafeIndex === null) {
            setMeldSourceModalError("Please select a secret from your Safe");
            setMeldSourceModalLoading(false);
            return;
          }

          const currentPlayer = gameState?.players?.find((p) => p.id === playerId);
          const targetColor = pendingMeldCard?.color;

          logger.debug("Melding from Safe", { selectedSafeIndex, targetColor });

          sendWebSocketMessage({
            type: "game_action",
            data: {
              action_type: "meld",
              source: "safe",
              secret_index: selectedSafeIndex,
              target_color: targetColor,
            },
          });
        } else {
          // Meld from hand
          const cardToMeld = cardFromHand || pendingMeldCard;
          if (!cardToMeld) {
            setMeldSourceModalError("No card selected from hand");
            setMeldSourceModalLoading(false);
            return;
          }

          logger.debug("Melding from hand", { card: cardToMeld.name });

          sendWebSocketMessage({
            type: "game_action",
            data: {
              action_type: "meld",
              card_id: cardToMeld.card_id || cardToMeld.id,
              card_name: cardToMeld.name,
            },
          });
        }

        // Close modal and clear state
        setMeldSourceModalOpen(false);
        setMeldSourceModalLoading(false);
        setPendingMeldCard(null);
        setSelectedCard(null);
        setSelectedCardLocation(null);
        setSelectedAction(null);
      } catch (error) {
        logger.error("Meld source confirmation failed:", error);
        setMeldSourceModalError(error.message || "Meld failed");
        setMeldSourceModalLoading(false);
      }
    },
    [pendingMeldCard, sendWebSocketMessage, gameState],
  );

  // Handle meld source modal close
  const handleMeldSourceModalClose = useCallback(() => {
    setMeldSourceModalOpen(false);
    setMeldSourceModalError(null);
    setPendingMeldCard(null);
  }, []);

  const handleDogma = useCallback(
    async (card = null, options = {}) => {
      // Check if there's a pending interaction - if so, don't send a new dogma action
      if (pendingInteraction) {
        console.log("⚠️ Cannot start new dogma - pending interaction exists:", pendingInteraction);
        logger.warn("Attempted to start dogma while interaction is pending", {
          pendingInteraction: pendingInteraction?.type || pendingInteraction?.action_type,
        });
        return;
      }

      const cardToDogma = card || selectedCard;
      if (!cardToDogma) {
        alert("Please select a card on your board to activate");
        return;
      }

      try {
        // Build the data payload with optional endorse parameters
        const data = {
          action_type: "dogma",
          card_name: cardToDogma.name,
        };

        // Add endorse parameters if provided (Cities expansion)
        if (options.endorse_city_id && options.endorse_junk_id) {
          data.endorse_city_id = options.endorse_city_id;
          data.endorse_junk_id = options.endorse_junk_id;
          console.log('🌟 [useGameActions] Sending dogma with endorse:', data);
        }

        sendWebSocketMessage({
          type: "game_action",
          data,
        });

        // Only clear state if message was sent successfully
        if (setSelectedCard) setSelectedCard(null);
        if (setSelectedCardLocation) setSelectedCardLocation(null);
        if (setSelectedAction) setSelectedAction(null);
      } catch (error) {
        console.error("Dogma action failed:", error);
        logger.error("Dogma action failed:", error);
      }
    },
    [selectedCard, sendWebSocketMessage, pendingInteraction],
  );

  const handleAchieve = useCallback(async () => {
    try {
      // Find eligible ages from computed_state
      const currentPlayer = gameState?.players?.find((p) => p.id === playerId);
      const eligibleAges = currentPlayer?.computed_state?.can_achieve || [];
      const ageToAchieve = eligibleAges.includes(selectedAge) ? selectedAge : eligibleAges[0];

      if (!ageToAchieve) {
        logger.warn("Cannot achieve: no eligible ages");
        return;
      }

      sendWebSocketMessage({
        type: "game_action",
        data: {
          action_type: "achieve",
          age: ageToAchieve,
        },
      });
    } catch (error) {
      logger.error("Achieve action failed:", error);
    }
  }, [selectedAge, sendWebSocketMessage, gameState, playerId]);

  const executeSelectedAction = useCallback(() => {
    switch (selectedAction) {
      case "meld":
        handleMeld();
        break;
      case "dogma":
        handleDogma();
        break;
      case "achieve":
        handleAchieve();
        break;
      default:
        break;
    }
  }, [selectedAction, handleMeld, handleDogma, handleAchieve]);

  const handleDogmaResponse = useCallback(
    async (card, pendingAction) => {
      try {
        // CONSOLIDATION FIX: All single card responses now use v2 WebSocket system
        const transactionId = pendingAction?.context?.transaction_id;
        const cardId = card.card_id || card.id;

        if (transactionId) {
          // Use v2 WebSocket system with transaction ID
          sendWebSocketMessage({
            type: "dogma_response",
            transaction_id: transactionId,
            selected_cards: [cardId],
            card_id: cardId, // Also send as individual field for backend compatibility
          });
        } else {
          // Fallback for any remaining non-v2 interactions (should be rare)
          logger.warn(
            "Single card dogma response without transaction ID - using fallback WebSocket path",
          );
          sendWebSocketMessage({
            type: "dogma_response",
            selected_cards: [cardId],
            card_id: cardId,
          });
        }
      } catch (error) {
        logger.error("Dogma response failed:", error);
      }
    },
    [sendWebSocketMessage],
  );

  const handleMultiCardDogmaResponse = useCallback(
    async (cards, pendingAction) => {
      console.log("🎯 [handleMultiCardDogmaResponse] Function ENTERED", {
        cardsCount: cards?.length,
        cardsType: typeof cards,
        cards: cards,
        pendingAction: pendingAction?.action_type,
      });

      // Defensive check - ensure sendWebSocketMessage is available
      if (!sendWebSocketMessage || typeof sendWebSocketMessage !== "function") {
        console.error("💥 sendWebSocketMessage is not available or not a function");
        logger.error("sendWebSocketMessage is not available or not a function");
        return;
      }

      // Handle the case where cards might be null, undefined, or an option object
      // This happens when called from ActionsPanel option choices or empty selections
      let actualCards = [];

      if (Array.isArray(cards)) {
        actualCards = cards;
      } else if (cards === null || cards === undefined) {
        // Use multiSelectedCards from the current state
        actualCards = multiSelectedCards;
        console.log("🔄 Using multiSelectedCards as cards array", { actualCards });
      } else if (typeof cards === "object" && cards.chosen_option !== undefined) {
        // This is an option choice, not a card selection - handle it differently
        console.log("🎯 Detected option choice, handling via option path");
        // Check multiple locations for transaction_id
        const transactionId = pendingAction?.context?.transaction_id || pendingAction?.transaction_id;
        console.log("🔍 Option choice transaction_id lookup:", {
          contextTxId: pendingAction?.context?.transaction_id,
          rootTxId: pendingAction?.transaction_id,
          finalTxId: transactionId,
          pendingActionKeys: pendingAction ? Object.keys(pendingAction) : null,
        });

        try {
          if (transactionId) {
            sendWebSocketMessage({
              type: "dogma_response",
              transaction_id: transactionId,
              chosen_option: cards.chosen_option,
            });
          } else {
            sendWebSocketMessage({
              type: "dogma_response",
              chosen_option: cards.chosen_option,
            });
          }
        } catch (error) {
          console.error("💥 Error sending option choice:", error);
          logger.error("Error sending option choice:", error);
        }
        return; // Exit early for option choices
      } else {
        console.warn("⚠️ Unexpected cards parameter type", { cards, type: typeof cards });
        actualCards = multiSelectedCards;
      }

      console.log("🔍 About to process cards", { actualCards });

      try {
        if (actualCards && actualCards.length > 0) {
          // Defensive check - ensure all cards have required properties
          const safeCards = actualCards.filter((c) => c && (c.name || c.card_id || c.id));
          if (safeCards.length !== actualCards.length) {
            console.warn("⚠️ Some cards are missing required properties", {
              original: actualCards.length,
              safe: safeCards.length,
            });
          }
          logger.debug("handleMultiCardDogmaResponse called", {
            cards: safeCards.map((c) => ({
              name: c.name || "Unknown",
              id: c.card_id || c.id || "Unknown",
            })),
            pendingAction,
          });
        } else {
          logger.debug("handleMultiCardDogmaResponse called with empty cards", {
            pendingAction,
          });
        }
        console.log("✅ Logger debug call completed");
      } catch (mapError) {
        console.error("💥 Error in cards.map:", mapError);
        return;
      }

      console.log("🚀 Entering main try-catch block");

      try {
        console.log("🔍 Checking action type", { actionType: pendingAction?.action_type });

        // CONSOLIDATION FIX: All multi-card responses now use v2 WebSocket system
        const transactionId = pendingAction?.context?.transaction_id;

        // Defensive card ID extraction with error handling
        let cardIds = [];
        try {
          cardIds = actualCards
            .filter((c) => c && (c.card_id || c.id)) // Filter out invalid cards
            .map((c) => c.card_id || c.id);

          if (cardIds.length !== actualCards.length) {
            console.warn("⚠️ Some cards couldn't be mapped to IDs", {
              original: actualCards.length,
              mapped: cardIds.length,
            });
          }
        } catch (idError) {
          console.error("💥 Error extracting card IDs:", idError);
          logger.error("Error extracting card IDs:", idError);
          return;
        }

        if (transactionId) {
          console.log("📡 Taking DogmaV2 WebSocket path");
          console.log("📤 About to send WebSocket message", { transactionId, cardIds });
          logger.debug("Sending DogmaV2 WebSocket response", { transactionId, cardIds });
          sendWebSocketMessage({
            type: "dogma_response",
            transaction_id: transactionId,
            selected_cards: cardIds,
          });
          console.log("✅ WebSocket message sent");
        } else {
          // Fallback for any remaining non-v2 interactions (should be rare)
          console.log(
            "⚠️ Multi-card dogma response without transaction ID - using fallback WebSocket path",
          );
          logger.warn(
            "Multi-card dogma response without transaction ID - using fallback WebSocket path",
          );
          sendWebSocketMessage({
            type: "dogma_response",
            selected_cards: cardIds,
          });
          console.log("✅ Fallback WebSocket message sent");
        }
        console.log("🧹 About to clear selected cards");
        logger.debug("Clearing selected cards");
        setMultiSelectedCards([]);
        console.log("✅ Selected cards cleared");
      } catch (error) {
        console.error("💥 Error in main try-catch:", error);
        logger.error("Multi-card dogma response failed:", error);
      }
    },
    [sendWebSocketMessage, multiSelectedCards],
  );

  const handleDeclineDogma = useCallback(
    async (pendingAction) => {
      try {
        // CONSOLIDATION FIX: All decline logic now uses dogma v2 WebSocket system
        // This removes the legacy REST API path and consolidates around v2 architecture
        const transactionId = pendingAction?.context?.transaction_id;

        if (transactionId) {
          // Use v2 WebSocket system with transaction ID
          // Backend expects 'decline: true' AND 'selected_cards: []' for declining optional card selections
          sendWebSocketMessage({
            type: "dogma_response",
            transaction_id: transactionId,
            selected_cards: [],
            decline: true, // CRITICAL: Backend validator checks this flag to set cancelled=True
          });
        } else {
          // Fallback for any remaining non-v2 interactions (should be rare)
          // Still use WebSocket but without transaction_id for backward compatibility
          logger.warn("Decline dogma without transaction ID - using fallback WebSocket path");
          sendWebSocketMessage({
            type: "dogma_response",
            selected_cards: [],
            decline: true, // CRITICAL: Backend validator checks this flag to set cancelled=True
          });
        }
      } catch (error) {
        logger.error("Decline dogma response failed:", error);
      }
    },
    [sendWebSocketMessage],
  );

  const handleSetupSelection = useCallback(
    async (card) => {
      try {
        sendWebSocketMessage({
          type: "setup_selection",
          data: { card_id: card.card_id || card.id },
        });
      } catch (error) {
        logger.error("Setup selection failed:", error);
      }
    },
    [sendWebSocketMessage],
  );

  const handleSelectAction = useCallback((actionType) => {
    setSelectedAction(actionType);
  }, []);

  const handleCardClick = useCallback(
    (card, needsToRespond, pendingAction, isMyTurn, cardLocation) => {
      console.log("🎯 handleCardClick called", {
        card: card?.name || "Unknown",
        cardId: card?.card_id || card?.id,
        cardColor: card?.color,
        needsToRespond,
        pendingAction: pendingAction?.action_type,
        isMyTurn,
        cardLocation,
        context: pendingAction?.context,
      });

      console.log("📊 handleCardClick flow decision:", {
        willSetSelection: !needsToRespond && isMyTurn,
        willHandleDogmaResponse: needsToRespond,
        reason: needsToRespond
          ? "Dogma response mode"
          : isMyTurn
            ? "Normal turn - will set selection"
            : "Not my turn - ignoring",
      });

      // Handle dogma responses first
      if (needsToRespond) {
        // Check if this is a color selection (choose_option with color names)
        const isOptionChoice =
          pendingAction?.type === "choose_option" || pendingAction?.action_type === "choose_option";
        const options = pendingAction?.options || [];
        const validColors = ["red", "blue", "green", "yellow", "purple"];
        const isColorChoice =
          isOptionChoice &&
          options.length > 0 &&
          options.every((opt) => validColors.includes(opt.toLowerCase()));

        if (isColorChoice && card?.color && cardLocation === "board") {
          // Color selection mode - submit the color choice
          const cardColor = card.color.toLowerCase();
          const colorIndex = options.findIndex((opt) => opt.toLowerCase() === cardColor);

          if (colorIndex >= 0) {
            console.log("🎨 Submitting color choice:", { color: cardColor, index: colorIndex });
            handleMultiCardDogmaResponse({ chosen_option: colorIndex }, pendingAction);
            return;
          } else {
            console.log("⚠️ Card color not in eligible colors:", { cardColor, options });
          }
        }

        console.log("📌 Checking card eligibility for dogma response");
        // Phase 1A: Use backend eligible_card_ids for O(1) lookup
        const interactionData = pendingAction?.context?.interaction_data?.data;
        const eligibleCardIds = interactionData?.eligible_card_ids || [];
        const isEligible = eligibleCardIds.includes(card?.card_id);
        console.log("✅ Card eligibility result:", isEligible);

        // Check if card is eligible for the current dogma response
        if (isEligible) {
          const context = pendingAction?.context || {};
          // CRITICAL FIX: Read from interaction_data.data if available (dogma v2 format)
          // Otherwise fall back to context directly (legacy format)
          const interactionData = context.interaction_data?.data || context;
          const maxCount = Number(interactionData.max_count ?? interactionData.count ?? 1);
          const minCount = Number(
            interactionData.min_count ??
              (interactionData.is_optional ? 0 : interactionData.count) ??
              1,
          );
          console.log("📊 Selection counts:", {
            maxCount,
            minCount,
            currentCount: multiSelectedCards.length,
            source: context.interaction_data ? "interaction_data" : "context",
          });

          // Check if this is a multi-card selection
          if (maxCount > 1 || minCount > 1) {
            // Multi-card selection mode
            const isSelected = multiSelectedCards.some((c) => c.name === card.name);
            if (isSelected) {
              // Deselect card
              setMultiSelectedCards((prev) => prev.filter((c) => c.name !== card.name));
            } else if (multiSelectedCards.length < maxCount) {
              // Select card - show visual selection state without auto-submitting
              setMultiSelectedCards((prev) => [...prev, card]);
            }
          } else {
            // Single card selection - immediate response
            handleDogmaResponse(card, pendingAction);
          }
        }
      } else if (isMyTurn) {
        // For the new contextual flow, just select the card and location
        // The ActionsPanel will show contextual buttons based on location
        console.log("✅ Setting card selection:", { card: card?.name, cardLocation });
        setSelectedCard(card);
        setSelectedCardLocation(cardLocation);
        console.log("✅ Card selection state updated");
      } else {
        console.log("⚠️ Card click ignored - not my turn and no dogma response needed");
      }
    },
    [handleDogmaResponse, handleMultiCardDogmaResponse, multiSelectedCards],
  );

  const cancelAction = useCallback(() => {
    setSelectedAction(null);
    setSelectedCard(null);
    setSelectedCardLocation(null);
    setMultiSelectedCards([]);
  }, []);

  const submitMultiCardSelection = useCallback(
    (optionData, pendingAction) => {
      console.log("🔥 [useGameActions] submitMultiCardSelection ENTERED", {
        optionData,
        pendingActionParam: pendingAction?.card_name,
        pendingInteractionProp: pendingInteraction?.card_name,
        multiSelectedCards,
      });
      logger.debug("submitMultiCardSelection called", {
        optionData,
        pendingAction,
        multiSelectedCards,
      });

      // CRITICAL FIX: Use the current pendingInteraction from props instead of the
      // potentially stale pendingAction parameter that might be captured in a closure.
      // This ensures we always use the most up-to-date interaction context.
      const currentPendingAction = pendingInteraction || pendingAction;

      console.log("🔍 [useGameActions] Using pending action:", {
        source: pendingInteraction ? "pendingInteraction (current)" : "pendingAction (parameter)",
        cardName: currentPendingAction?.card_name,
        txId: currentPendingAction?.context?.transaction_id,
      });

      // Simply delegate to handleMultiCardDogmaResponse, which now handles all cases
      // including option choices, multi-card selections, and null/empty selections
      try {
        console.log("🚀 About to call handleMultiCardDogmaResponse");
        handleMultiCardDogmaResponse(optionData, currentPendingAction);
        console.log("✅ handleMultiCardDogmaResponse call completed");
      } catch (error) {
        console.error("💥 Error calling handleMultiCardDogmaResponse:", error);
      }
    },
    [multiSelectedCards, handleMultiCardDogmaResponse, sendWebSocketMessage, pendingInteraction],
  );

  // Add a function to clear multi-card selection state (useful when dogma completes)
  const clearMultiCardSelection = useCallback(() => {
    setMultiSelectedCards([]);
  }, []);

  // Cities expansion: Submit card ordering (Search icon)
  const submitCardOrder = useCallback(
    (orderedCardIds, pendingAction) => {
      logger.debug("submitCardOrder called", {
        orderedCardIds,
        pendingAction,
      });

      const currentPendingAction = pendingInteraction || pendingAction;

      if (!currentPendingAction) {
        logger.error("No pending action for card ordering");
        return;
      }

      const { transaction_id, context } = currentPendingAction;
      if (!transaction_id) {
        logger.error("Missing transaction_id for card ordering");
        return;
      }

      // Send the ordered card IDs response
      const message = {
        action: "dogma_response",
        game_id: currentPendingAction.game_id || context?.game_id,
        transaction_id,
        ordered_card_ids: orderedCardIds,
      };

      logger.info("Sending card order response", { message });
      sendWebSocketMessage(message);
    },
    [sendWebSocketMessage, pendingInteraction],
  );

  return {
    selectedCard,
    selectedCardLocation,
    selectedAction,
    selectedAge,
    setSelectedAge,
    multiSelectedCards,
    handleDraw,
    handleMeld,
    handleDogma,
    handleAchieve,
    handleSelectAction,
    executeSelectedAction,
    handleDogmaResponse,
    handleDeclineDogma,
    handleSetupSelection,
    handleCardClick,
    cancelAction,
    submitMultiCardSelection,
    clearMultiCardSelection,
    submitCardOrder, // Cities: Card ordering for Search icon
    // Unseen expansion: Meld source modal
    meldSourceModalOpen,
    meldSourceModalLoading,
    meldSourceModalError,
    pendingMeldCard,
    handleMeldSourceConfirm,
    handleMeldSourceModalClose,
  };
}

import { useEffect, useCallback, useRef, useState } from "react";

/**
 * Normalize field names with graceful degradation instead of strict enforcement
 * Provides intelligent fallbacks while maintaining functionality and debugging information
 */
function normalizeCardInteractionData(interactionData) {
  if (!interactionData) return interactionData;

  // Create a copy to avoid mutating original
  const normalized = { ...interactionData };

  // CRITICAL: Preserve source_player field for opponent board selection
  // This field is set by the backend to indicate which player's board to select from
  if (interactionData.source_player && !normalized.source_player) {
    normalized.source_player = interactionData.source_player;
  }

  // Backend consistently uses 'eligible_cards' - no legacy fallbacks needed
  if (!normalized.eligible_cards) {
    normalized.eligible_cards = [];
  }

  console.debug("✅ [field-normalization] Processed card interaction data", {
    hasEligibleCards: !!normalized.eligible_cards,
    eligibleCardsCount: normalized.eligible_cards?.length || 0,
    hasSourcePlayer: !!normalized.source_player,
    interactionType: interactionData.type,
  });

  return normalized;
}

/**
 * Enhanced WebSocket hook with exponential backoff, heartbeat, and connection recovery
 */
export function useWebSocketEnhanced({
  gameId,
  playerId,
  token,
  websocket,
  isConnected,
  setWebSocket,
  setConnected,
  setError,
  updateGameState,
  setDogmaResults,
  addActivityEvent,
  WS_BASE,
}) {
  // Connection state
  const [connectionState, setConnectionState] = useState("disconnected"); // disconnected, connecting, connected, reconnecting

  // Enhanced pending action state - persists across game state updates
  const [enhancedPendingAction, setEnhancedPendingAction] = useState(null);

  // Refs for managing connection lifecycle
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef(null);
  const heartbeatIntervalRef = useRef(null);
  const lastPongRef = useRef(Date.now());
  const messageQueueRef = useRef([]);
  const wsRef = useRef(null);

  // Configuration
  const maxReconnectAttempts = 10;
  const baseReconnectDelay = 1000; // Start with 1 second
  const maxReconnectDelay = 30000; // Max 30 seconds
  const heartbeatInterval = 30000; // Send ping every 30 seconds
  const heartbeatTimeout = 300000; // Consider connection dead after 5 minutes without pong

  /**
   * Calculate exponential backoff delay
   */
  const getReconnectDelay = useCallback(() => {
    const delay = Math.min(
      baseReconnectDelay * Math.pow(2, reconnectAttemptsRef.current),
      maxReconnectDelay,
    );
    // Add jitter to prevent thundering herd
    const jitter = Math.random() * 1000;
    return delay + jitter;
  }, []);

  /**
   * Process queued messages after reconnection
   */
  const processMessageQueue = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const queue = [...messageQueueRef.current];
      messageQueueRef.current = [];

      queue.forEach((message) => {
        wsRef.current.send(JSON.stringify(message));
      });
    }
  }, []);

  /**
   * Start heartbeat mechanism
   */
  const startHeartbeat = useCallback(() => {
    // Clear existing interval if any
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }

    // Set up new heartbeat
    heartbeatIntervalRef.current = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        // Check if we've received a pong recently
        const timeSinceLastPong = Date.now() - lastPongRef.current;
        if (timeSinceLastPong > heartbeatTimeout) {
          console.warn("Heartbeat timeout - connection appears dead");
          // Force reconnection
          if (wsRef.current) {
            wsRef.current.close();
          }
          return;
        }

        // Send ping
        const pingMessage = { type: "ping", timestamp: Date.now() };
        wsRef.current.send(JSON.stringify(pingMessage));
      }
    }, heartbeatInterval);
  }, []);

  /**
   * Stop heartbeat mechanism
   */
  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }
  }, []);

  /**
   * Handle incoming WebSocket messages
   */
  const handleWebSocketMessage = useCallback(
    (data) => {
      // DEBUG: Log ALL incoming WebSocket messages
      console.log("🔵 [WebSocket] Received message:", {
        type: data.type,
        hasGameState: !!(data.game_state || data.data?.game_state || data.result?.game_state),
        keys: Object.keys(data),
      });

      // Update last pong time for any message received
      lastPongRef.current = Date.now();

      switch (data.type) {
        case "game_started":
          updateGameState(() => data.game_state);
          break;
        case "player_joined":
          // Update game state when a new player joins
          if (data.game_state) {
            updateGameState(() => data.game_state);
          }
          break;
        case "player_left":
          // Update game state when a player leaves
          if (data.game_state) {
            updateGameState(() => data.game_state);
          }
          break;
        case "action_performed":
          console.log("🎯 [WebSocket] Received action_performed:", {
            success: data.result?.success,
            action: data.result?.action,
            hasGameState: !!data.result?.game_state,
            actionLogLength: data.result?.game_state?.action_log?.length,
          });
          if (!data.result.success) {
            setError(data.result.error || "Action failed");
          } else {
            // Check if this action has dogma results to display
            if (data.result.effects && data.result.effects.length > 0 && setDogmaResults) {
              // Extract the card name from the action or results
              const cardName =
                data.result.card_name ||
                data.result.action ||
                data.result.effects[0]?.card_name ||
                "Card";
              console.log("📊 Displaying dogma results from WebSocket:", {
                cardName,
                resultsCount: data.result.effects.length,
              });
              setDogmaResults(data.result.effects, cardName);
            }

            // Clear enhanced pending action when normal actions complete
            // This handles cases where actions indirectly complete pending dogmas
            if (enhancedPendingAction && !data.result.game_state?.state?.pending_dogma_action) {
              console.log("🧹 Clearing enhanced pending action after action_performed");
              setEnhancedPendingAction(null);
            }

            // Force a new object reference to ensure React detects the change
            const newGameState = JSON.parse(JSON.stringify(data.result.game_state));
            console.log("🔄 [WebSocket] Updating game state with action_log:", {
              entries: newGameState?.action_log?.length,
              lastEntry:
                newGameState?.action_log?.[newGameState.action_log.length - 1]?.description,
            });
            updateGameState(() => newGameState);
          }
          break;
        case "dogma_response":
          console.log("💎 [WebSocket] dogma_response handler triggered:", {
            success: data.result?.success,
            hasGameState: !!data.result?.game_state,
            gameStateKeys: data.result?.game_state ? Object.keys(data.result.game_state) : [],
          });
          if (!data.result.success) {
            console.error("WebSocket dogma_response error:", data.result.error);
            setError(data.result.error || "Dogma response failed");
          } else {
            console.log("💎 [WebSocket] Calling updateGameState from dogma_response");
            // CRITICAL FIX: Force a new object reference to ensure React detects the change
            const newGameState = JSON.parse(JSON.stringify(data.result.game_state));
            updateGameState(() => newGameState);
          }
          break;
        case "setup_selection_made":
          if (data.result && !data.result.success) {
            setError(data.result.error || "Setup selection failed");
          } else {
            updateGameState(() => (data.result ? data.result.game_state : data.game_state));
          }
          break;
        case "pong":
          // Heartbeat response received
          break;
        case "heartbeat":
          // Server heartbeat message - acknowledge but no action needed
          break;
        case "connection_restored":
          // Server acknowledged reconnection - update game state with latest data
          if (data.game_state) {
            console.log("🔄 [connection_restored] Updating game state with action_log:", {
              entries: data.game_state?.action_log?.length,
              hasPlayers: !!data.game_state.players,
              playersCount: data.game_state.players?.length,
            });
            // Use direct state update for reliability during reconnection
            updateGameState(data.game_state);
          } else {
            console.warn("⚠️ [connection_restored] Received without game_state");
          }
          processMessageQueue();
          break;
        case "player_interaction":
          // Handle legacy player_interaction from reconnection logic
          console.debug("Received legacy player_interaction on reconnect", data);

          try {
            // Validate nested structure exists before accessing
            if (!data.interaction_data?.interaction_data) {
              console.error(
                "Invalid player_interaction structure: missing nested interaction_data",
              );
              break;
            }

            const interactionData = data.interaction_data.interaction_data;

            // Extract interaction data from the nested structure
            const cardName = interactionData.card_name;
            if (!cardName) {
              console.error("Invalid player_interaction: missing card_name");
              break;
            }

            // The actual interaction data is stored in interaction_data field
            const actualInteractionData = interactionData.interaction_data;
            const contextData = actualInteractionData || interactionData.data;

            console.debug("Processing reconnection interaction for card:", cardName, contextData);

            // Create a pending action similar to how player_interaction_request does it
            const pendingAction = {
              action_type: "dogma_v2_interaction",
              card_name: cardName,
              target_player_id: data.target_player_id,
              context: contextData || {},
            };

            // Set the enhanced pending action to trigger the UI
            console.log(`🔄 Setting enhanced pending action from reconnect: ${cardName}`);
            setEnhancedPendingAction(pendingAction);

            // Manually update game state since reconnection doesn't include it
            // The game state should already be up to date from the initial connection
            updateGameState((current) => current);
          } catch (error) {
            console.error("Error processing legacy player_interaction:", error, data);
          }
          break;
        case "player_interaction_request":
          // Handle regular player interaction request (e.g., SelectCards for active player)

          if (data.game_state) {
            // Extract interaction data to enhance the game state with correct context
            let interactionData = data.interaction.interaction_data?.data || {};

            // CRITICAL FIX: Normalize field names for consistent frontend handling
            interactionData = normalizeCardInteractionData(interactionData);

            // Check if this is a multi-card selection and enhance the pending action context
            if (
              interactionData.type === "select_cards" ||
              data.interaction.interaction_data?.message?.includes("Choose 3 cards")
            ) {
              // For Tools dogma specifically, ensure we set the correct multi-card constraints
              const maxCount =
                interactionData.max_count ??
                interactionData.selection_count ??
                (data.interaction.interaction_data?.message?.includes("Choose 3 cards") ? 3 : 1);
              const minCount =
                interactionData.min_count ??
                interactionData.selection_count ??
                (data.interaction.interaction_data?.message?.includes("Choose 3 cards") ? 3 : 1);
              const count = interactionData.selection_count ?? interactionData.count ?? maxCount;

              // Create a complete pending action with all required multi-card context
              const pendingAction = {
                action_type: "dogma_v2_interaction",
                card_name: data.interaction.interaction_data?.card_name || "Tools",
                target_player_id: data.interaction.target_player_id,
                context: {
                  transaction_id: data.interaction.transaction_id,
                  max_count: maxCount,
                  min_count: minCount,
                  count: count,
                  is_optional: interactionData.is_optional || false, // Respect backend's is_optional flag
                  eligible_cards: interactionData.eligible_cards || [],
                  selection_source: interactionData.source || "hand",
                  // CRITICAL: Preserve source_player for opponent board selection (Compass card)
                  source_player: interactionData.source_player,
                  // Include the full interaction data for compatibility
                  interaction_data: data.interaction.interaction_data,
                },
              };

              // Store the enhanced pending action in persistent state
              setEnhancedPendingAction(pendingAction);

              // Use functional update to ensure we have the latest state
              updateGameState((prevState) => {
                const enhancedGameState = {
                  ...data.game_state,
                  state: {
                    ...data.game_state.state,
                    pending_dogma_action: pendingAction,
                  },
                };

                return enhancedGameState;
              });
            } else {
              // Use functional update for consistency
              updateGameState(() => data.game_state);
            }
          } else {
            // If no game state provided, ensure the interaction is reflected in current state
            console.log(
              "No game state in player_interaction_request, manually setting pending interaction",
            );

            // Transform DogmaV2 interaction data to frontend format
            const interactionData = data.interaction.interaction_data?.data || {};
            const interactionMessage = data.interaction.interaction_data?.message || "Select cards";

            // Extract card selection constraints from DogmaV2 format
            let context = {
              transaction_id: data.interaction.transaction_id,
              interaction_data: data.interaction.interaction_data,
            };

            // Handle card selection interactions - transform to frontend format
            // Check if this is a card selection interaction
            if (interactionData.type === "select_cards") {
              // Map DogmaV2 constraints to frontend format
              const constraints = interactionData.constraints || {};

              // Extract card count from multiple possible locations in the DogmaV2 format
              const maxCount =
                constraints.max_count ??
                interactionData.max_count ??
                interactionData.selection_count ??
                1;
              const minCount =
                constraints.min_count ??
                interactionData.min_count ??
                interactionData.selection_count ??
                1;
              const count = interactionData.selection_count ?? interactionData.count ?? maxCount;

              context = {
                ...context,
                max_count: maxCount,
                min_count: minCount,
                count: count,
                is_optional: constraints.is_optional || interactionData.is_optional || false,
                // Include normalized card eligibility data
                eligible_cards: normalizeCardInteractionData(interactionData).eligible_cards || [],
                selection_source: interactionData.selection_source || "hand",
                // CRITICAL: Preserve source_player for opponent board selection (Compass card)
                source_player: interactionData.source_player,
              };
            }

            // Force a game state update by creating a minimal state update
            // This ensures the UI shows the interaction even without full game state
            const pendingAction = {
              card_name: data.interaction.interaction_data?.card_name || "Card",
              target_player_id: data.interaction.target_player_id,
              action_type: "dogma_v2_interaction",
              context: context,
            };

            // Use callback approach to merge with existing state
            updateGameState((prevState) => ({
              ...prevState,
              state: {
                ...prevState.state,
                pending_dogma_action: pendingAction,
              },
            }));
          }
          break;
        case "dogma_interaction":
          // Handle unified dogma interaction (new pattern)
          {
            const {
              interaction_type,
              interaction,
              transaction_id,
              game_state,
              target_player_id: rootLevelTarget,
              activating_player_id,
            } = data.data || {};

            console.log("🟣 [WebSocket] dogma_interaction handler triggered:", {
              interactionType: interaction_type,
              hasGameState: !!game_state,
              hasInteraction: !!interaction,
              cardName: interaction?.card_name,
            });
            console.debug(`Received ${interaction_type} dogma_interaction`, data);

            // Build pending action for all players; UI filters via target_player_id
            if (interaction) {
              // Transform interaction data to frontend format
              let interactionData = interaction.data || {};

              // Normalize field names for consistent handling
              interactionData = normalizeCardInteractionData(interactionData);

              // Determine the player that needs to respond to this interaction.
              // Some backend paths do not populate interaction.player_id (legacy demand/sharing
              // behaviour), so fall back to other identifiers before defaulting to the current player.
              const targetPlayerId =
                interaction.player_id ||
                rootLevelTarget ||
                interactionData.player_id ||
                interactionData.target_player_id ||
                activating_player_id ||
                playerId;

              console.log("📋 [dogma_interaction] Normalized interaction data", {
                eligibleCardsCount: interactionData.eligible_cards?.length || 0,
                interactionType: interaction_type,
                targetPlayerId,
              });

              // Create pending action with all required context
              const selCount = interactionData.selection_count ?? interactionData.count;
              const minCount = interactionData.min_count ?? selCount ?? 1;
              const maxCount = interactionData.max_count ?? selCount ?? 1;
              const pendingAction = {
                action_type: "dogma_v2_interaction",
                interaction_type: interaction_type, // "demand", "sharing", or "player"
                card_name: interaction.card_name || "Unknown",
                target_player_id: targetPlayerId,
                context: {
                  transaction_id: transaction_id,
                  max_count: maxCount,
                  min_count: minCount,
                  count: selCount || 1,
                  is_optional: interactionData.is_optional || false,
                  eligible_cards: interactionData.eligible_cards || [],
                  selection_source: interactionData.source || interactionData.location || "hand",
                  message: interaction.message,
                  target_player_id: targetPlayerId,
                  interaction_data: {
                    data: interactionData, // Store the actual interaction data where frontend expects it
                    message: interaction.message,
                    card_name: interaction.card_name,
                    player_id: targetPlayerId,
                  },
                },
              };
              // If this is a choice interaction (e.g., select_color via choose_option),
              // expose fields that ActionsPanel expects for option rendering.
              if (
                interactionData?.type === "choose_option" &&
                Array.isArray(interactionData?.options)
              ) {
                pendingAction.action_type = "choose_option";
                pendingAction.options = interactionData.options;
              }
              // Handle select_color interaction type for color stack clicking
              if (
                interactionData?.type === "select_color" &&
                Array.isArray(interactionData?.available_colors)
              ) {
                pendingAction.action_type = "select_color";
                pendingAction.type = "select_color";
                pendingAction.available_colors = interactionData.available_colors;
              }

              // Store the enhanced pending action for all players
              setEnhancedPendingAction(pendingAction);
            }

            // Always update game state for all players
            if (game_state) {
              console.log("🟣 [WebSocket] Calling updateGameState from dogma_interaction");
              // CRITICAL FIX: Force a new object reference to ensure React detects the change
              const newGameState = JSON.parse(JSON.stringify(game_state));
              updateGameState(() => newGameState);
            }
          }
          break;
        case "game_state_update":
        case "game_state_updated":
          // Handle game state update (sent to non-target players during interactions)
          // Both "game_state_update" and "game_state_updated" are handled identically
          console.log("🟢 [WebSocket] game_state_update handler triggered:", {
            hasGameState: !!data.game_state,
            gameStateKeys: data.game_state ? Object.keys(data.game_state) : [],
            hasPendingDogma: !!data.game_state?.state?.pending_dogma_action,
          });
          if (data.game_state) {
            console.log("🟢 [WebSocket] Calling updateGameState with new game state");
            // CRITICAL FIX: Force a new object reference to ensure React detects the change
            const newGameState = JSON.parse(JSON.stringify(data.game_state));
            updateGameState(() => newGameState);

            // OARS FIX: Check if there's a new pending_dogma_action that needs to be shown
            const pendingDogma = data.game_state.state?.pending_dogma_action;
            if (pendingDogma && pendingDogma.target_player_id === playerId) {
              console.log("🔄 [WebSocket] New pending dogma action detected for this player:", {
                cardName: pendingDogma.card_name,
                actionType: pendingDogma.action_type,
                targetPlayerId: pendingDogma.target_player_id,
              });

              // Extract interaction data from context
              const interactionData = pendingDogma.context?.interaction_data?.data ||
                                     pendingDogma.context?.data ||
                                     pendingDogma.context;

              if (interactionData) {
                // Normalize field names (eligible_cards vs cards)
                if (interactionData.cards && !interactionData.eligible_cards) {
                  interactionData.eligible_cards = interactionData.cards;
                  delete interactionData.cards;
                }

                // Build enhanced pending action similar to dogma_interaction handler
                const selCount = interactionData.selection_count ?? interactionData.count;
                const minCount = interactionData.min_count ?? selCount ?? 1;
                const maxCount = interactionData.max_count ?? selCount ?? 1;

                const pendingAction = {
                  action_type: "dogma_v2_interaction",
                  interaction_type: pendingDogma.action_type,
                  card_name: pendingDogma.card_name || "Unknown",
                  target_player_id: pendingDogma.target_player_id,
                  context: {
                    transaction_id: pendingDogma.context?.transaction_id,
                    max_count: maxCount,
                    min_count: minCount,
                    count: selCount || 1,
                    is_optional: interactionData.is_optional || false,
                    eligible_cards: interactionData.eligible_cards || [],
                    selection_source: interactionData.source || interactionData.location || "hand",
                    message: interactionData.message || pendingDogma.context?.message,
                    target_player_id: pendingDogma.target_player_id,
                    interaction_data: {
                      data: interactionData,
                      message: interactionData.message || pendingDogma.context?.message,
                      card_name: pendingDogma.card_name,
                      player_id: pendingDogma.target_player_id,
                    },
                  },
                };

                // Handle choose_option type
                if (interactionData?.type === "choose_option" && Array.isArray(interactionData?.options)) {
                  pendingAction.action_type = "choose_option";
                  pendingAction.options = interactionData.options;
                }

                console.log("✅ [WebSocket] Setting enhancedPendingAction from game_state_updated");
                setEnhancedPendingAction(pendingAction);
              } else {
                console.warn("🟠 [WebSocket] pending_dogma_action has no interaction data");
              }
            } else if (pendingDogma && pendingDogma.target_player_id !== playerId) {
              console.log("ℹ️ [WebSocket] Pending dogma action is for different player");
            } else if (!pendingDogma && enhancedPendingAction) {
              // No pending dogma action - clear the UI if we had one
              console.log("🧹 [WebSocket] No pending dogma - clearing enhancedPendingAction");
              setEnhancedPendingAction(null);
            }
          } else {
            console.warn("🟠 [WebSocket] game_state_update received but no game_state in data");
          }
          break;
        // Old interaction handlers removed - now using unified dogma_interaction
        case "dogma_response_processed":
          // Handle dogma response processing result - generic for all dogma interactions
          console.log("🎯 Received dogma_response_processed", {
            type: data.type,
            result: data.result,
            hasGameState: !!data.result?.game_state,
            pendingDogmaInResult: !!data.result?.game_state?.state?.pending_dogma_action,
            enhancedPendingAction: enhancedPendingAction,
            results: data.result?.results,
          });

          if (data.result) {
            if (!data.result.success) {
              console.error("WebSocket dogma_response_processed error:", data.result.error);
              setError(data.result.error || "Dogma response processing failed");
              // CRITICAL FIX: Clear the pending interaction UI when there's an error
              // Otherwise the frontend stays sarchive showing stale interaction UI
              console.log("🧹 Clearing enhanced pending action due to error");
              setEnhancedPendingAction(null);
            } else {
              // Successfully processed - clear pending actions immediately and update game state
              console.log("✅ Dogma response processed successfully");

              // CRITICAL FIX: Only clear enhanced pending action if:
              // 1. The new game state has no pending_dogma_action (interaction complete for all players)
              // 2. OR this player just submitted their response (they're no longer the target)
              const shouldClearPending =
                !data.result.game_state?.state?.pending_dogma_action ||
                data.result.game_state?.state?.pending_dogma_action?.target_player_id !== playerId;

              if (shouldClearPending) {
                console.log("🧹 Clearing enhanced pending action - dogma processing complete");
                setEnhancedPendingAction(null);
              } else {
                console.log(
                  "⏳ Keeping enhanced pending action - other player's response, this player still needs to respond",
                );
              }

              if (data.result.game_state) {
                const newGameState = data.result.game_state;

                console.log("🔄 State transition:", {
                  newHandCount:
                    newGameState?.players?.find((p) => p.id === playerId)?.hand?.length || 0,
                  isDogmaComplete: !newGameState.state?.pending_dogma_action,
                  pendingAction: newGameState.state?.pending_dogma_action?.card_name,
                });

                // Extract dogma results and card name if available
                if (data.result.results && data.result.results.length > 0) {
                  const cardName =
                    enhancedPendingAction?.card_name || data.result.card_name || "Card";

                  console.log("🎯 Setting dogma results:", {
                    resultsCount: data.result.results.length,
                    cardName: cardName,
                    results: data.result.results,
                  });

                  setDogmaResults(data.result.results, cardName);
                }

                // CRITICAL FIX: Only clear pending_dogma_action if we should clear the UI
                // Otherwise, preserve it so the UI stays visible for the target player
                const cleanedGameState = shouldClearPending
                  ? {
                      ...newGameState,
                      state: {
                        ...newGameState.state,
                        pending_dogma_action: null,
                      },
                    }
                  : newGameState;

                // Update game state with cleaned state - use direct assignment for immediate effect
                updateGameState(cleanedGameState);
              } else {
                // Handle case where dogma completed but no new game state provided
                // Clear pending actions to restore UI responsiveness
                console.log(
                  "⚠️ Dogma response processed but no game state provided, clearing pending actions",
                );
                updateGameState((prevState) => ({
                  ...prevState,
                  state: {
                    ...prevState.state,
                    pending_dogma_action: null,
                  },
                }));
              }
            }
          } else {
            console.error("🚫 dogma_response_processed received without result", data);
          }
          break;
        case "activity_event":
          // Handle activity events from the backend for display in activity log
          try {
            const event = data.data || {};
            // Basic normalization
            const normalized = {
              timestamp: event.timestamp || new Date().toISOString(),
              type: event.event_type || "activity",
              game_id: event.game_id || null,
              player_id: event.player_id || null,
              message: event.message || "",
              data: event.data || event, // preserve fields for rendering
            };

            // SPECIAL HANDLING: Convert dogma_interaction_required into enhanced pending action
            if (event.event_type === "dogma_interaction_required" && event.data) {
              const interactionData = event.data;
              console.log(
                "🔄 Converting dogma_interaction_required activity to enhancedPendingAction:",
                interactionData,
              );

              // Build enhanced pending action from activity data
              if (interactionData.interaction) {
                const interaction = interactionData.interaction;
                const interactionDataNormalized = normalizeCardInteractionData(interaction);

                const pendingAction = {
                  action_type: "dogma_v2_interaction",
                  interaction_type: interactionData.interaction_type || "player",
                  card_name: interactionData.card_name || "Unknown",
                  target_player_id: event.player_id, // Use player_id from activity event
                  context: {
                    transaction_id: interactionData.transaction_id,
                    max_count: interactionDataNormalized.max_count ?? 1,
                    min_count: interactionDataNormalized.min_count ?? 1,
                    count: interactionDataNormalized.count ?? 1,
                    is_optional: interactionDataNormalized.is_optional ?? false,
                    eligible_cards: interactionDataNormalized.eligible_cards || [],
                    selection_source:
                      interactionDataNormalized.source ||
                      interactionDataNormalized.location ||
                      "hand",
                    message: interaction.message,
                    target_player_id: event.player_id,
                    interaction_data: {
                      data: interactionDataNormalized,
                      message: interaction.message,
                      card_name: interactionData.card_name,
                      player_id: event.player_id,
                    },
                  },
                };

                console.log("🎮 Setting enhancedPendingAction from activity:", pendingAction);
                setEnhancedPendingAction(pendingAction);
              }
            }

            // SPECIAL HANDLING: Clear enhancedPendingAction when turn resumes after dogma
            if (event.event_type === "player_action" && event.data?.action === "turn_resume") {
              console.log(
                "✅ Clearing enhancedPendingAction - turn resumed after dogma:",
                event.data,
              );
              setEnhancedPendingAction(null);
            }

            // Store in context via update function if available
            if (typeof updateGameState === "function") {
              // We use a dedicated activity adder exposed via GameContext
              // but since hooks don't have access here, we mirror via a custom event
              // Consumers can subscribe or pull from GameContext
            }
            // Attach to window for dev inspection
            if (!window.__activityEvents) window.__activityEvents = [];
            window.__activityEvents.push(normalized);
            // Publish into game context state if setter provided
            if (typeof addActivityEvent === "function") addActivityEvent(normalized);

            // Handle game_ended: force a game state refresh so victory banner shows
            if (event.event_type === "game_ended") {
              console.log("🏆 [WebSocket] Game ended! Fetching final state...");
              // Send sync request to get the final game state with phase=finished and winner
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "sync_request" }));
              }
            }
          } catch (e) {
            console.error("Failed to handle activity_event", e);
          }
          break;
        case "error":
          setError(data.message || "Server error");
          break;
        default:
          console.warn("⚠️ [WebSocket] Unknown message type:", data.type);
          console.warn("⚠️ [WebSocket] Full message data:", JSON.stringify(data, null, 2));
          if (data.type && data.type.includes("interaction")) {
            console.error("🚨 MISSED INTERACTION MESSAGE:", JSON.stringify(data, null, 2));
          }
      }
    },
    [
      updateGameState,
      setError,
      processMessageQueue,
      enhancedPendingAction,
      setDogmaResults,
      playerId,
    ],
  );

  /**
   * Connect to WebSocket with enhanced error handling
   */
  const connectWebSocket = useCallback(() => {
    // Don't connect if already connected or connecting
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.CONNECTING ||
        wsRef.current.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    if (!gameId || !playerId || !token) {
      return;
    }

    setConnectionState("connecting");

    // Include token and reconnection flag in query parameters
    const isReconnection = reconnectAttemptsRef.current > 0;
    const wsUrl = `${WS_BASE}/ws/${gameId}/${playerId}?token=${encodeURIComponent(
      token,
    )}&reconnect=${isReconnection}`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState("connected");
        setConnected(true);
        reconnectAttemptsRef.current = 0;
        lastPongRef.current = Date.now();

        // Start heartbeat
        startHeartbeat();

        // Process any queued messages
        processMessageQueue();

        // CRITICAL: Always sync game state on connection, not just reconnection
        // After a page refresh, we need to sync even though isReconnection is false
        console.log("🔄 WebSocket connected - syncing game state", {
          hasGameId: !!gameId,
          hasPlayerId: !!playerId,
          gameId,
          playerId,
          isReconnection,
        });

        // Only attempt sync if we have valid IDs
        if (!gameId) {
          console.warn("⚠️ Cannot sync on connection: gameId is undefined");
          console.warn("⚠️ This usually means the connection happened before session loaded");
          // The session manager will handle loading the game once the session is restored
          return;
        }

        // Primary: Send WebSocket sync request
        ws.send(
          JSON.stringify({
            type: "sync_request",
            player_id: playerId,
          }),
        );

        // Fallback: Also fetch via HTTP to ensure we get latest state
        // This handles cases where WebSocket sync fails or is delayed
        setTimeout(async () => {
          try {
            console.log("🔄 Fetching game state via HTTP fallback for game:", gameId);
            const response = await fetch(`${process.env.REACT_APP_API_BASE || 'http://localhost:8000'}/api/v1/games/${gameId}`);
            if (response.ok) {
              const gameState = await response.json();
              console.log("✅ HTTP fallback successful, updating game state", {
                turn: gameState.state?.turn_number,
                phase: gameState.phase,
                players: gameState.players?.length,
              });
              updateGameState(gameState);
            } else {
              console.warn("⚠️ HTTP fallback failed:", response.status);
            }
          } catch (error) {
            console.error("❌ HTTP fallback error:", error);
          }
        }, 500); // Wait 500ms to give WebSocket sync a chance first
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleWebSocketMessage(data);
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      ws.onclose = (event) => {
        wsRef.current = null;
        setConnected(false);
        stopHeartbeat();

        // Handle different close codes
        if (event.code === 1000) {
          // Normal closure
          setConnectionState("disconnected");
        } else if (event.code === 1006) {
          // Abnormal closure - network issue
          setConnectionState("reconnecting");
          attemptReconnection();
        } else if (event.code === 1008) {
          // Policy violation
          setError("Connection rejected by server");
          setConnectionState("disconnected");
        } else if (event.code === 1011) {
          // Server error
          setError("Server error - please try again");
          setConnectionState("reconnecting");
          attemptReconnection();
        } else if (gameId && reconnectAttemptsRef.current < maxReconnectAttempts) {
          // Other errors - attempt reconnection
          setConnectionState("reconnecting");
          attemptReconnection();
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setError("Failed to reconnect after multiple attempts");
          setConnectionState("disconnected");
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        // Don't set error state here - let onclose handle it
      };

      setWebSocket(ws);
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      setError("Failed to connect to game server");
      setConnectionState("disconnected");
    }
  }, [gameId, playerId, token, WS_BASE]);

  /**
   * Attempt reconnection with exponential backoff
   */
  const attemptReconnection = useCallback(() => {
    if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
      setError("Unable to reconnect to game server");
      setConnectionState("disconnected");
      return;
    }

    reconnectAttemptsRef.current++;
    const delay = getReconnectDelay();

    reconnectTimeoutRef.current = setTimeout(() => {
      connectWebSocket();
    }, delay);
  }, [connectWebSocket, getReconnectDelay, setError]);

  /**
   * Send message with queuing support
   */
  const sendWebSocketMessage = useCallback(
    (message) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        try {
          wsRef.current.send(JSON.stringify(message));
        } catch (error) {
          // Send failed - connection is dead but hasn't been detected yet
          console.error("Failed to send WebSocket message, forcing reconnection:", error);
          messageQueueRef.current.push(message);
          // Force close to trigger reconnection
          if (wsRef.current) {
            wsRef.current.close();
          }
          connectWebSocket();
        }
      } else {
        // Queue message for sending after reconnection
        console.warn("WebSocket not open, queuing message:", message.type);
        messageQueueRef.current.push(message);

        // Attempt to reconnect if disconnected or connecting failed
        if (connectionState !== "connecting") {
          console.log("Forcing reconnection to send queued message");
          connectWebSocket();
        }
      }
    },
    [connectionState, connectWebSocket],
  );

  /**
   * Cleanup all WebSocket-related state
   */
  const cleanupWebSocketState = useCallback(() => {
    console.log("🧹 Cleaning up WebSocket enhanced state");
    setEnhancedPendingAction(null);
    setConnectionState("disconnected");
    messageQueueRef.current = [];
    reconnectAttemptsRef.current = 0;
    lastPongRef.current = null;

    // Clear any pending heartbeat timers
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    // Close WebSocket if open
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close(1000, "Cleanup");
      wsRef.current = null;
    }
  }, []);

  /**
   * Manual reconnection trigger
   */
  const reconnectWebSocket = useCallback(() => {
    // Reset reconnection attempts
    reconnectAttemptsRef.current = 0;

    // Close existing connection if any
    if (wsRef.current) {
      wsRef.current.close(1000, "Manual reconnection");
    }

    // Clear any pending reconnection timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    // Attempt connection
    connectWebSocket();
  }, [connectWebSocket]);

  /**
   * Initialize WebSocket connection
   */
  useEffect(() => {
    connectWebSocket();

    // Cleanup function
    return () => {
      // Clear timeouts and intervals
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      stopHeartbeat();

      // Close WebSocket connection
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, "Component unmounting");
      }

      // Clear message queue
      messageQueueRef.current = [];
    };
  }, [connectWebSocket]); // Re-run when connectWebSocket changes (which depends on gameId, playerId, token)

  return {
    sendWebSocketMessage,
    reconnectWebSocket,
    connectionState,
    isConnected: connectionState === "connected",
    enhancedPendingAction,
    cleanupWebSocketState,
  };
}

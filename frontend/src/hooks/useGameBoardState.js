/**
 * Custom hook for managing GameBoard state derivations and loading logic
 */
import { useState, useEffect, useMemo, useContext, useRef, useCallback } from "react";
import { useGame, GameContext } from "../context/GameContext";
import { calculateActualDrawAge, playerNeedsToRespond } from "../utils/gameLogic";

export function useGameBoardState() {
  const { gameId, playerId, gameState, error, clearError, isConnected, enhancedPendingAction } =
    useGame();

  // Track previous values for debugging state changes
  const prevPendingRef = useRef();
  const prevNeedsToRespondRef = useRef();

  // Effect to log state changes
  useEffect(() => {
    // CRITICAL FIX: Backend sends pending_interaction, not pending_dogma_action
    const currentPending =
      enhancedPendingAction ||
      gameState?.pending_interaction ||
      gameState?.state?.pending_dogma_action;
    const currentPendingName = currentPending?.card_name;
    const prevPendingName = prevPendingRef.current;

    if (currentPendingName !== prevPendingName) {
      console.log("🔄 [useGameBoardState] Pending dogma action changed:", {
        from: prevPendingName,
        to: currentPendingName,
        enhancedPending: enhancedPendingAction?.card_name,
        gameStatePending: (gameState?.pending_interaction || gameState?.state?.pending_dogma_action)
          ?.card_name,
        timestamp: new Date().toISOString(),
      });
      prevPendingRef.current = currentPendingName;
    }
  }, [
    enhancedPendingAction,
    gameState?.pending_interaction,
    gameState?.state?.pending_dogma_action,
  ]);

  const [loadingTimeout, setLoadingTimeout] = useState(false);

  // AI turn tracking state
  const [aiTurnStartTime, setAiTurnStartTime] = useState(null);
  const [lastAIActionTime, setLastAIActionTime] = useState(null);
  const prevTurnNumberRef = useRef(null);

  // Track when AI turn starts/ends
  useEffect(() => {
    if (!gameState?.players || !gameState?.state) return;

    const currentPlayerData = gameState.players[gameState.state.current_player_index];
    const isAITurn = currentPlayerData?.is_ai && gameState.phase === "playing";
    const turnNumber = gameState.state.turn_number;

    // Detect AI turn start
    if (isAITurn && turnNumber !== prevTurnNumberRef.current) {
      setAiTurnStartTime(Date.now());
      setLastAIActionTime(null);
      console.log("🤖 AI turn started:", { player: currentPlayerData?.name, turnNumber });
    }

    // Detect AI turn end (no longer AI's turn)
    if (!isAITurn && prevTurnNumberRef.current !== null && aiTurnStartTime) {
      setAiTurnStartTime(null);
      console.log("🤖 AI turn ended");
    }

    prevTurnNumberRef.current = turnNumber;
  }, [gameState?.players, gameState?.state?.current_player_index, gameState?.state?.turn_number, gameState?.phase, aiTurnStartTime]);

  // Track when AI action log updates (indicates AI did something)
  useEffect(() => {
    if (!gameState?.action_log || !aiTurnStartTime) return;

    const latestAction = gameState.action_log[gameState.action_log.length - 1];
    if (latestAction) {
      setLastAIActionTime(Date.now());
    }
  }, [gameState?.action_log?.length, aiTurnStartTime]);

  // Handler to retry AI turn
  const handleRetryAITurn = useCallback(async () => {
    if (!gameId) return;

    console.log("🔄 Requesting AI turn retry...");
    try {
      const apiBase = (await import("../utils/config")).getApiBase();
      const response = await fetch(`${apiBase}/api/v1/games/${gameId}/retry-ai-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (response.ok) {
        setAiTurnStartTime(Date.now());
        console.log("✅ AI turn retry requested successfully");
      } else {
        console.error("❌ AI turn retry failed:", await response.text());
      }
    } catch (err) {
      console.error("❌ AI turn retry request error:", err);
    }
  }, [gameId]);

  // Auto-clear errors after 5 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(clearError, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, clearError]);

  // Loading timeout detection
  useEffect(() => {
    if (!gameState || !gameState.players) {
      const timeout = setTimeout(() => {
        setLoadingTimeout(true);
      }, 10000);

      return () => clearTimeout(timeout);
    } else {
      setLoadingTimeout(false);
    }
  }, [gameState]);

  // Derived game state
  const derivedState = useMemo(() => {
    if (!gameState?.players) {
      return {
        currentPlayer: null,
        otherPlayers: [],
        isMyTurn: false,
        playerDrawAge: 1,
        actualDrawAge: 1,
        needsToRespond: false,
        pendingDogmaAction: null,
      };
    }

    const currentPlayer = gameState.players.find((p) => p.id === playerId) || null;
    const otherPlayers = gameState.players.filter((p) => p.id !== playerId) || [];
    const isMyTurn = gameState.current_player && gameState.current_player.id === playerId;

    // Phase 3: Backend always provides computed_state.draw_age
    const playerDrawAge = currentPlayer?.computed_state?.draw_age ?? 1;
    const actualDrawAge = gameState.age_deck_sizes
      ? calculateActualDrawAge(playerDrawAge, gameState.age_deck_sizes)
      : 1;

    // SYNCHRONIZED PENDING ACTION LOGIC: Intelligently merge enhanced and game state versions
    // Enhanced pending action provides better UI context from WebSocket interactions
    // Game state pending action provides server-side consistency
    let pendingDogmaAction = null;

    // CRITICAL FIX: Backend sends pending_interaction, not pending_dogma_action
    const gameStatePending = gameState.pending_interaction || gameState.state?.pending_dogma_action;
    const enhancedPending = enhancedPendingAction;

    // Validation function to check pending action integrity
    const validatePendingAction = (action, source) => {
      if (!action) return { valid: true, issues: [] };

      const issues = [];

      // Check required fields
      if (!action.card_name) issues.push("missing card_name");
      if (!action.action_type) issues.push("missing action_type");
      if (!action.context && !action.target_player_id)
        issues.push("missing context or target_player_id");

      // Check for field name issues
      const context = action.context || {};
      const interactionData = context.interaction_data?.data || context.data || {};

      if (interactionData.type === "select_cards") {
        const hasEligibleCards = !!(interactionData.eligible_cards || context.eligible_cards);
        if (!hasEligibleCards) {
          issues.push("no card eligibility data");
        }
      }

      return { valid: issues.length === 0, issues };
    };

    // Validate both pending actions
    const enhancedValidation = validatePendingAction(enhancedPending, "enhanced");
    const gameStateValidation = validatePendingAction(gameStatePending, "gameState");

    // Smart selection logic with validation and synchronization
    if (enhancedPending && gameStatePending) {
      // Both exist - choose the better one with synchronization checks
      const enhancedCardName = enhancedPending.card_name;
      const gameStateCardName = gameStatePending.card_name;

      if (enhancedCardName === gameStateCardName) {
        // Same card - prefer enhanced for better UI context
        pendingDogmaAction = enhancedPending;
        console.debug("✅ [synchronization] Both pending actions match - using enhanced");
      } else {
        // Different cards - check which is more recent or valid
        console.warn("⚠️ [synchronization] Pending action mismatch:", {
          enhanced: enhancedCardName,
          gameState: gameStateCardName,
          enhancedValid: enhancedValidation.valid,
          gameStateValid: gameStateValidation.valid,
        });

        // Prefer the more valid action, fallback to enhanced for better UI context
        if (enhancedValidation.valid && !gameStateValidation.valid) {
          pendingDogmaAction = enhancedPending;
          console.debug("✅ [synchronization] Using enhanced - better validation");
        } else if (!enhancedValidation.valid && gameStateValidation.valid) {
          pendingDogmaAction = gameStatePending;
          console.debug("✅ [synchronization] Using gameState - better validation");
        } else {
          // Both valid or both invalid - prefer enhanced for UI context
          pendingDogmaAction = enhancedPending;
          console.debug("✅ [synchronization] Using enhanced - better UI context");
        }
      }
    } else if (enhancedPending) {
      // Only enhanced exists
      pendingDogmaAction = enhancedPending;
      console.debug("✅ [synchronization] Using enhanced - only source available");
    } else if (gameStatePending) {
      // Only game state exists
      pendingDogmaAction = gameStatePending;
      console.debug("✅ [synchronization] Using gameState - only source available");
    }

    // Log validation issues for debugging
    if (!enhancedValidation.valid && enhancedPending) {
      console.warn("⚠️ Enhanced pending action validation issues:", enhancedValidation.issues);
    }
    if (!gameStateValidation.valid && gameStatePending) {
      console.warn("⚠️ Game state pending action validation issues:", gameStateValidation.issues);
    }

    const needsToRespond = currentPlayer
      ? playerNeedsToRespond(pendingDogmaAction, playerId, currentPlayer, gameState.players)
      : false;

    // Comprehensive debug logging for state transitions with validation results
    console.debug("📊 [useGameBoardState] State derived:", {
      // Pending action analysis
      gameStatePending: (gameState.pending_interaction || gameState.state?.pending_dogma_action)
        ?.card_name,
      enhancedPending: enhancedPendingAction?.card_name,
      finalPending: pendingDogmaAction?.card_name,
      synchronizationStatus:
        enhancedPending && gameStatePending
          ? enhancedPending.card_name === gameStatePending.card_name
            ? "synchronized"
            : "mismatched"
          : "single-source",

      // Validation results
      validation: {
        enhanced: enhancedValidation,
        gameState: gameStateValidation,
      },

      // Player state
      needsToRespond,
      isMyTurn,
      playerId,

      // Interaction context debugging
      interactionContext: pendingDogmaAction
        ? {
            hasEligibleCards: !!(
              pendingDogmaAction.context?.eligible_cards ||
              pendingDogmaAction.context?.data?.eligible_cards
            ),
            hasSourcePlayer: !!(
              pendingDogmaAction.context?.source_player ||
              pendingDogmaAction.context?.data?.source_player
            ),
            interactionType:
              pendingDogmaAction.context?.interaction_data?.data?.type ||
              pendingDogmaAction.context?.interaction_type,
            targetPlayerId: pendingDogmaAction.target_player_id,
          }
        : null,
    });

    return {
      currentPlayer,
      otherPlayers,
      isMyTurn,
      playerDrawAge,
      actualDrawAge,
      needsToRespond,
      pendingDogmaAction,
    };
  }, [gameState, playerId, enhancedPendingAction]);

  // Loading and error states
  const isLoading = !gameState || !gameState.players;
  const hasValidPlayer = !!derivedState.currentPlayer;

  // Debug loading state
  console.log("🔍 [useGameBoardState] Loading state:", {
    isLoading,
    hasValidPlayer,
    hasGameState: !!gameState,
    hasPlayers: !!gameState?.players,
    playersCount: gameState?.players?.length,
    currentPlayerId: derivedState.currentPlayer?.id,
  });

  // Log needsToRespond changes
  useEffect(() => {
    if (derivedState.needsToRespond !== prevNeedsToRespondRef.current) {
      console.log("📊 [useGameBoardState] needsToRespond changed:", {
        from: prevNeedsToRespondRef.current,
        to: derivedState.needsToRespond,
        pendingAction: derivedState.pendingDogmaAction?.card_name,
        timestamp: new Date().toISOString(),
      });
      prevNeedsToRespondRef.current = derivedState.needsToRespond;
    }
  }, [derivedState.needsToRespond, derivedState.pendingDogmaAction]);

  return {
    // Core game state
    gameId,
    playerId,
    gameState,
    error,
    clearError,
    isConnected,

    // Loading states
    loadingTimeout,
    isLoading,
    hasValidPlayer,

    // AI turn tracking
    aiTurnStartTime,
    lastAIActionTime,
    onRetryAITurn: handleRetryAITurn,

    // Derived state
    ...derivedState,
  };
}

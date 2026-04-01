import { Box, Typography } from "@mui/material";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import { useGame } from "../context/GameContext";
import { useBackendEligibility } from "../hooks/useBackendEligibility";
import { getApiBase } from "../utils/config";
import SymbolCounter from "./SymbolCounter";
import ColorStack from "./board/ColorStack";
import ExpansionZone from "./board/ExpansionZone";
import PlayerHand from "./board/PlayerHand";
import ScorePileSelection from "./board/ScorePileSelection";
import AchieveFromSafeModal from "./game/AchieveFromSafeModal";
import MuseumCollection from "./artifacts/MuseumCollection";
import DisplayZone from "./artifacts/DisplayZone";

const PlayerBoard = memo(
  function PlayerBoard({
    player,
    isCurrentPlayer = false,
    onCardClick,
    showHand = false,
    needsToRespond = false,
    dogmaResponse = null,
    hideBoard = false,
    compareToPlayer = null,
    showSymbolCounter = true,
    compact = false,
  }) {
    // Get current game state to access fresh pendingAction
    const { gameState, sendWebSocketMessage } = useGame();
    const currentPendingAction =
      dogmaResponse?.pendingAction || gameState?.state?.pending_dogma_action;

    // PHASE 1A: Extract backend eligibility metadata using custom hook
    const backendEligibility = useBackendEligibility(currentPendingAction);

    // UNSEEN EXPANSION: Achievement modal state
    const [achieveModalOpen, setAchieveModalOpen] = useState(false);
    const [achievementData, setAchievementData] = useState(null);

    // Fetch achievement data for Safe achievement validation
    useEffect(() => {
      const fetchAchievements = async () => {
        if (!gameState?.game_id || !player?.id || !isCurrentPlayer) {
          return;
        }

        try {
          const API_BASE = getApiBase();
          const url = `${API_BASE}/api/v1/games/${gameState.game_id}/achievements?player_id=${player.id}`;
          const response = await fetch(url);

          if (response.ok) {
            const data = await response.json();
            setAchievementData(data);
          }
        } catch (error) {
          console.error("Error fetching achievement data:", error);
        }
      };

      if (isCurrentPlayer && player?.safe?.card_count > 0) {
        fetchAchievements();
      }
    }, [gameState?.game_id, player?.id, isCurrentPlayer, player?.safe?.card_count]);

    // Check if we're in color selection mode and extract eligible colors
    const { isColorSelectionMode, eligibleColors } = useMemo(() => {
      const pendingAction = currentPendingAction || dogmaResponse?.pendingAction;

      // Check for dogma_v2 interaction format
      const interactionData = pendingAction?.context?.interaction_data?.data;
      const validColors = ["red", "blue", "green", "yellow", "purple"];

      // Check for select_color type (from SelectColor primitive)
      const isSelectColor =
        pendingAction?.type === "select_color" ||
        pendingAction?.action_type === "select_color" ||
        interactionData?.type === "select_color";

      if (isSelectColor) {
        // For select_color, colors are in available_colors field
        const availableColors = interactionData?.available_colors || pendingAction?.available_colors || [];
        const extractedColors = availableColors
          .filter((c) => typeof c === "string" && validColors.includes(c.toLowerCase()))
          .map((c) => c.toLowerCase());
        return {
          isColorSelectionMode: extractedColors.length > 0,
          eligibleColors: extractedColors,
        };
      }

      // Check for choose_option type with color options
      const isOptionChoice =
        pendingAction?.type === "choose_option" ||
        pendingAction?.action_type === "choose_option" ||
        interactionData?.type === "choose_option";

      // Extract options from correct path
      const options = interactionData?.options || pendingAction?.options || [];

      // Extract colors from structured options (backend sends {label, value})
      const extractedColors = options
        .map((opt) => {
          // Backend sends structured: {label: "Splay green cards", value: "green"}
          if (typeof opt === "object" && opt.value && typeof opt.value === "string") {
            const value = opt.value.toLowerCase();
            return validColors.includes(value) ? value : null;
          }
          // Backward compat: simple string options
          if (typeof opt === "string") {
            const lowerOpt = opt.toLowerCase();
            return validColors.includes(lowerOpt) ? lowerOpt : null;
          }
          return null;
        })
        .filter(Boolean);

      const isColorSelection =
        isOptionChoice && extractedColors.length > 0 && extractedColors.length === options.length; // All options must be color-related

      return {
        isColorSelectionMode: isColorSelection,
        eligibleColors: extractedColors,
      };
    }, [currentPendingAction, dogmaResponse]);

    // Memoize color stacks to prevent recreation on each render
    const colorStacks = useMemo(
      () => [
        { color: "blue", cards: player?.board?.blue_cards || [] },
        { color: "red", cards: player?.board?.red_cards || [] },
        { color: "green", cards: player?.board?.green_cards || [] },
        { color: "yellow", cards: player?.board?.yellow_cards || [] },
        { color: "purple", cards: player?.board?.purple_cards || [] },
      ],
      [player?.board],
    );

    // Extract can_activate_dogma with null safety
    const canActivateDogma = useMemo(
      () => player?.computed_state?.can_activate_dogma || [],
      [player?.computed_state?.can_activate_dogma],
    );

    // PHASE 1A: Check card eligibility using backend data (O(1) lookup)
    const isCardEligibleForDogmaResponse = useCallback(
      (card) => {
        // Use the enhanced currentPendingAction if available, fallback to dogmaResponse
        const effectivePendingAction = currentPendingAction || dogmaResponse?.pendingAction;
        if (!effectivePendingAction) {
          return false;
        }

        // PHASE 1A: Use backend eligible_card_ids (no fallback)
        return backendEligibility.eligibleCardIds.includes(card?.card_id);
      },
      [dogmaResponse, currentPendingAction, backendEligibility],
    );

    // PHASE 1A: Check if this board should show clickable cards using backend data
    const shouldShowClickableBoardCards = useMemo(() => {
      const effectivePendingAction = currentPendingAction || dogmaResponse?.pendingAction;
      if (!effectivePendingAction) {
        return false;
      }

      // PHASE 1A: Use backend clickable_player_ids (no fallback)
      return backendEligibility.clickablePlayerIds.includes(player?.id);
    }, [
      currentPendingAction,
      dogmaResponse?.pendingAction,
      isCurrentPlayer,
      backendEligibility,
      player?.id,
    ]);

    // Handle color stack click for color selection interactions
    const handleColorStackClick = useCallback(
      (color) => {
        if (!isColorSelectionMode || !eligibleColors.includes(color) || !needsToRespond) {
          return;
        }

        const pendingAction = currentPendingAction || dogmaResponse?.pendingAction;
        const txId = pendingAction?.context?.transaction_id;

        if (!txId || !sendWebSocketMessage) {
          console.error("❌ Cannot send color selection:", {
            missingTxId: !txId,
            missingSendFunction: !sendWebSocketMessage,
          });
          return;
        }

        // Find the option that matches this color value and extract its label
        const interactionData = pendingAction?.context?.interaction_data?.data;
        const options = interactionData?.options || pendingAction?.options || [];

        // Find the option with matching value field
        const matchingOption = options.find((opt) => {
          if (typeof opt === "object" && opt.value) {
            return opt.value.toLowerCase() === color.toLowerCase();
          }
          // Backward compat: simple string
          if (typeof opt === "string") {
            return opt.toLowerCase() === color.toLowerCase();
          }
          return false;
        });

        // Detect if this is a select_color interaction (vs choose_option)
        const isSelectColorType =
          pendingAction?.type === "select_color" ||
          pendingAction?.action_type === "select_color" ||
          interactionData?.type === "select_color";

        if (isSelectColorType) {
          // For select_color, backend expects selected_color field with the color value
          sendWebSocketMessage({
            type: "dogma_response",
            transaction_id: txId,
            selected_color: color,
          });
        } else {
          // For choose_option, send the label (what user sees) back to backend
          const selectedOption = matchingOption
            ? typeof matchingOption === "object"
              ? matchingOption.label
              : matchingOption
            : color;

          sendWebSocketMessage({
            type: "dogma_response",
            transaction_id: txId,
            selected_option: selectedOption,
          });
        }
      },
      [
        isColorSelectionMode,
        eligibleColors,
        needsToRespond,
        currentPendingAction,
        dogmaResponse,
        sendWebSocketMessage,
      ],
    );

    // UNSEEN EXPANSION: Achievement modal loading state
    const [achieveLoading, setAchieveLoading] = useState(false);
    const [achieveError, setAchieveError] = useState(null);

    // UNSEEN EXPANSION: Handle achieve from Safe confirmation
    const handleAchieveFromSafe = useCallback(
      async (secretIndex, age) => {
        if (!gameState?.game_id || !player?.id) {
          console.error("Cannot achieve from Safe: missing game_id or player_id");
          return;
        }

        setAchieveLoading(true);
        setAchieveError(null);

        try {
          const API_BASE = getApiBase();
          const url = `${API_BASE}/api/v1/games/${gameState.game_id}/actions`;

          const response = await fetch(url, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              player_id: player.id,
              action_type: "achieve",
              source: "safe",
              safe_index: secretIndex,
            }),
          });

          if (response.ok) {
            console.log(`✅ Successfully achieved using secret #${secretIndex} (Age ${age})`);
            setAchieveModalOpen(false); // Close modal on success
          } else {
            const error = await response.json();
            console.error("❌ Failed to achieve from Safe:", error);
            const errorMsg = error.detail || error.error || error.message || "Unknown error";
            setAchieveError(errorMsg);
          }
        } catch (error) {
          console.error("❌ Error achieving from Safe:", error);
          setAchieveError(`Error: ${error.message}`);
        } finally {
          setAchieveLoading(false);
        }
      },
      [gameState?.game_id, player?.id],
    );

    // Calculate available achievements for modal
    const availableAchievementAges = useMemo(() => {
      if (!achievementData?.regular) return [];
      return achievementData.regular.filter((a) => a.available && a.can_claim).map((a) => a.age);
    }, [achievementData]);

    // Early return after all hooks have been called
    if (!player) return null;

    return (
      <Box sx={{ width: "100%" }}>
        {/* Symbol counter above board for current player */}
        {showSymbolCounter && isCurrentPlayer && (
          <Box
            sx={{
              mb: compact ? 1 : 2,
              display: hideBoard ? "none" : "block",
            }}
          >
            <SymbolCounter
              player={player}
              compareToPlayer={compareToPlayer}
              position="above"
              isCurrentPlayer={isCurrentPlayer}
            />
          </Box>
        )}

        <Box
          sx={{
            display: "flex",
            gap: compact ? 0.5 : 1.5,
            flexDirection: compact ? "column" : "row",
            alignItems: "flex-start",
            flexWrap: "wrap",
          }}
        >
          {/* Game Board */}
          <Box sx={{ flex: compact ? "1 1 100%" : "1 1 auto", order: compact ? 2 : 1 }}>
            {!hideBoard ? (
              <Box
                sx={{
                  display: "flex",
                  gap: compact ? 0.5 : 1,
                  flexWrap: "wrap",
                  mb: compact ? 0.5 : 1,
                  justifyContent: compact ? "center" : "flex-start",
                }}
              >
                {colorStacks.map(({ color, cards }) => {
                  const splayDirection = player?.board?.splay_directions?.[color] || null;

                  // Check if this color is eligible for selection
                  const isEligibleForColorSelection =
                    isColorSelectionMode &&
                    eligibleColors.includes(color) &&
                    needsToRespond &&
                    isCurrentPlayer;

                  return (
                    <ColorStack
                      key={color}
                      color={color}
                      cards={cards}
                      splayDirection={splayDirection}
                      isEligibleForColorSelection={isEligibleForColorSelection}
                      onStackClick={handleColorStackClick}
                      onCardClick={onCardClick}
                      isCurrentPlayer={isCurrentPlayer}
                      needsToRespond={needsToRespond}
                      dogmaResponse={dogmaResponse}
                      currentPendingAction={currentPendingAction}
                      isCardEligibleForDogmaResponse={isCardEligibleForDogmaResponse}
                      canActivateDogma={canActivateDogma}
                      shouldShowClickableBoardCards={shouldShowClickableBoardCards}
                      compact={compact}
                    />
                  );
                })}
              </Box>
            ) : (
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: "200px",
                  border: "2px dashed",
                  borderColor: "divider",
                  borderRadius: 2,
                  bgcolor: "background.paper",
                  mb: 2,
                }}
              >
                <Typography color="text.secondary">
                  Waiting for all players to choose their starting cards...
                </Typography>
              </Box>
            )}
          </Box>

          {/* Player Info Sidebar */}
          <Box
            sx={{
              minWidth: compact ? "100%" : "250px",
              maxWidth: compact ? "100%" : "300px",
              order: compact ? 1 : 2,
            }}
          >
            <Box
              sx={{
                display: "flex",
                flexDirection: compact ? "row" : "column",
                gap: compact ? 2 : 2,
                alignItems: compact ? "center" : "flex-start",
                justifyContent: compact ? "space-between" : "flex-start",
                flexWrap: compact ? "wrap" : "nowrap",
              }}
            >
              {/* Player Header */}
              <Box sx={{ flex: compact ? "0 0 auto" : "1 1 auto" }}>
                <Typography
                  variant={compact ? "h6" : "h5"}
                  gutterBottom={!compact}
                  sx={{ mb: compact ? 0.5 : 1 }}
                  color={isCurrentPlayer ? "primary.main" : "text.primary"}
                >
                  {player.name} {isCurrentPlayer && "(You)"}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Score Pile Selection */}
        <ScorePileSelection
          scorePile={player?.score_pile}
          dogmaResponse={dogmaResponse}
          currentPendingAction={currentPendingAction}
          isCardEligibleForDogmaResponse={isCardEligibleForDogmaResponse}
          onCardClick={onCardClick}
          needsToRespond={needsToRespond}
          compact={compact}
          isCurrentPlayer={isCurrentPlayer}
        />

        {/* Symbol counter above hand for other players */}
        {showSymbolCounter && !isCurrentPlayer && !hideBoard && (
          <Box sx={{ mt: compact ? 1 : 2 }}>
            <SymbolCounter
              player={player}
              compareToPlayer={compareToPlayer}
              position="below"
              isCurrentPlayer={isCurrentPlayer}
            />
          </Box>
        )}

        {/* Hand Cards */}
        {showHand && (
          <PlayerHand
            hand={player?.hand}
            isCurrentPlayer={isCurrentPlayer}
            needsToRespond={needsToRespond}
            dogmaResponse={dogmaResponse}
            currentPendingAction={currentPendingAction}
            isCardEligibleForDogmaResponse={isCardEligibleForDogmaResponse}
            onCardClick={onCardClick}
            compact={compact}
            hideBoard={hideBoard}
          />
        )}

        {/* Expansion Zone Indicators */}
        <ExpansionZone
          player={player}
          isCurrentPlayer={isCurrentPlayer}
          onSafeClick={() => setAchieveModalOpen(true)}
          hideBoard={hideBoard}
          compact={compact}
        />

        {/* ARTIFACTS EXPANSION: Display Zone */}
        {player?.display && !hideBoard && (
          <DisplayZone
            artifact={player.display}
            playerName={player.name}
            compact={compact}
          />
        )}

        {/* ARTIFACTS EXPANSION: Museum Collection */}
        {player?.museums !== undefined && !hideBoard && (
          <MuseumCollection
            museums={player.museums || []}
            playerName={player.name}
            isCurrentPlayer={isCurrentPlayer}
            compact={compact}
          />
        )}

        {/* Achieve from Safe Modal - Unseen Expansion */}
        {isCurrentPlayer && player?.safe && (
          <AchieveFromSafeModal
            open={achieveModalOpen}
            onClose={() => {
              setAchieveModalOpen(false);
              setAchieveError(null); // Clear error when closing
            }}
            onConfirm={handleAchieveFromSafe}
            safe={player.safe}
            availableAchievements={availableAchievementAges}
            currentPlayerScore={player.score || 0}
            currentPlayerHighestAge={player.highest_top_card || 0}
            loading={achieveLoading}
            error={achieveError}
          />
        )}
      </Box>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    // Compare deep equality for player object and other props
    const playerChanged =
      prevProps.player?.id !== nextProps.player?.id ||
      prevProps.player?.name !== nextProps.player?.name ||
      prevProps.player?.score !== nextProps.player?.score ||
      prevProps.player?.hand?.length !== nextProps.player?.hand?.length ||
      prevProps.player?.score_pile?.length !== nextProps.player?.score_pile?.length ||
      JSON.stringify(prevProps.player?.board) !== JSON.stringify(nextProps.player?.board) ||
      JSON.stringify(prevProps.player?.score_pile) !==
        JSON.stringify(nextProps.player?.score_pile) ||
      JSON.stringify(prevProps.player?.hand) !== JSON.stringify(nextProps.player?.hand);

    const otherPropsChanged =
      prevProps.isCurrentPlayer !== nextProps.isCurrentPlayer ||
      prevProps.showHand !== nextProps.showHand ||
      prevProps.needsToRespond !== nextProps.needsToRespond ||
      prevProps.hideBoard !== nextProps.hideBoard ||
      prevProps.showSymbolCounter !== nextProps.showSymbolCounter ||
      prevProps.compact !== nextProps.compact ||
      prevProps.onCardClick !== nextProps.onCardClick ||
      JSON.stringify(prevProps.dogmaResponse) !== JSON.stringify(nextProps.dogmaResponse) ||
      JSON.stringify(prevProps.compareToPlayer) !== JSON.stringify(nextProps.compareToPlayer);

    return !playerChanged && !otherPropsChanged;
  },
);

export default PlayerBoard;

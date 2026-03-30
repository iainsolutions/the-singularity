import React, { memo, useEffect, useRef, useLayoutEffect, useMemo, useCallback } from "react";
import {
  Button,
  Box,
  Typography,
  Chip,
  useTheme,
  useMediaQuery,
  Alert,
  Divider,
  Card,
  CardContent,
} from "@mui/material";
import {
  Add as DrawIcon,
  PlayArrow as MeldIcon,
  Psychology as DogmaIcon,
  EmojiEvents as AchieveIcon,
  Warning as WarningIcon,
  Block as DeclineIcon,
  Check as CheckIcon,
  Clear as CancelIcon,
  Undo as UndoIcon,
  Done as CommitIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon,
} from "@mui/icons-material";
import {
  getDogmaResponseMessage,
  canDeclineDogmaResponse,
  getDeclineButtonText,
} from "../../utils/gameLogic";
import { useGame } from "../../context/GameContext";
import EndorseButton from "../EndorseButton";

// Import symbol images for symbol selection
import castleIcon from "../../assets/symbols/castle.png";
import leafIcon from "../../assets/symbols/leaf.png";
import lightbulbIcon from "../../assets/symbols/lightbulb.png";
import crownIcon from "../../assets/symbols/crown.png";
import factoryIcon from "../../assets/symbols/factory.png";
import clockIcon from "../../assets/symbols/clock.png";

// Symbol icon mapping
const SYMBOL_ICONS = {
  castle: castleIcon,
  leaf: leafIcon,
  lightbulb: lightbulbIcon,
  crown: crownIcon,
  factory: factoryIcon,
  clock: clockIcon,
};

function ActionsPanel({
  selectedCard,
  selectedCardLocation,
  playerDrawAge,
  actualDrawAge,
  actionsRemaining,
  canMeld,
  currentPlayer,
  ageDeckSizes,
  achievementCards,
  onDraw,
  onMeld,
  onDogma,
  onAchieve,
  // Dogma response props
  needsToRespond = false,
  pendingDogmaAction = null,
  multiSelectedCards = [],
  onSubmitMultiCard = null,
  onSubmitCardOrder = null, // Cities: Card ordering for Search icon
  onDecline = null,
  onCancelSelection = null,
}) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  // Access transaction state and methods from GameContext
  const {
    currentTransaction,
    undoTransaction,
    commitTransaction,
    clearTransaction,
    sendWebSocketMessage,
  } = useGame();

  // Ref for the actions panel element - for scrolling
  const actionsPanelRef = useRef(null);

  // Track when UI state changes for debugging
  const prevUIStateRef = useRef();

  useEffect(() => {
    const currentUIState = {
      needsToRespond,
      hasPendingDogma: !!pendingDogmaAction,
      pendingCard: pendingDogmaAction?.card_name,
      showNormalActions: !needsToRespond && !pendingDogmaAction,
      selectedCard: selectedCard?.name,
      selectedLocation: selectedCardLocation,
    };

    const prevUIState = prevUIStateRef.current;
    if (
      !prevUIState ||
      prevUIState.needsToRespond !== currentUIState.needsToRespond ||
      prevUIState.hasPendingDogma !== currentUIState.hasPendingDogma ||
      prevUIState.showNormalActions !== currentUIState.showNormalActions ||
      prevUIState.selectedCard !== currentUIState.selectedCard ||
      prevUIState.selectedLocation !== currentUIState.selectedLocation
    ) {
      console.log("🎭 [ActionsPanel] UI state changed:", {
        previous: prevUIState,
        current: currentUIState,
        timestamp: new Date().toISOString(),
      });

      prevUIStateRef.current = currentUIState;
    }
  }, [needsToRespond, pendingDogmaAction, selectedCard, selectedCardLocation]);

  // Auto-scroll to action panel when dogma response is needed
  useLayoutEffect(() => {
    if (needsToRespond && actionsPanelRef.current) {
      // Use layoutEffect to ensure DOM is updated before scrolling
      // This runs synchronously after all DOM mutations
      actionsPanelRef.current.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [needsToRespond]);

  const getDrawButtonText = () => {
    if (actualDrawAge === null) {
      return isMobile ? "Draw" : "Draw (All ages exhausted)";
    }
    if (playerDrawAge === actualDrawAge) {
      return `Draw (${playerDrawAge})`;
    }
    return isMobile ? `Draw (${actualDrawAge})` : `Draw (${playerDrawAge} → ${actualDrawAge})`;
  };

  // Get eligible achievement ages for the current player - memoized
  // Phase 2: Use backend computed_state.can_achieve (no frontend calculation)
  const eligibleAges = useMemo(() => {
    if (!currentPlayer) {
      return [];
    }

    // Backend provides can_achieve array with eligible age numbers
    return currentPlayer.computed_state?.can_achieve || [];
  }, [currentPlayer?.computed_state?.can_achieve]);

  const getAchieveButtonText = useCallback(() => {
    if (eligibleAges.length === 0) {
      return "Achieve";
    }

    // Show instruction to select an achievement first
    return isMobile ? "Select Achievement" : "Select Achievement";
  }, [eligibleAges, isMobile]);

  const getActionButtonProps = (
    actionType,
    icon,
    color,
    onClick,
    disabled = false,
    show = true,
  ) => {
    if (!show) return null;

    return {
      variant: "outlined",
      size: isMobile ? "small" : "medium",
      startIcon: icon,
      disabled: disabled || actionsRemaining <= 0,
      onClick,
      sx: {
        minWidth: isMobile ? "90px" : "130px",
        height: isMobile ? "36px" : "42px",
        borderColor: color,
        color: color,
        backgroundColor: "transparent",
        borderWidth: "2px",
        fontWeight: 600,
        fontSize: isMobile ? "0.75rem" : "0.875rem",
        "&:hover:not(:disabled)": {
          backgroundColor: `${color}12`,
          borderColor: color,
          transform: "translateY(-2px)",
          boxShadow: `0 6px 20px ${color}30`,
        },
        "&:active:not(:disabled)": {
          transform: "translateY(-1px)",
          boxShadow: `0 4px 12px ${color}40`,
        },
        "&:disabled": {
          transform: "none",
          boxShadow: "none",
          opacity: 0.5,
          cursor: "not-allowed",
        },
        "&:focus-visible": {
          outline: `3px solid ${color}50`,
          outlineOffset: "2px",
        },
        transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
      },
    };
  };

  // Endorse-related state and functions (Cities expansion)
  const { gameState: fullGameState } = useGame();
  const endorseUsedThisTurn = fullGameState?.endorse_used_this_turn || false;
  const citiesEnabled = fullGameState?.expansion_config?.enabled_expansions?.includes('cities') || false;

  // Helper function to get eligible cities for endorse
  const getEligibleCities = useCallback(() => {
    if (!selectedCard || !currentPlayer || selectedCardLocation !== "board") return [];

    const featuredIcon = selectedCard.dogma_resource;
    if (!featuredIcon) return [];

    // Get top cards from all color stacks
    const topCards = [];
    ['blue', 'red', 'green', 'yellow', 'purple'].forEach(color => {
      const stack = currentPlayer.board[`${color}_cards`];
      if (stack && stack.length > 0) {
        const topCard = stack[stack.length - 1];
        // Check if it's a city and has the featured icon
        if (topCard.expansion === 'cities' && topCard.symbols?.includes(featuredIcon)) {
          topCards.push(topCard);
        }
      }
    });

    return topCards;
  }, [selectedCard, currentPlayer, selectedCardLocation]);

  const eligibleCities = useMemo(() => getEligibleCities(), [getEligibleCities]);

  // Create endorse confirm handler
  const handleEndorseConfirm = useCallback((cityId, junkCardId) => {
    console.log('🌟 [ActionsPanel] Endorse confirmed:', { cityId, junkCardId, selectedCard: selectedCard?.name });

    // Call dogma action with endorse parameters
    if (onDogma && selectedCard) {
      onDogma(selectedCard, {
        endorse: true,
        endorse_city_id: cityId,
        endorse_junk_id: junkCardId,
      });
    }
  }, [selectedCard, onDogma]);

  // Determine which buttons to show based on context
  const showMeld = selectedCard && selectedCardLocation === "hand";
  // Don't show dogma button if there's already a pending dogma action
  const showDogma = selectedCard && selectedCardLocation === "board" && !pendingDogmaAction;
  const showDraw = !selectedCard;

  // Debug logging for button visibility
  console.log("🎭 [ActionsPanel] Render decision:", {
    selectedCard: selectedCard?.name,
    selectedLocation: selectedCardLocation,
    showDogmaButton: showDogma,
    showMeldButton: showMeld,
    showDrawButton: showDraw,
    showNormalActions: !needsToRespond && !pendingDogmaAction,
    needsToRespond,
    pendingDogmaAction: pendingDogmaAction?.card_name,
    timestamp: new Date().toISOString(),
  });

  // Only show achieve button if player can achieve any age
  const canAchieve = eligibleAges.length > 0;
  const showAchieve = !selectedCard && canAchieve;

  // console.log("🎮 Action button visibility:", {
  //   showDraw,
  //   showMeld,
  //   showDogma,
  //   showAchieve,
  //   canAchieve,
  //   eligibleAgesCount: eligibleAges.length,
  //   selectedCard: selectedCard?.name,
  //   actionsRemaining
  // });

  // Button handlers - memoized to prevent recreation
  const handleMeld = useCallback(() => {
    if (selectedCard && selectedCardLocation === "hand") {
      onMeld(selectedCard);
    }
  }, [selectedCard, selectedCardLocation, onMeld]);

  const handleDogma = useCallback(() => {
    if (selectedCard && selectedCardLocation === "board") {
      onDogma(selectedCard);
    }
  }, [selectedCard, selectedCardLocation, onDogma]);

  // Transaction handlers
  const handleUndo = useCallback(async () => {
    const result = await undoTransaction();
    if (result && result.success) {
      clearTransaction();
    }
  }, [undoTransaction, clearTransaction]);

  const handleCommit = useCallback(async () => {
    const result = await commitTransaction();
    if (result && result.success) {
      clearTransaction();
    }
  }, [commitTransaction, clearTransaction]);

  // Dogma response logic
  const dogmaMessage = needsToRespond ? getDogmaResponseMessage(pendingDogmaAction) : "";
  const showDeclineButton = needsToRespond ? canDeclineDogmaResponse(pendingDogmaAction) : false;
  const declineButtonText = needsToRespond ? getDeclineButtonText(pendingDogmaAction) : "";

  // Check if this is a multi-card selection
  const context = pendingDogmaAction?.context || {};
  // CRITICAL FIX: Read from interaction_data.data if available (dogma v2 format)
  // Otherwise fall back to context directly (legacy format)
  const interactionData = context.interaction_data?.data || context;
  const maxCount = Number(interactionData.max_count ?? interactionData.count ?? 1);
  const minCount = Number(
    interactionData.min_count ?? (interactionData.is_optional ? 0 : interactionData.count) ?? 1,
  );
  const isMultiCardSelection = maxCount > 1 || minCount > 1;
  const canSubmit = multiSelectedCards.length >= minCount && multiSelectedCards.length <= maxCount;

  // DEBUG: Log button state calculation
  console.log("🔍 [ActionsPanel] Button state:", {
    maxCount,
    minCount,
    isMultiCardSelection,
    multiSelectedCardsLength: multiSelectedCards.length,
    canSubmit,
    interactionData,
    context,
    pendingDogmaAction: pendingDogmaAction?.action_type,
  });

  // Check if this is an option choice
  // CRITICAL FIX: Backend sends interaction_type (not type/action_type) and data.options (not options)
  const isOptionChoice =
    pendingDogmaAction?.context?.interaction_data?.interaction_type === "choose_option" || // dogma_v2 format
    pendingDogmaAction?.interaction_type === "choose_option" ||
    pendingDogmaAction?.data?.type === "choose_option" ||
    pendingDogmaAction?.type === "choose_option" || // Backwards compatibility
    pendingDogmaAction?.action_type === "choose_option"; // Backwards compatibility

  // Use the interactionData already extracted above (line 299)
  const options = interactionData.options || pendingDogmaAction?.options || [];

  console.log("🎨 [ActionsPanel] Options extraction:", {
    options,
    optionsLength: options.length,
    firstOption: options[0],
    interactionDataType: interactionData.type,
  });

  // Check if this is a select_color interaction (new format)
  const isSelectColorInteraction =
    pendingDogmaAction?.action_type === "dogma_v2_interaction" &&
    pendingDogmaAction?.context?.interaction_data?.data?.type === "select_color";
  const selectColorAvailable =
    pendingDogmaAction?.context?.interaction_data?.data?.available_colors || [];

  // Check if this is a color choice (colors sent as choose_option with color names)
  const validColors = ["red", "blue", "green", "yellow", "purple"];
  // Support both simple string options and option objects with value field
  const isColorChoice =
    isOptionChoice &&
    options.length > 0 &&
    options.every((opt) => {
      const optValue = typeof opt === "string" ? opt : opt.value || opt;
      const isValidColor = typeof optValue === "string" && validColors.includes(optValue.toLowerCase());
      console.log("🎨 Checking option:", { opt, optValue, isValidColor });
      return isValidColor;
    });
  const eligibleColors = isSelectColorInteraction
    ? selectColorAvailable
    : isColorChoice
      ? options.map((opt) => (typeof opt === "string" ? opt : opt.value || opt))
      : [];

  console.log("🎨 [ActionsPanel] Color detection:", {
    isColorChoice,
    eligibleColors,
    isSelectColorInteraction,
  });

  // Check if this is a symbol choice (symbols sent as choose_option with symbol names)
  const validSymbols = ["castle", "leaf", "lightbulb", "crown", "factory", "clock"];
  const isSymbolChoice =
    isOptionChoice &&
    options.length > 0 &&
    options.every((opt) => {
      const optValue = typeof opt === "string" ? opt : opt.value || opt;
      return typeof optValue === "string" && validSymbols.includes(optValue.toLowerCase());
    });
  const eligibleSymbols = isSymbolChoice
    ? options.map(opt => typeof opt === "string" ? opt : opt.value || opt)
    : [];

  // Check if this is an achievement selection (matching AchievementRow.js structure)
  const isAchievementSelection =
    pendingDogmaAction?.action_type === "dogma_v2_interaction" &&
    pendingDogmaAction?.context?.interaction_data?.data?.type === "select_achievement";
  const eligibleAchievements =
    pendingDogmaAction?.context?.interaction_data?.data?.eligible_achievements || [];
  const isOptionalAchievement =
    pendingDogmaAction?.context?.interaction_data?.data?.is_optional || false;

  // Check if this is a tiebreaker selection (choosing between tied highest/lowest cards)
  const isTiebreakerSelection =
    pendingDogmaAction?.action_type === "dogma_v2_interaction" &&
    pendingDogmaAction?.context?.interaction_data?.data?.selection_type === "choose_highest_tie";
  const tiebreakerMessage = isTiebreakerSelection
    ? "Multiple cards are tied - choose which one to select"
    : "";

  // Cities expansion: Check if this is a card ordering interaction (Search icon)
  const isCardOrdering =
    pendingDogmaAction?.action_type === "dogma_v2_interaction" &&
    pendingDogmaAction?.context?.interaction_data?.data?.type === "order_cards";
  const cardsToOrder = pendingDogmaAction?.context?.interaction_data?.data?.cards_to_order || [];
  const orderingInstruction = pendingDogmaAction?.context?.interaction_data?.data?.instruction || "Choose the order for these cards";

  // Card ordering state
  const [orderedCards, setOrderedCards] = React.useState([]);

  // Initialize ordered cards when interaction changes
  React.useEffect(() => {
    if (isCardOrdering && cardsToOrder.length > 0) {
      setOrderedCards([...cardsToOrder]);
    }
  }, [isCardOrdering, cardsToOrder]);

  // Move card up in order
  const moveCardUp = (index) => {
    if (index === 0) return;
    const newOrder = [...orderedCards];
    [newOrder[index - 1], newOrder[index]] = [newOrder[index], newOrder[index - 1]];
    setOrderedCards(newOrder);
  };

  // Move card down in order
  const moveCardDown = (index) => {
    if (index === orderedCards.length - 1) return;
    const newOrder = [...orderedCards];
    [newOrder[index], newOrder[index + 1]] = [newOrder[index + 1], newOrder[index]];
    setOrderedCards(newOrder);
  };

  // Submit card order
  const handleSubmitOrder = () => {
    const cardIds = orderedCards.map(card => card.card_id);
    if (onSubmitCardOrder) {
      onSubmitCardOrder(cardIds, pendingDogmaAction);
    }
  };

  // Debug logging for achievement selection
  if (pendingDogmaAction && isAchievementSelection) {
    console.log("🎯 ActionsPanel achievement selection detected:", {
      action_type: pendingDogmaAction.action_type,
      interaction_type: pendingDogmaAction?.context?.interaction_data?.data?.type,
      eligible_achievements: eligibleAchievements,
      eligible_count: eligibleAchievements.length,
      is_optional: isOptionalAchievement,
      achievement_details: eligibleAchievements.map((a) => ({
        id: a.id || a.name,
        name: a.name,
        age: a.age,
      })),
    });
  }

  // Get recent context from execution results if available
  const recentContext = pendingDogmaAction?.execution_results || [];

  return (
    <Box ref={actionsPanelRef} sx={{ width: "100%" }}>
      {/* Dogma Response Section - Compact */}
      {needsToRespond && (
        <Box sx={{ mb: 1 }}>
          <Alert
            severity="warning"
            icon={<WarningIcon />}
            sx={{
              py: 0.5,
              px: 1,
              "& .MuiAlert-icon": {
                py: 0.5,
              },
              "& .MuiAlert-message": {
                width: "100%",
                py: 0.5,
              },
            }}
          >
            <Box sx={{ width: "100%" }}>
              <Typography variant="body2" sx={{ fontWeight: 600, display: "inline", mr: 1 }}>
                Action Required:
              </Typography>
              <Typography variant="body2" sx={{ display: "inline" }}>
                {tiebreakerMessage || dogmaMessage}
              </Typography>
              {tiebreakerMessage && (
                <Typography
                  variant="caption"
                  sx={{ display: "block", mt: 0.5, fontStyle: "italic", color: "text.secondary" }}
                >
                  {dogmaMessage}
                </Typography>
              )}

              {/* Show recent execution context */}
              {recentContext && recentContext.length > 0 && (
                <Box
                  sx={{
                    mt: 1,
                    p: 1,
                    bgcolor: "info.50",
                    borderRadius: 1,
                    border: "1px solid",
                    borderColor: "info.200",
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{ fontWeight: 600, color: "info.dark", display: "block", mb: 0.5 }}
                  >
                    💡 What just happened:
                  </Typography>
                  {recentContext.slice(-4).map((result, idx) => (
                    <Typography
                      key={idx}
                      variant="caption"
                      sx={{ display: "block", color: "text.secondary", ml: 1, fontSize: "0.7rem" }}
                    >
                      • {result}
                    </Typography>
                  ))}
                </Box>
              )}

              {/* Multi-card selection status - Compact inline */}
              {isMultiCardSelection && (
                <Box
                  sx={{
                    mt: 0.5,
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    flexWrap: "wrap",
                  }}
                >
                  <Typography variant="caption" sx={{ fontWeight: 600, color: "primary.main" }}>
                    {multiSelectedCards.length}/
                    {minCount === maxCount ? minCount : `${minCount}-${maxCount}`}
                  </Typography>

                  {/* Selected cards display - inline chips */}
                  {multiSelectedCards.length > 0 &&
                    multiSelectedCards.map((card) => (
                      <Chip
                        key={card.name}
                        label={card.name}
                        color="primary"
                        variant="outlined"
                        size="small"
                        sx={{ height: 20, "& .MuiChip-label": { px: 0.5, fontSize: "0.7rem" } }}
                      />
                    ))}
                </Box>
              )}

              {/* Option choice buttons (but not color or symbol choices) */}
              {isOptionChoice && !isColorChoice && !isSymbolChoice && options.length > 0 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mt: 1 }}>
                  {options.map((option, index) => (
                    <Button
                      key={index}
                      variant="outlined"
                      color="primary"
                      size={isMobile ? "small" : "medium"}
                      onClick={() =>
                        onSubmitMultiCard &&
                        onSubmitMultiCard({ chosen_option: String(option.value || `option_${index}`) }, pendingDogmaAction)
                      }
                      sx={{
                        justifyContent: "flex-start",
                        textAlign: "left",
                        textTransform: "none",
                        "&:hover": {
                          bgcolor: "primary.50",
                          transform: "translateX(4px)",
                          boxShadow: "0 2px 8px rgba(25, 118, 210, 0.3)",
                        },
                        transition: "all 0.2s ease-in-out",
                      }}
                    >
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                          Option {index + 1}:
                        </Typography>
                        <Typography variant="body2">
                          {option.label || option.description || option.value || "Choose this option"}
                        </Typography>
                      </Box>
                    </Button>
                  ))}
                </Box>
              )}

              {/* Color stack click hint - for select_color interactions */}
              {isSelectColorInteraction && selectColorAvailable.length > 0 && (
                <Typography
                  variant="body2"
                  sx={{
                    mt: 1,
                    fontWeight: 600,
                    color: "primary.main",
                    textAlign: "center",
                  }}
                >
                  Click on a {selectColorAvailable.join(" or ")} color stack above
                </Typography>
              )}

              {/* Color choice buttons - ONLY for choose_option colors, NOT select_color (which uses color stack clicks) */}
              {isColorChoice && !isSelectColorInteraction && eligibleColors.length > 0 && (
                <Box
                  role="group"
                  aria-label="Color selection options"
                  sx={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 1,
                    mt: 1,
                    justifyContent: "center",
                  }}
                >
                  {eligibleColors.map((color, index) => {
                    const colorMap = {
                      red: "#d32f2f",
                      blue: "#1976d2",
                      green: "#388e3c",
                      yellow: "#f57c00",
                      purple: "#7b1fa2",
                    };
                    const colorValue = colorMap[color.toLowerCase()] || "#666";

                    return (
                      <Button
                        key={color}
                        variant="outlined"
                        size={isMobile ? "small" : "medium"}
                        aria-label={`Select ${color} color`}
                        onClick={() => {
                          if (isSelectColorInteraction) {
                            // For select_color interactions, send the selected color directly
                            const txId = pendingDogmaAction?.context?.transaction_id;
                            if (txId && sendWebSocketMessage) {
                              console.log("📤 Sending color selection:", {
                                type: "dogma_response",
                                transaction_id: txId,
                                selected_color: color,
                              });
                              sendWebSocketMessage({
                                type: "dogma_response",
                                transaction_id: txId,
                                selected_color: color,
                              });
                            }
                          } else {
                            // For choose_option interactions, send the option value as string
                            onSubmitMultiCard &&
                              onSubmitMultiCard({ chosen_option: String(color || `option_${index}`) }, pendingDogmaAction);
                          }
                        }}
                        sx={{
                          minWidth: isMobile ? "70px" : "100px",
                          borderColor: colorValue,
                          color: colorValue,
                          borderWidth: "2px",
                          fontWeight: 600,
                          textTransform: "capitalize",
                          "&:hover": {
                            bgcolor: `${colorValue}12`,
                            borderColor: colorValue,
                            transform: "translateY(-2px)",
                            boxShadow: `0 4px 12px ${colorValue}40`,
                          },
                          transition: "all 0.2s ease-in-out",
                        }}
                      >
                        {color}
                      </Button>
                    );
                  })}
                </Box>
              )}

              {/* Symbol choice buttons */}
              {isSymbolChoice && eligibleSymbols.length > 0 && (
                <Box
                  role="group"
                  aria-label="Symbol selection options"
                  sx={{
                    display: "flex",
                    flexWrap: "wrap",
                    gap: 1,
                    mt: 1,
                    justifyContent: "center",
                  }}
                >
                  {eligibleSymbols.map((symbol, index) => {
                    const symbolIcon = SYMBOL_ICONS[symbol.toLowerCase()];

                    return (
                      <Button
                        key={symbol}
                        variant="outlined"
                        size={isMobile ? "small" : "medium"}
                        aria-label={`Select ${symbol} symbol`}
                        onClick={() =>
                          onSubmitMultiCard &&
                          onSubmitMultiCard({ chosen_option: String(symbol || `option_${index}`) }, pendingDogmaAction)
                        }
                        sx={{
                          minWidth: isMobile ? "80px" : "110px",
                          borderColor: "primary.main",
                          color: "primary.main",
                          borderWidth: "2px",
                          fontWeight: 600,
                          textTransform: "capitalize",
                          display: "flex",
                          alignItems: "center",
                          gap: 1,
                          "&:hover": {
                            bgcolor: "primary.50",
                            borderColor: "primary.dark",
                            transform: "translateY(-2px)",
                            boxShadow: "0 4px 12px rgba(25, 118, 210, 0.3)",
                          },
                          transition: "all 0.2s ease-in-out",
                        }}
                      >
                        {symbolIcon && (
                          <img
                            src={symbolIcon}
                            alt={symbol}
                            style={{ width: "20px", height: "20px", objectFit: "contain" }}
                          />
                        )}
                        {symbol}
                      </Button>
                    );
                  })}
                </Box>
              )}

              {/* Cities expansion: Card ordering UI (Search icon) */}
              {isCardOrdering && orderedCards.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="body2" sx={{ mb: 1, fontWeight: 600, color: "primary.main", textAlign: "center" }}>
                    {orderingInstruction}
                  </Typography>
                  <Typography variant="caption" sx={{ mb: 2, display: "block", color: "text.secondary", textAlign: "center" }}>
                    Use arrow buttons to arrange cards (top card returned first)
                  </Typography>
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
                    {orderedCards.map((card, index) => (
                      <Card key={card.card_id || card.name} variant="outlined" sx={{ bgcolor: "background.paper" }}>
                        <CardContent sx={{ display: "flex", alignItems: "center", gap: 1.5, p: 1.5, "&:last-child": { pb: 1.5 } }}>
                          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
                            <Button
                              size="small"
                              onClick={() => moveCardUp(index)}
                              disabled={index === 0}
                              sx={{ minWidth: 36, p: 0.5 }}
                              aria-label="Move card up"
                            >
                              <ArrowUpIcon fontSize="small" />
                            </Button>
                            <Button
                              size="small"
                              onClick={() => moveCardDown(index)}
                              disabled={index === orderedCards.length - 1}
                              sx={{ minWidth: 36, p: 0.5 }}
                              aria-label="Move card down"
                            >
                              <ArrowDownIcon fontSize="small" />
                            </Button>
                          </Box>
                          <Box sx={{ flex: 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {index + 1}. {card.name}
                            </Typography>
                            <Typography variant="caption" sx={{ color: "text.secondary" }}>
                              Age {card.age} • {card.color?.charAt(0).toUpperCase() + card.color?.slice(1)}
                            </Typography>
                          </Box>
                        </CardContent>
                      </Card>
                    ))}
                  </Box>
                  <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
                    <Button
                      variant="contained"
                      color="primary"
                      size="large"
                      startIcon={<CheckIcon />}
                      onClick={handleSubmitOrder}
                      sx={{
                        minWidth: 200,
                        "&:hover": {
                          transform: "translateY(-1px)",
                          boxShadow: "0 4px 12px rgba(25, 118, 210, 0.3)",
                        },
                        transition: "all 0.2s ease-in-out",
                      }}
                      aria-label="Confirm card order"
                    >
                      Confirm Order
                    </Button>
                  </Box>
                </Box>
              )}

              {/* Achievement selection buttons */}
              {isAchievementSelection && eligibleAchievements.length > 0 && (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 1, mt: 1 }}>
                  {eligibleAchievements
                    .filter(
                      (achievement) =>
                        achievement && achievement.age && (achievement.id || achievement.name),
                    )
                    .map((achievement) => {
                      const achievementId = achievement.id || achievement.name;
                      const achievementName = achievement.name || achievement.id;
                      const achievementAge = achievement.age;

                      return (
                        <Button
                          key={achievementId}
                          variant="outlined"
                          color="primary"
                          size={isMobile ? "small" : "medium"}
                          onClick={() => {
                            const txId = pendingDogmaAction?.context?.transaction_id;
                            console.log("🎯 Achievement button clicked:", {
                              achievementId,
                              achievementAge,
                              txId,
                              hasSendWebSocketMessage: !!sendWebSocketMessage,
                            });
                            if (txId && sendWebSocketMessage) {
                              console.log("📤 Sending achievement selection:", {
                                type: "dogma_response",
                                transaction_id: txId,
                                selected_achievements: [achievementId],
                              });
                              sendWebSocketMessage({
                                type: "dogma_response",
                                transaction_id: txId,
                                selected_achievements: [achievementId],
                              });
                            } else {
                              console.error("❌ Cannot send achievement selection:", {
                                missingTxId: !txId,
                                missingSendFunction: !sendWebSocketMessage,
                              });
                            }
                          }}
                          sx={{
                            justifyContent: "flex-start",
                            textAlign: "left",
                            textTransform: "none",
                            "&:hover": {
                              bgcolor: "primary.50",
                              transform: "translateX(4px)",
                              boxShadow: "0 2px 8px rgba(25, 118, 210, 0.3)",
                            },
                            transition: "all 0.2s ease-in-out",
                          }}
                        >
                          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              Age {achievementAge}
                            </Typography>
                          </Box>
                        </Button>
                      );
                    })}

                  {/* Skip button for optional achievement selection */}
                  {isOptionalAchievement && (
                    <Button
                      variant="outlined"
                      color="secondary"
                      size={isMobile ? "small" : "medium"}
                      startIcon={<CancelIcon />}
                      onClick={() => {
                        const txId = pendingDogmaAction?.context?.transaction_id;
                        console.log("🎯 Skip achievement button clicked:", {
                          txId,
                          hasSendWebSocketMessage: !!sendWebSocketMessage,
                        });
                        if (txId && sendWebSocketMessage) {
                          console.log("📤 Sending skip achievement selection:", {
                            type: "dogma_response",
                            transaction_id: txId,
                            decline: true,
                          });
                          sendWebSocketMessage({
                            type: "dogma_response",
                            transaction_id: txId,
                            decline: true,
                          });
                        } else {
                          console.error("❌ Cannot send skip selection:", {
                            missingTxId: !txId,
                            missingSendFunction: !sendWebSocketMessage,
                          });
                        }
                      }}
                      sx={{
                        textTransform: "none",
                        "&:hover": {
                          bgcolor: "secondary.50",
                        },
                      }}
                    >
                      Skip (Optional)
                    </Button>
                  )}
                </Box>
              )}

              {/* Action buttons - Compact */}
              <Box sx={{ display: "flex", gap: 1, mt: 0.5, justifyContent: "center" }}>
                {isMultiCardSelection && !isOptionChoice && (
                  <Button
                    variant="contained"
                    color="primary"
                    size={isMobile ? "small" : "medium"}
                    startIcon={<CheckIcon />}
                    onClick={() => {
                      console.log("🔥🔥🔥 [ActionsPanel] Accept button CLICKED!!!", {
                        onSubmitMultiCard: !!onSubmitMultiCard,
                        onSubmitMultiCardType: typeof onSubmitMultiCard,
                        pendingDogmaAction,
                        multiSelectedCards,
                        canSubmit,
                        disabled: !canSubmit,
                      });
                      if (onSubmitMultiCard) {
                        console.log("🚀 Calling onSubmitMultiCard now...");
                        try {
                          onSubmitMultiCard(multiSelectedCards, pendingDogmaAction);
                          console.log("✅ onSubmitMultiCard call completed");
                        } catch (error) {
                          console.error("💥 Error in onSubmitMultiCard:", error);
                        }
                      } else {
                        console.error("❌ onSubmitMultiCard is not available!");
                      }
                    }}
                    disabled={!canSubmit}
                    sx={{
                      minWidth: isMobile ? "auto" : 200,
                      "&:hover:not(:disabled)": {
                        transform: "translateY(-1px)",
                        boxShadow: "0 4px 12px rgba(25, 118, 210, 0.3)",
                      },
                      transition: "all 0.2s ease-in-out",
                    }}
                  >
                    {multiSelectedCards.length === 0
                      ? `Select ${
                          minCount === maxCount ? minCount : `${minCount}-${maxCount}`
                        } Card${minCount !== 1 ? "s" : ""}`
                      : `Accept Selection (${multiSelectedCards.length})`}
                  </Button>
                )}

                {showDeclineButton && (
                  <Button
                    variant="outlined"
                    color="warning"
                    size={isMobile ? "small" : "medium"}
                    startIcon={<DeclineIcon />}
                    onClick={() => onDecline && onDecline(pendingDogmaAction)}
                    sx={{
                      "&:hover": {
                        bgcolor: "warning.50",
                        transform: "translateY(-1px)",
                        boxShadow: "0 4px 12px rgba(255, 152, 0, 0.2)",
                      },
                      transition: "all 0.2s ease-in-out",
                    }}
                  >
                    {declineButtonText}
                  </Button>
                )}
              </Box>
            </Box>
          </Alert>
          <Divider sx={{ mb: 2 }} />
        </Box>
      )}

      {/* Show waiting message when there's a pending dogma but player doesn't need to respond */}
      {!needsToRespond && pendingDogmaAction && (
        <Box sx={{ width: "100%", textAlign: "center", py: 2 }}>
          <Alert severity="info" sx={{ maxWidth: 600, mx: "auto" }}>
            <Typography variant="body2">
              Waiting for opponent to respond to {pendingDogmaAction.card_name || "dogma"}...
            </Typography>
          </Alert>
        </Box>
      )}

      {/* Normal Game Actions Section - Hide when responding to dogma OR when waiting for opponent's response */}
      {(() => {
        const showNormalActions = !needsToRespond && !pendingDogmaAction;
        console.log("🎭 [ActionsPanel] Render decision:", {
          needsToRespond,
          pendingDogmaAction: pendingDogmaAction?.card_name,
          showNormalActions,
          showDogmaButton: showDogma,
          selectedCard: selectedCard?.name,
          selectedLocation: selectedCardLocation,
          timestamp: new Date().toISOString(),
        });
        return showNormalActions;
      })() && (
        <Box
          sx={{
            display: "flex",
            flexDirection: isMobile ? "column" : "row",
            alignItems: "center",
            gap: isMobile ? 1 : 2,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: isMobile ? 1 : 0 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                color: "primary.main",
                display: "flex",
                alignItems: "center",
                gap: 1,
              }}
            >
              Game Actions
              <Chip
                label={`${actionsRemaining} remaining`}
                size="small"
                color={actionsRemaining > 0 ? "primary" : "default"}
                variant="outlined"
              />
            </Typography>
            {selectedCard && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Chip
                  label={`${selectedCard.name} selected`}
                  size="small"
                  color="secondary"
                  variant="filled"
                />
                {onCancelSelection && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    startIcon={<CancelIcon />}
                    onClick={onCancelSelection}
                    sx={{
                      minWidth: "auto",
                      px: 1,
                      fontSize: "0.75rem",
                      "&:hover": {
                        bgcolor: "error.50",
                        transform: "translateY(-1px)",
                        boxShadow: "0 2px 8px rgba(211, 47, 47, 0.2)",
                      },
                      transition: "all 0.2s ease-in-out",
                    }}
                  >
                    {isMobile ? "" : "Cancel"}
                  </Button>
                )}
              </Box>
            )}
          </Box>

          <Box
            sx={{
              display: "flex",
              gap: isMobile ? 1 : 1.5,
              flexWrap: "wrap",
              justifyContent: "center",
              width: "100%",
              maxWidth: isMobile ? "none" : "600px",
              mx: "auto",
            }}
          >
            {showDraw && (
              <Button
                {...getActionButtonProps(
                  "draw",
                  <DrawIcon />,
                  theme.palette.success.main,
                  onDraw,
                  actualDrawAge === null,
                )}
              >
                {getDrawButtonText()}
              </Button>
            )}

            {showMeld && (
              <Button
                {...getActionButtonProps(
                  "meld",
                  <MeldIcon />,
                  theme.palette.info.main,
                  handleMeld,
                  !canMeld,
                )}
              >
                {isMobile ? "Meld" : `Meld ${selectedCard?.name}`}
              </Button>
            )}

            {showDogma && (
              <>
                <Button
                  {...getActionButtonProps(
                    "dogma",
                    <DogmaIcon />,
                    theme.palette.error.main,
                    handleDogma,
                  )}
                >
                  {isMobile ? "Dogma" : `Dogma ${selectedCard?.name}`}
                </Button>

                {/* ENDORSE BUTTON - Cities Expansion */}
                {citiesEnabled && (
                  <EndorseButton
                    dogmaCard={selectedCard}
                    eligibleCities={eligibleCities}
                    playerHand={currentPlayer?.hand || []}
                    endorseUsedThisTurn={endorseUsedThisTurn}
                    citiesEnabled={citiesEnabled}
                    onEndorseConfirm={handleEndorseConfirm}
                  />
                )}
              </>
            )}

            {showAchieve && (
              <Button
                {...getActionButtonProps(
                  "achieve",
                  <AchieveIcon />,
                  theme.palette.warning.main,
                  onAchieve,
                )}
              >
                {getAchieveButtonText()}
              </Button>
            )}
          </Box>

          {/* Transaction Controls - Show when there's an active transaction */}
          {currentTransaction && (
            <Box
              sx={{
                mt: 2,
                pt: 2,
                borderTop: "2px solid",
                borderColor: "divider",
                display: "flex",
                gap: 2,
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                }}
              >
                <Chip label="Transaction Active" size="small" color="info" variant="outlined" />
              </Typography>

              <Button
                variant="outlined"
                size={isMobile ? "small" : "medium"}
                startIcon={<UndoIcon />}
                onClick={handleUndo}
                color="error"
                sx={{
                  minWidth: isMobile ? "90px" : "120px",
                  "&:hover": {
                    bgcolor: "error.50",
                    transform: "translateY(-1px)",
                    boxShadow: "0 4px 12px rgba(211, 47, 47, 0.2)",
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                Undo
              </Button>

              <Button
                variant="contained"
                size={isMobile ? "small" : "medium"}
                startIcon={<CommitIcon />}
                onClick={handleCommit}
                color="success"
                sx={{
                  minWidth: isMobile ? "90px" : "120px",
                  "&:hover": {
                    transform: "translateY(-1px)",
                    boxShadow: "0 4px 12px rgba(46, 125, 50, 0.3)",
                  },
                  transition: "all 0.2s ease-in-out",
                }}
              >
                Commit
              </Button>
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

// Memoize the entire component with a custom comparison function
export default memo(ActionsPanel, (prevProps, nextProps) => {
  // Optimize comparison by checking references first, then deep comparison only when needed
  const quickChecks =
    prevProps.selectedCard === nextProps.selectedCard &&
    prevProps.selectedCardLocation === nextProps.selectedCardLocation &&
    prevProps.playerDrawAge === nextProps.playerDrawAge &&
    prevProps.actualDrawAge === nextProps.actualDrawAge &&
    prevProps.actionsRemaining === nextProps.actionsRemaining &&
    prevProps.canMeld === nextProps.canMeld &&
    prevProps.needsToRespond === nextProps.needsToRespond &&
    prevProps.onDraw === nextProps.onDraw &&
    prevProps.onMeld === nextProps.onMeld &&
    prevProps.onDogma === nextProps.onDogma &&
    prevProps.onAchieve === nextProps.onAchieve &&
    prevProps.onSubmitMultiCard === nextProps.onSubmitMultiCard &&
    prevProps.onSubmitCardOrder === nextProps.onSubmitCardOrder &&
    prevProps.onDecline === nextProps.onDecline &&
    prevProps.onCancelSelection === nextProps.onCancelSelection;

  if (!quickChecks) return false;

  // Deep comparison only for complex objects
  const deepChecks =
    JSON.stringify(prevProps.currentPlayer?.score_pile) ===
      JSON.stringify(nextProps.currentPlayer?.score_pile) &&
    JSON.stringify(prevProps.ageDeckSizes) === JSON.stringify(nextProps.ageDeckSizes) &&
    JSON.stringify(prevProps.pendingDogmaAction) === JSON.stringify(nextProps.pendingDogmaAction) &&
    JSON.stringify(prevProps.multiSelectedCards) === JSON.stringify(nextProps.multiSelectedCards);

  return deepChecks;
});

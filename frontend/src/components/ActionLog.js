import { useState, memo, useMemo, useCallback, useEffect } from "react";
import { Box, Typography, List, ListItem, Chip, Paper, Divider, Popover } from "@mui/material";
import Card from "./Card";
import {
  getAllCardNames,
  getCardColor,
  getCardInfo,
  getFullCardInfo,
  setFullCardDataCache,
  getCardBackgroundColor,
  getCardTextColor,
} from "../data/cardDatabase";
import { fetchCardDatabase } from "../services/cardDataService";

const ActionLog = memo(
  ({ actionLog, gameState }) => {
    const [hoveredCard, setHoveredCard] = useState(null);
    const [cardDataLoaded, setCardDataLoaded] = useState(false);

    // Helper to get player name from player_id
    const getPlayerName = useCallback(
      (playerId) => {
        if (!gameState || !playerId) return "Unknown";
        const player = gameState.players?.find((p) => p.id === playerId);
        return player?.name || "Unknown";
      },
      [gameState],
    );

    // Load full card data from backend on mount
    useEffect(() => {
      fetchCardDatabase()
        .then((cardData) => {
          setFullCardDataCache(cardData);
          setCardDataLoaded(true);
        })
        .catch((error) => {
          // Card database load error - continue with fallback data
          // Continue anyway with fallback data
          setCardDataLoaded(true);
        });
    }, []);

    // Map event types to main game actions (Singularity terminology)
    const getMainAction = useCallback((eventType) => {
      const type = (eventType || "").toLowerCase();

      if (type.includes("action_draw") || type === "draw") return "Research";
      if (type.includes("action_meld") || type === "meld") return "Deploy";
      if (type.includes("action_dogma") || type === "dogma" || type.startsWith("dogma_"))
        return "Execute";
      if (type.includes("action_achieve") || type === "achieve") return "Breakthrough";

      if (type.includes("turn_started")) return "Turn Start";
      if (type.includes("turn_ended")) return "Turn End";
      if (type.includes("game_")) return "Game";
      if (type.includes("player_")) return "Player";

      return "Activity";
    }, []);

    // Memoize sorted entries to prevent unnecessary sorting
    // Transform activity events to match ActionLog display structure
    const sortedEntries = useMemo(() => {
      if (!actionLog || actionLog.length === 0) return [];

      const mapped = [...actionLog].map((entry, originalIndex) => ({
        // Map new activity event structure to old action_log structure
        action_type: getMainAction(entry.type || entry.action_type),
        player_name: entry.player_name || getPlayerName(entry.player_id),
        description: entry.message || entry.description || "",
        turn_number: entry.turn_number ?? 1,
        timestamp: entry.timestamp,
        transaction_id: entry.transaction_id,
        // CRITICAL FIX: Backend sends data.results (array of strings), map to state_changes (array of objects)
        state_changes:
          entry.state_changes || entry.data?.results?.map((msg) => ({ message: msg })) || [],
        originalIndex, // Preserve original order from backend
        // Preserve original data for debugging
        _original: entry,
      }));

      // Sort: reverse chronological by timestamp, but preserve backend order within same transaction
      return mapped.sort((a, b) => {
        // If same transaction, preserve original backend order (which is execution order)
        if (a.transaction_id && b.transaction_id && a.transaction_id === b.transaction_id) {
          return b.originalIndex - a.originalIndex; // Reverse for display (newest first)
        }
        // Different transactions or no transaction_id: sort by timestamp (newest first)
        return new Date(b.timestamp) - new Date(a.timestamp);
      });
    }, [actionLog, gameState, getPlayerName, getMainAction]);

    const [anchorEl, setAnchorEl] = useState(null);
    const popoverOpen = Boolean(anchorEl);

    const handleCardHoverEnter = useCallback(
      (event, cardName) => {
        setAnchorEl(event.currentTarget);

        // Get full card data including symbols and dogma effects
        const fullCard = getFullCardInfo(cardName);
        const cardInfo = getCardInfo(cardName);

        setHoveredCard({
          name: cardName,
          age: fullCard.age || cardInfo.age,
          color: fullCard.color || cardInfo.color,
          card_id: fullCard.card_id || cardInfo.card_id,
          symbols: fullCard.symbols || [],
          dogma_effects: fullCard.dogma_effects || [],
        });
      },
      [cardDataLoaded],
    ); // Depend on cardDataLoaded to refresh when data loads

    const handleCardHoverLeave = useCallback(() => {
      setAnchorEl(null);
      setHoveredCard(null);
    }, []);

    // Memoize parseDescription function to prevent recreation on each render
    const parseDescription = useCallback(
      (description) => {
        const parts = [];
        let lastIndex = 0;
        let match;

        // Create a regex that matches any of the known card names
        const cardNames = getAllCardNames();
        const cardRegex = new RegExp(`\\b(${cardNames.join("|")})\\b`, "g");

        while ((match = cardRegex.exec(description)) !== null) {
          // Add text before the card name
          if (match.index > lastIndex) {
            parts.push(
              <span key={`text-${lastIndex}`}>
                {description.substring(lastIndex, match.index)}
              </span>,
            );
          }

          // Add the card name as a hoverable element with card color
          const cardName = match[1];
          const cardColor = getCardColor(cardName);
          parts.push(
            <span
              key={`card-${match.index}`}
              style={{
                backgroundColor: getCardBackgroundColor(cardColor),
                color: getCardTextColor(cardColor),
                padding: "2px 6px",
                borderRadius: "4px",
                fontWeight: "bold",
                cursor: "pointer",
                display: "inline-block",
                margin: "0 2px",
                border: `1px solid ${getCardTextColor(cardColor)}33`,
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => handleCardHoverEnter(e, cardName)}
              onMouseLeave={handleCardHoverLeave}
            >
              {cardName}
            </span>,
          );

          lastIndex = match.index + match[0].length;
        }

        // Add any remaining text
        if (lastIndex < description.length) {
          parts.push(<span key={`text-${lastIndex}`}>{description.substring(lastIndex)}</span>);
        }

        return parts.length > 0 ? parts : description;
      },
      [handleCardHoverEnter, handleCardHoverLeave],
    );

    // Helper function to get action color
    const getActionColor = useCallback((actionType) => {
      switch (actionType?.toLowerCase()) {
        case "research":
          return "primary";
        case "deploy":
          return "success";
        case "execute":
          return "warning";
        case "breakthrough":
          return "secondary";
        case "turn start":
        case "turn end":
          return "info";
        case "game":
        case "player":
          return "default";
        default:
          return "default";
      }
    }, []);

    // Format structured state_change objects into readable messages
    const formatStateChange = useCallback((change) => {
      // If it already has a message/description, use it
      if (change.message || change.description) {
        return change.message || change.description;
      }

      // Handle structured state_change format from backend
      if (change.change_type && change.data) {
        const { change_type, data } = change;

        switch (change_type) {
          case "symbol_check":
            if (data.meets_requirement === false) {
              return `${data.player} has ${data.count} ${data.symbol} (needs ${data.required_count})`;
            }
            return `${data.player} has ${data.count} ${data.symbol}`;

          case "meld":
            return `${data.player} deployed ${data.card} (${data.color})`;

          case "draw":
            return data.revealed
              ? `${data.player} researched ${data.card} (era ${data.age})`
              : `${data.player} researched a card (era ${data.age})`;

          case "score":
            return `${data.player} harvested ${data.card}`;

          case "splay":
            return `${data.player} proliferated ${data.color} ${data.direction}`;

          case "transfer":
            return `${data.card} transferred from ${data.from_player || data.from_location} to ${
              data.to_player || data.to_location
            }`;

          case "return":
            return `${data.player} recalled ${data.card}`;

          case "tuck":
            return `${data.player} archived ${data.card} to ${data.color}`;

          default:
            // For unknown types, create a readable summary
            const playerInfo = data.player ? `${data.player}: ` : "";
            const cardInfo = data.card ? data.card : "";
            return `${playerInfo}${cardInfo}`.trim() || JSON.stringify(change);
        }
      }

      // Fallback to JSON for unknown formats
      return JSON.stringify(change);
    }, []);

    // Early return after all hooks are defined
    if (!actionLog || actionLog.length === 0) {
      return (
        <Box>
          <Typography variant="h6" gutterBottom sx={{ color: "primary.main" }}>
            Action Log
          </Typography>
          <Paper
            variant="outlined"
            sx={{
              p: 3,
              textAlign: "center",
              bgcolor: "background.default",
              borderStyle: "dashed",
            }}
          >
            <Typography color="text.secondary">No actions yet</Typography>
          </Paper>
        </Box>
      );
    }

    return (
      <Box>
        <Typography variant="h6" gutterBottom sx={{ color: "primary.main" }}>
          Action Log
        </Typography>

        <List
          sx={{
            maxHeight: { lg: "calc(100vh - 200px)" },
            overflow: "auto",
            "& .MuiListItem-root": {
              px: 0,
            },
          }}
        >
          {sortedEntries.map((entry, index) => (
            <ListItem key={index} sx={{ display: "block", py: 1 }}>
              <Paper
                elevation={1}
                sx={{
                  p: 2,
                  bgcolor: "background.paper",
                  border: "1px solid",
                  borderColor: "divider",
                  transition: "all 0.2s ease",
                  "&:hover": {
                    elevation: 2,
                    borderColor: "primary.200",
                  },
                }}
              >
                {/* Header with action type and turn */}
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    mb: 1,
                  }}
                >
                  <Chip
                    label={entry.action_type}
                    color={getActionColor(entry.action_type)}
                    size="small"
                    variant="outlined"
                  />
                  <Chip
                    label={`Turn ${entry.turn_number}`}
                    size="small"
                    variant="filled"
                    sx={{ bgcolor: "text.secondary", color: "white" }}
                  />
                </Box>

                {/* Description */}
                <Typography variant="body2" sx={{ mb: 1, whiteSpace: "pre-wrap" }}>
                  <Box component="span" sx={{ fontWeight: "medium", color: "primary.main" }}>
                    {entry.player_name}
                  </Box>{" "}
                  <Box component="span" sx={{ cursor: "pointer" }}>
                    {parseDescription(entry.description)}
                  </Box>
                </Typography>

                {/* State Changes - Detailed steps */}
                {entry.state_changes && entry.state_changes.length > 0 && (
                  <Box sx={{ ml: 2, mt: 1, mb: 1 }}>
                    {entry.state_changes.map((change, changeIndex) => (
                      <Typography
                        key={changeIndex}
                        variant="caption"
                        sx={{
                          display: "block",
                          color: "text.secondary",
                          fontSize: "0.75rem",
                          lineHeight: 1.5,
                        }}
                      >
                        • {parseDescription(formatStateChange(change))}
                      </Typography>
                    ))}
                  </Box>
                )}

                {/* Timestamp */}
                <Typography variant="caption" color="text.secondary">
                  {new Date(entry.timestamp).toLocaleTimeString()}
                </Typography>
              </Paper>

              {index < sortedEntries.length - 1 && <Divider sx={{ mt: 1, opacity: 0.3 }} />}
            </ListItem>
          ))}
        </List>

        {/* Card Popover */}
        <Popover
          open={popoverOpen}
          anchorEl={anchorEl}
          onClose={handleCardHoverLeave}
          anchorOrigin={{
            vertical: "center",
            horizontal: "left",
          }}
          transformOrigin={{
            vertical: "center",
            horizontal: "right",
          }}
          sx={{
            pointerEvents: "none",
          }}
          slotProps={{
            paper: {
              sx: {
                p: 1,
                boxShadow: 3,
              },
            },
          }}
        >
          {hoveredCard && <Card card={hoveredCard} size="medium" />}
        </Popover>
      </Box>
    );
  },
  (prevProps, nextProps) => {
    // Only re-render if actionLog or relevant gameState properties change
    return (
      JSON.stringify(prevProps.actionLog) === JSON.stringify(nextProps.actionLog) &&
      prevProps.gameState?.turn_number === nextProps.gameState?.turn_number &&
      JSON.stringify(prevProps.gameState?.players?.map((p) => ({ id: p.id, name: p.name }))) ===
        JSON.stringify(nextProps.gameState?.players?.map((p) => ({ id: p.id, name: p.name })))
    );
  },
);

// Card data is now fetched from the backend API on component mount
// and cached for efficient access during the session

export default ActionLog;

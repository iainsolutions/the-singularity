import { memo, useMemo, useState, useEffect } from "react";
import { Box, Typography, Chip } from "@mui/material";
import SafeguardBadge from "./SafeguardBadge";

import styles from "./AchievementRow.module.css";
import { useGame } from "../../context/GameContext";
import { getApiBase } from "../../utils/config";

const AGES = Array.from({ length: 9 }, (_, i) => i + 1);

const ERA_COLORS = {
  1: "#0066CC", 2: "#0066CC",
  3: "#339933", 4: "#339933",
  5: "#CC9900", 6: "#CC9900",
  7: "#7733AA", 8: "#7733AA",
  9: "#CC3333",
};

const SPECIAL_ACHIEVEMENTS = {
  Emergence: { color: "#CC3333", description: "Archive 6+ OR Harvest 6+ in a single turn" },
  Dominion: { color: "#FFD700", description: "3+ of every icon type visible on board" },
  Consciousness: { color: "#4169E1", description: "12+ visible Human Mind icons" },
  Apotheosis: { color: "#9932CC", description: "All 5 colors Proliferated right/up/aslant" },
  Transcendence: { color: "#1E90FF", description: "All 5 colors, each top card Era 8+" },
  Abundance: { color: "#228B22", description: "5+ Harvest cards from different eras" },
};

const AchievementRow = memo(
  function AchievementRow({
    achievements,
    selectedAge,
    onSelectAge,
    isMyTurn,
    currentPlayer,
    ageDeckSizes,
    compact = false,
  }) {
    const { gameState, sendWebSocketMessage } = useGame();
    const pendingAction = gameState?.state?.pending_dogma_action;
    const isSelectAchievementPending = useMemo(() => {
      if (!pendingAction || pendingAction.action_type !== "dogma_v2_interaction") return false;
      const dataType = pendingAction?.context?.interaction_data?.data?.type;
      const isSelectAchievement = dataType === "select_achievement";

      // Debug logging to help troubleshoot
      if (pendingAction) {
        console.log("🎯 AchievementRow pending action check:", {
          action_type: pendingAction.action_type,
          interaction_type: pendingAction.interaction_type,
          dataType: dataType,
          isSelectAchievement: isSelectAchievement,
          context: pendingAction.context,
          eligible_achievements:
            pendingAction?.context?.interaction_data?.data?.eligible_achievements?.length,
        });
      }

      return isSelectAchievement;
    }, [pendingAction]);
    const [imageErrors, setImageErrors] = useState(new Set());
    const [hoveredAchievement, setHoveredAchievement] = useState(null);

    // Backend achievement data (replaces frontend logic)
    const [achievementData, setAchievementData] = useState(null);

    // Build special achievement data from game state
    useEffect(() => {
      if (!gameState) return;

      const available = gameState.special_achievements_available || [];
      const specialData = available.map((name) => ({
        name,
        display_state: "available",
        claimed_by: null,
      }));

      // Check if any player has claimed special achievements
      for (const player of gameState.players || []) {
        for (const ach of player.achievements || []) {
          const achName = ach?.name || ach;
          if (SPECIAL_ACHIEVEMENTS[achName]) {
            const existing = specialData.find((s) => s.name === achName);
            if (existing) {
              existing.display_state =
                player.id === currentPlayer?.id ? "earned_by_you" : "earned_by_other";
              existing.claimed_by = player.name;
            } else {
              specialData.push({
                name: achName,
                display_state:
                  player.id === currentPlayer?.id ? "earned_by_you" : "earned_by_other",
                claimed_by: player.name,
              });
            }
          }
        }
      }

      setAchievementData({ special: specialData });
    }, [gameState?.special_achievements_available, gameState?.players, currentPlayer?.id]);

    // Era-based tile color for achievements
    const getEraColor = (age) => ERA_COLORS[age] || "#666";

    // Use backend data for special achievements (no more frontend logic!)
    const specialAchievements = achievementData?.special || [];
    console.log("🎯 AchievementRow: Rendering with special achievements:", {
      achievementData_is_null: achievementData === null,
      special_count: specialAchievements.length,
      special_achievements: specialAchievements,
    });

    return (
      <Box>
        <Typography
          variant="body2"
          sx={{
            mb: 0.5,
            fontWeight: 600,
            color: "primary.main",
            fontSize: compact ? "0.6rem" : "0.7rem",
            lineHeight: 1,
          }}
        >
          Achievements
        </Typography>

        {/* Single Row: Special Achievements + Regular Achievements */}
        <div className={styles.allAchievementsRow}>
          {/* Special Achievements */}
          <div className={styles.specialAchievementSection}>
            {specialAchievements.map((achievement) => {
              const specialName = achievement.name;
              const specialConfig = SPECIAL_ACHIEVEMENTS[specialName];

              // Backend tells us the display state - no more frontend logic!
              const isEarnedByYou = achievement.display_state === "earned_by_you";
              const isEarnedByOther = achievement.display_state === "earned_by_other";
              const isClaimed = isEarnedByYou || isEarnedByOther;
              const claimedBy = achievement.claimed_by;

              return (
                <div
                  key={specialName}
                  className={`${styles.specialAchievement} ${
                    isClaimed ? styles.specialAchievementEarned : styles.specialAchievementAvailable
                  } ${isEarnedByOther ? styles.specialAchievementClaimedByOther : ""}`}
                  title={`${specialName}: ${specialConfig?.description || ""}${
                    claimedBy ? ` (Earned by ${claimedBy})` : ""
                  }`}
                  onMouseEnter={() => setHoveredAchievement(specialName)}
                  onMouseLeave={() => setHoveredAchievement(null)}
                >
                  <div
                    style={{
                      width: "100%",
                      height: "100%",
                      backgroundColor: specialConfig?.color || "#666",
                      borderRadius: "4px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      overflow: "hidden",
                      opacity: isEarnedByOther ? 0.5 : 1,
                      border: isEarnedByYou
                        ? "2px solid rgba(255, 215, 0, 0.8)"
                        : "2px solid transparent",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "'Orbitron', sans-serif",
                        fontSize: "6px",
                        fontWeight: 700,
                        color: "white",
                        transform: "rotate(-45deg)",
                        whiteSpace: "nowrap",
                        letterSpacing: "0.5px",
                      }}
                    >
                      {specialName}
                    </span>
                  </div>
                  {isClaimed && (
                    <Chip
                      label={claimedBy || "Earned"}
                      size="small"
                      sx={{
                        position: "absolute",
                        bottom: -6,
                        left: "50%",
                        transform: "translateX(-50%)",
                        fontSize: compact ? "0.4rem" : "0.5rem",
                        height: compact ? 12 : 14,
                        background: isEarnedByOther ? "#666" : specialConfig.color,
                        color: "white",
                        fontWeight: 600,
                        zIndex: 1,
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>

          {/* Separator */}
          <div className={styles.achievementSeparator}></div>

          {/* Regular Achievements */}
          <div className={styles.regularAchievementSection}>
            {AGES.map((age) => {
              // Get achievement data from backend (no more frontend logic!)
              const achievementInfo = achievementData?.regular?.find((a) => a.age === age);

              // Backend tells us everything we need to know
              const hasUnclaimed = achievementInfo?.available ?? true; // Default to true if no data yet
              const isEligible = achievementInfo?.can_claim ?? false;
              const displayState = achievementInfo?.display_state || "available";

              // Fallback to old achievements prop for WebSocket interaction handling
              // (This is still needed for the select_achievement interaction)
              const ageAchievements = achievements?.[age];

              const handleClick = () => {
                // If a select_achievement interaction is pending, send WS response instead of normal age select
                if (isSelectAchievementPending && hasUnclaimed) {
                  try {
                    const txId = pendingAction?.context?.transaction_id;
                    // Determine eligible achievements for this age from interaction data when available
                    const eligible =
                      pendingAction?.context?.interaction_data?.data?.eligible_achievements || [];
                    // Find first eligible achievement matching this age
                    let chosenId = null;
                    const match = eligible.find((a) => a.age === age && !a.claimed_by);
                    if (match) {
                      chosenId = match.id || match.name;
                    } else {
                      // Fallback: derive from achievements prop
                      const pool = Array.isArray(ageAchievements)
                        ? ageAchievements
                        : ageAchievements
                          ? [ageAchievements]
                          : [];
                      const firstUnclaimed = pool.find((c) => !c.claimed_by);
                      chosenId = firstUnclaimed?.name || firstUnclaimed?.id || String(age);
                    }
                    if (txId && chosenId) {
                      sendWebSocketMessage({
                        type: "dogma_response",
                        transaction_id: txId,
                        selected_achievements: [chosenId],
                      });
                    }
                  } catch (e) {
                    // noop; UI will remain awaiting selection
                  }
                  return;
                }
                // Default: normal age selection (only when NOT in achievement selection mode)
                if (!isSelectAchievementPending && isMyTurn && hasUnclaimed) onSelectAge(age);
              };

              return (
                <div
                  key={age}
                  className={`${styles.achievementOption} ${
                    selectedAge === age ? styles.achievementOptionSelected : ""
                  } ${!hasUnclaimed ? styles.achievementClaimed : ""} ${
                    isEligible && hasUnclaimed ? styles.achievementEligible : ""
                  }`}
                  onClick={handleClick}
                  title={
                    !hasUnclaimed
                      ? `Age ${age} achievement claimed`
                      : isEligible
                        ? `Age ${age} achievement available (You can achieve this!)`
                        : `Age ${age} achievement available`
                  }
                >
                  {hasUnclaimed ? (
                    <div
                      className={styles.achievementTile}
                      style={{
                        background: `linear-gradient(135deg, #1B2A4A 0%, ${getEraColor(age)}33 100%)`,
                        borderColor: getEraColor(age),
                      }}
                    >
                      <span className={styles.achievementEraNum}>{age}</span>
                    </div>
                  ) : (
                    <div className={styles.achievementEmpty}>
                      <span className={styles.achievementEmptyText}>✓</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Hover tooltip for special achievements */}
        {hoveredAchievement && SPECIAL_ACHIEVEMENTS[hoveredAchievement] && (
          <div className={`${styles.specialAchievementHover} ${styles.visible}`}>
            <div style={{
              padding: "8px",
              background: SPECIAL_ACHIEVEMENTS[hoveredAchievement].color,
              color: "white",
              borderRadius: "6px",
              fontFamily: "'Orbitron', sans-serif",
              fontSize: "11px",
              textAlign: "center",
            }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{hoveredAchievement}</div>
              <div style={{ fontFamily: "'Inter', sans-serif", fontSize: "9px", opacity: 0.9 }}>
                {SPECIAL_ACHIEVEMENTS[hoveredAchievement].description}
              </div>
            </div>
          </div>
        )}
      </Box>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      JSON.stringify(prevProps.achievements) === JSON.stringify(nextProps.achievements) &&
      prevProps.selectedAge === nextProps.selectedAge &&
      prevProps.onSelectAge === nextProps.onSelectAge &&
      prevProps.isMyTurn === nextProps.isMyTurn &&
      JSON.stringify(prevProps.currentPlayer?.score_pile) ===
        JSON.stringify(nextProps.currentPlayer?.score_pile) &&
      JSON.stringify(prevProps.currentPlayer?.achievements) ===
        JSON.stringify(nextProps.currentPlayer?.achievements) &&
      JSON.stringify(prevProps.ageDeckSizes) === JSON.stringify(nextProps.ageDeckSizes) &&
      prevProps.compact === nextProps.compact
    );
  },
);

export default AchievementRow;

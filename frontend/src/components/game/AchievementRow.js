import { memo, useMemo, useState, useEffect } from "react";
import { Box, Typography, Chip } from "@mui/material";
import SafeguardBadge from "./SafeguardBadge";

import styles from "./AchievementRow.module.css";
import { useGame } from "../../context/GameContext";
import { getApiBase } from "../../utils/config";

// Move constants outside component to prevent recreation
const AGES = Array.from({ length: 10 }, (_, i) => i + 1);

// Special achievements with their corresponding PNG images and colors
const SPECIAL_ACHIEVEMENTS = {
  Monument: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements2.png",
    color: "#8B4513",
    description: "At least four top cards with a DEMAND effect",
  },
  Empire: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements3.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements4.png",
    color: "#FFD700",
    description: "At least three icons of each of these six types on your board",
  },
  World: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements5.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements6.png",
    color: "#4169E1",
    description: "At least twelve clock symbols on your board",
  },
  Wonder: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements7.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements8.png",
    color: "#9932CC",
    description: "Five colors splayed on your board, each splayed right, up, or aslant",
  },
  Universe: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements9.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements10.png",
    color: "#1E90FF",
    description: "Five top cards, each of value at least 8",
  },
  Wealth: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements11.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements12.png",
    color: "#228B22",
    description: "At least eight bonuses on your board",
  },
  // Echoes Expansion Special Achievements
  Supremacy: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements15.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements16.png",
    color: "#C41E3A", // Cardinal red
    description: "All non-purple top cards share a common icon (not crown)",
  },
  Destiny: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements13.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements14.png",
    color: "#00CED1", // Dark turquoise
    description: "Return blue cards from your forecast",
  },
  Heritage: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements17.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements18.png",
    color: "#DAA520", // Goldenrod
    description: "At least five crowns on your board in one color",
  },
  History: {
    frontImage: "/cards/Specials/InnoUlt_SpecialAchievements19.png",
    backImage: "/cards/Specials/InnoUlt_SpecialAchievements20.png",
    color: "#8B008B", // Dark magenta
    description: "At least three echo effects in one color",
  },
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

    // Fetch achievement display data from backend
    useEffect(() => {
      const fetchAchievements = async () => {
        if (!gameState?.game_id || !currentPlayer?.id) {
          console.log("🎯 AchievementRow: Skipping fetch - missing game_id or player_id", {
            game_id: gameState?.game_id,
            player_id: currentPlayer?.id,
          });
          return;
        }

        try {
          const API_BASE = getApiBase();
          const url = `${API_BASE}/api/v1/games/${gameState.game_id}/achievements?player_id=${currentPlayer.id}`;
          console.log("🎯 AchievementRow: Fetching achievements from:", url);

          const response = await fetch(url);

          if (response.ok) {
            const data = await response.json();
            console.log("✅ AchievementRow: Received achievement data:", {
              regular_count: data.regular?.length,
              special_count: data.special?.length,
              special_achievements: data.special,
            });
            setAchievementData(data);
          } else {
            console.error("❌ AchievementRow: Failed to fetch achievement data:", response.status);
          }
        } catch (error) {
          console.error("❌ AchievementRow: Error fetching achievement data:", error);
        }
      };

      fetchAchievements();
    }, [gameState?.game_id, currentPlayer?.id, gameState?.players]); // Re-fetch when players change (achievements earned)

    // Get card back image path for the age
    const getCardBackPath = (age) => {
      // Map age to card back image number (1-10 for ages 1-10)
      return `/cards/CardBacks/InnoUlt_CardBacks_PRODUCTION${age}.png`;
    };

    // Fallback image path
    const getFallbackImage = (age) => {
      return `/cards/card_backgrounds/age${age}_background.png`;
    };

    // Handle image load error
    const handleImageError = (age) => {
      setImageErrors((prev) => new Set([...prev, age]));
    };

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
                  <img
                    src={isClaimed ? specialConfig.frontImage : specialConfig.backImage}
                    alt={`${specialName} achievement`}
                    style={{
                      width: "100%",
                      height: "100%",
                      borderRadius: "4px",
                      objectFit: "cover",
                      border: isEarnedByYou
                        ? "2px solid rgba(255, 215, 0, 0.6)"
                        : isEarnedByOther
                          ? "2px solid rgba(128, 128, 128, 0.6)"
                          : "2px solid transparent",
                      filter: isEarnedByOther ? "grayscale(70%) opacity(0.7)" : "none",
                    }}
                    onError={(e) => {
                      // Fallback to solid color block if image fails
                      e.target.style.display = "none";
                      e.target.nextSibling.style.display = "block";
                    }}
                  />
                  <div
                    style={{
                      display: "none",
                      width: "100%",
                      height: "100%",
                      backgroundColor: isClaimed ? specialConfig.color : "#ccc",
                      borderRadius: "4px",
                      transition: "background-color 0.3s ease",
                      border: isEarnedByYou
                        ? "2px solid rgba(255, 215, 0, 0.6)"
                        : isEarnedByOther
                          ? "2px solid rgba(128, 128, 128, 0.6)"
                          : "2px solid transparent",
                      filter: isEarnedByOther ? "grayscale(70%) opacity(0.7)" : "none",
                    }}
                  />
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
                    <>
                      <img
                        src={imageErrors.has(age) ? getFallbackImage(age) : getCardBackPath(age)}
                        alt={`Age ${age} achievement`}
                        className={styles.achievementCardBack}
                        onError={() => handleImageError(age)}
                        loading="lazy"
                      />
                      {/* Safeguard Badge - Unseen Expansion */}
                      {achievementInfo?.safeguard_owners && achievementInfo.safeguard_owners.length > 0 && (
                        <SafeguardBadge
                          achievementAge={age}
                          safeguardOwners={achievementInfo.safeguard_owners}
                          currentPlayerId={currentPlayer?.id}
                          currentPlayerName={currentPlayer?.name}
                          canClaim={achievementInfo.can_claim}
                        />
                      )}
                    </>
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

        {/* Hover overlay for special achievements */}
        {hoveredAchievement && (
          <div className={`${styles.specialAchievementHover} ${styles.visible}`}>
            <img
              src={SPECIAL_ACHIEVEMENTS[hoveredAchievement].frontImage}
              alt={`${hoveredAchievement} achievement large view`}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                borderRadius: "6px",
              }}
            />
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

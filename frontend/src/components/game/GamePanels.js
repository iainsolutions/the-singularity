/**
 * GamePanels - Handles age selector, forecast zone, and achievement row display
 */
import { Paper, Grid } from "@mui/material";
import AgeSelector from "./AgeSelector";
import AchievementRow from "./AchievementRow";
import { useGame } from "../../context/GameContext";

function GamePanels({
  selectedAge,
  setSelectedAge,
  ageDeckSizes,
  citiesDeckSizes,
  echoesDeckSizes,
  figuresDeckSizes,
  artifactsDeckSizes,
  unseenDeckSizes,
  achievementCards,
  junkPile,
  isMyTurn,
  currentPlayer,
  isMobile,
  isTablet,
}) {
  const compact = isMobile || isTablet;
  const { gameState } = useGame();
  const pending = gameState?.state?.pending_dogma_action;
  const isSelectAchievementPending = Boolean(
    pending &&
      pending.action_type === "dogma_v2_interaction" &&
      (pending?.context?.interaction_data?.data?.type === "select_achievement" ||
        pending?.interaction_type === "select_achievement"),
  );

  return (
    <Paper elevation={1} sx={{ mb: 1, p: 1.5 }}>
      <Grid container spacing={{ xs: 1, md: 2 }} alignItems="stretch">
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex", alignItems: "flex-start" }}>
          <AgeSelector
            selectedAge={isSelectAchievementPending ? null : selectedAge}
            ageDeckSizes={ageDeckSizes}
            citiesDeckSizes={citiesDeckSizes}
            echoesDeckSizes={echoesDeckSizes}
            figuresDeckSizes={figuresDeckSizes}
            artifactsDeckSizes={artifactsDeckSizes}
            unseenDeckSizes={unseenDeckSizes}
            onSelectAge={isSelectAchievementPending ? () => {} : setSelectedAge}
            isMyTurn={isMyTurn && !isSelectAchievementPending}
            junkPile={junkPile}
            compact={compact}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex", alignItems: "flex-start" }}>
          <AchievementRow
            achievements={achievementCards}
            selectedAge={isSelectAchievementPending ? null : selectedAge}
            onSelectAge={setSelectedAge}
            isMyTurn={isMyTurn}
            currentPlayer={currentPlayer}
            ageDeckSizes={ageDeckSizes}
            compact={compact}
          />
        </Grid>
      </Grid>
    </Paper>
  );
}

export default GamePanels;

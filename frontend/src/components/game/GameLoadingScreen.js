import { memo } from "react";
import styles from "./GameLoadingScreen.module.css";

const GameLoadingScreen = memo(function GameLoadingScreen({
  loadingTimeout,
  onLeaveGame,
  error,
  gameId,
  playerId,
  isConnected,
  gameState,
}) {
  return (
    <div className={styles.loadingScreen}>
      <div className={styles.loadingScreen__content}>
        <div className={styles.loadingScreen__message}>
          {loadingTimeout ? "Game appears to be stuck loading..." : "Loading game..."}
        </div>

        {loadingTimeout && (
          <div className={styles.loadingScreen__warning}>
            If the game doesn't load, try returning to the lobby and rejoining.
          </div>
        )}

        <div className={styles.loadingScreen__actions}>
          <button onClick={onLeaveGame} className={styles.loadingScreen__returnButton}>
            Return to Lobby
          </button>
        </div>

        {error && <div className={styles.loadingScreen__error}>Error: {error}</div>}

        <div className={styles.loadingScreen__debug}>
          Game ID: {gameId}
          <br />
          Player ID: {playerId}
          <br />
          WebSocket: {isConnected ? "Connected" : "Disconnected"}
          <br />
          Game State: {gameState ? "Partial" : "None"}
        </div>
      </div>
    </div>
  );
});

export default GameLoadingScreen;

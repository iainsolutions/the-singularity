import { memo } from "react";
import Button from "../common/Button";
import styles from "./LobbyActions.module.css";

const LobbyActions = memo(
  function LobbyActions({ canStartGame, onStartGame, onLeaveGame, loading, isWaiting }) {
    return (
      <div className={styles.lobbyActions}>
        <div className={styles["lobbyActions__buttons"]}>
          {canStartGame && (
            <Button variant="primary" onClick={onStartGame} disabled={loading}>
              {loading ? "Starting..." : "Start Game"}
            </Button>
          )}

          <Button variant="secondary" onClick={onLeaveGame}>
            Leave Game
          </Button>
        </div>

        {isWaiting && (
          <p className={styles["lobbyActions__waitingMessage"]}>
            Waiting for more players to join (minimum 2 players required)
          </p>
        )}
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      prevProps.canStartGame === nextProps.canStartGame &&
      prevProps.loading === nextProps.loading &&
      prevProps.isWaiting === nextProps.isWaiting &&
      prevProps.onStartGame === nextProps.onStartGame &&
      prevProps.onLeaveGame === nextProps.onLeaveGame
    );
  },
);

export default LobbyActions;

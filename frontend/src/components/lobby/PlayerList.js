import { memo, useState } from "react";
import styles from "./PlayerList.module.css";
import { getApiBase } from "../../utils/config";

const PlayerList = memo(
  function PlayerList({ players = [], currentPlayer, gameId, onPlayerRemoved }) {
    const [removing, setRemoving] = useState(null);

    const handleRemoveAI = async (playerId) => {
      setRemoving(playerId);

      try {
        const API_BASE = getApiBase();
        const response = await fetch(`${API_BASE}/api/games/${gameId}/players/${playerId}`, {
          method: "DELETE",
        });

        const data = await response.json();

        if (data.success && onPlayerRemoved) {
          onPlayerRemoved(data);
        }
      } catch (err) {
        console.error("Error removing AI player:", err);
      } finally {
        setRemoving(null);
      }
    };

    return (
      <div className={styles.playerList}>
        <h4>Players ({players.length}/4):</h4>
        {players.map((player) => (
          <div key={player.id} className={styles["playerList__item"]}>
            <span>
              {player.name} {player.name === currentPlayer && "(You)"}
              {player.is_ai && (
                <span className={styles["playerList__aiBadge"]}>
                  🤖 AI ({player.ai_difficulty})
                </span>
              )}
            </span>
            {player.is_ai && gameId && (
              <button
                onClick={() => handleRemoveAI(player.id)}
                disabled={removing === player.id}
                className={styles["playerList__removeButton"]}
                title="Remove AI player"
              >
                {removing === player.id ? "..." : "×"}
              </button>
            )}
          </div>
        ))}
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      JSON.stringify(prevProps.players) === JSON.stringify(nextProps.players) &&
      prevProps.currentPlayer === nextProps.currentPlayer &&
      prevProps.gameId === nextProps.gameId
    );
  },
);

export default PlayerList;

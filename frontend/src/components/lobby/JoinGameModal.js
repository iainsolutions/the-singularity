import { useState, useEffect } from "react";
import { useGame } from "../../context/GameContext";
import Button from "../common/Button";
import ExpansionSelector from "./ExpansionSelector";
import styles from "./JoinGameModal.module.css";

function JoinGameModal({ visible }) {
  const { createGame, joinGame, loading, clearError } = useGame();
  const [playerName, setPlayerName] = useState(() => {
    // Load cached username from localStorage on initial render
    return localStorage.getItem("innovation_player_name") || "";
  });
  const [gameId, setGameId] = useState("");
  const [showJoinForm, setShowJoinForm] = useState(false);
  const [selectedExpansions, setSelectedExpansions] = useState(() => {
    // Load cached expansion selections from localStorage on initial render
    const cached = localStorage.getItem("innovation_selected_expansions");
    return cached ? JSON.parse(cached) : [];
  });

  // Save username to localStorage whenever it changes
  useEffect(() => {
    if (playerName.trim()) {
      localStorage.setItem("innovation_player_name", playerName.trim());
    }
  }, [playerName]);

  // Save expansion selections to localStorage whenever they change
  useEffect(() => {
    localStorage.setItem("innovation_selected_expansions", JSON.stringify(selectedExpansions));
  }, [selectedExpansions]);

  const handleCreateGame = async () => {
    if (!playerName.trim()) {
      alert("Please enter your name");
      return;
    }

    try {
      clearError();
      // createGame now automatically adds the creator as a player
      // so we don't need to call joinGame separately
      await createGame(playerName.trim(), selectedExpansions);
    } catch (error) {
      console.error("Error creating game:", error);
    }
  };

  const handleJoinGame = async () => {
    if (!playerName.trim() || !gameId.trim()) {
      alert("Please enter your name and game ID");
      return;
    }

    try {
      clearError();
      await joinGame(gameId.trim(), playerName.trim());
    } catch (error) {
      console.error("Error joining game:", error);
    }
  };

  if (!visible) return null;

  return (
    <div className={styles.joinGameModal}>
      <div className={styles["joinGameModal__group"]}>
        <label htmlFor="playerName">Your Name:</label>
        <input
          id="playerName"
          type="text"
          value={playerName}
          onChange={(e) => setPlayerName(e.target.value)}
          placeholder="Enter your name"
          disabled={loading}
        />
      </div>

      <ExpansionSelector
        selectedExpansions={selectedExpansions}
        onExpansionsChange={setSelectedExpansions}
        disabled={loading}
      />

      <div className={styles["joinGameModal__buttons"]}>
        <Button
          variant="primary"
          onClick={handleCreateGame}
          disabled={loading || !playerName.trim()}
        >
          {loading ? "Creating..." : "Create New Game"}
        </Button>

        <Button
          variant="secondary"
          onClick={() => setShowJoinForm(!showJoinForm)}
          disabled={loading}
        >
          Join Existing Game
        </Button>
      </div>

      {showJoinForm && (
        <div className={styles["joinGameModal__joinForm"]}>
          <div className={styles["joinGameModal__group"]}>
            <label htmlFor="gameId">Game ID:</label>
            <input
              id="gameId"
              type="text"
              value={gameId}
              onChange={(e) => setGameId(e.target.value)}
              placeholder="Enter game ID"
              disabled={loading}
            />
          </div>

          <Button
            variant="primary"
            onClick={handleJoinGame}
            disabled={loading || !playerName.trim() || !gameId.trim()}
          >
            {loading ? "Joining..." : "Join Game"}
          </Button>
        </div>
      )}
    </div>
  );
}

export default JoinGameModal;

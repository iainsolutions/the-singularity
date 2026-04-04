import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGame } from "../context/GameContext";
import JoinGameModal from "./lobby/JoinGameModal";
import PlayerList from "./lobby/PlayerList";
import LobbyActions from "./lobby/LobbyActions";
import AIPlayerSetup from "./lobby/AIPlayerSetup";
import GamePreamble from "./lobby/GamePreamble";
import styles from "./GameLobby.module.css";

function GameLobby() {
  const navigate = useNavigate();
  const [copiedGameId, setCopiedGameId] = useState(false);
  const [showPreamble, setShowPreamble] = useState(false);
  const freshStart = useRef(false);
  const {
    startGame,
    gameId,
    gameState,
    playerName,
    loading,
    error,
    clearError,
    leaveGame,
    setGameState,
  } = useGame();

  // Find highest-difficulty AI opponent (if any)
  const aiPlayer = gameState?.players
    ?.filter((p) => p.is_ai)
    ?.sort((a, b) => {
      const order = ["novice","beginner","intermediate","skilled","advanced","pro","expert","master"];
      return order.indexOf(b.ai_difficulty) - order.indexOf(a.ai_difficulty);
    })?.[0];

  useEffect(() => {
    if (
      gameId &&
      gameState &&
      (gameState.phase === "playing" || gameState.phase === "setup_card_selection")
    ) {
      // Show preamble only for AI games that were just started from this
      // lobby (freshStart ref).  Rejoining an in-progress game skips it.
      if (aiPlayer && freshStart.current && !showPreamble) {
        setShowPreamble(true);
      } else if (!showPreamble) {
        navigate(`/game/${gameId}`);
      }
    }
  }, [gameId, gameState, navigate, aiPlayer, showPreamble]);

  const handleStartGame = async () => {
    try {
      clearError();
      freshStart.current = true;
      await startGame();
    } catch (error) {
      console.error("Error starting game:", error);
    }
  };

  const canStartGame =
    gameState &&
    gameState.players &&
    gameState.players.length >= 2 &&
    gameState.phase === "waiting_for_players";

  const handleCopyGameId = async () => {
    try {
      await navigator.clipboard.writeText(gameId);
      setCopiedGameId(true);
      // Reset the copied state after 2 seconds
      setTimeout(() => setCopiedGameId(false), 2000);
    } catch (err) {
      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = gameId;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
      setCopiedGameId(true);
      setTimeout(() => setCopiedGameId(false), 2000);
    }
  };

  const handleLeaveGame = async () => {
    try {
      await leaveGame();
      // The leaveGame function resets the state, which will trigger navigation
    } catch (error) {
      console.error("Error leaving game:", error);
    }
  };

  const handleAIAdded = (data) => {
    if (data.game_state) {
      setGameState(data.game_state);
    }
  };

  const handlePlayerRemoved = (data) => {
    if (data.game_state) {
      setGameState(data.game_state);
    }
  };

  if (showPreamble && aiPlayer) {
    return (
      <GamePreamble
        aiDifficulty={aiPlayer.ai_difficulty || "intermediate"}
        playerName={playerName}
        onBegin={() => {
          setShowPreamble(false);
          navigate(`/game/${gameId}`);
        }}
      />
    );
  }

  return (
    <>
      <title>The Singularity - Lobby</title>
      <div className={styles.lobby}>
        <h1 className={styles["lobby__title"]}>The Singularity</h1>
        <p>
          <a href="/rules.html" target="_blank" rel="noopener noreferrer">
            View Rules
          </a>
        </p>

        {error && <div className={styles["lobby__error-message"]}>{error}</div>}

        {!gameId ? (
          <JoinGameModal visible={!gameId} />
        ) : (
          <div className={styles["lobby__game-info"]}>
            <h2>Game Lobby</h2>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <p style={{ margin: 0 }}>
                <strong>Game ID:</strong> {gameId}
              </p>
              <button
                onClick={handleCopyGameId}
                style={{
                  padding: "4px 8px",
                  cursor: "pointer",
                  backgroundColor: copiedGameId ? "#4CAF50" : "#f0f0f0",
                  color: copiedGameId ? "white" : "black",
                  border: "1px solid #ccc",
                  borderRadius: "4px",
                  fontSize: "12px",
                  transition: "all 0.3s",
                }}
              >
                {copiedGameId ? "✓ Copied!" : "📋 Copy"}
              </button>
            </div>
            <p>
              <strong>Status:</strong>{" "}
              {gameState?.phase === "waiting_for_players"
                ? "Waiting for players"
                : gameState?.phase}
            </p>

            <PlayerList
              players={gameState?.players}
              currentPlayer={playerName}
              gameId={gameId}
              onPlayerRemoved={handlePlayerRemoved}
            />

            {/* AI Player Setup - only show in waiting phase and if not full */}
            {console.log("🎮 GameLobby: gameId =", gameId, "gameState.phase =", gameState?.phase)}
            {gameId && (
              <AIPlayerSetup
                gameId={gameId}
                onAIAdded={handleAIAdded}
                onAIRemoved={handlePlayerRemoved}
              />
            )}

            {/* Show rejoin button if game is in playing phase */}
            {gameState?.phase === "playing" && (
              <div style={{ margin: "20px 0" }}>
                <button
                  onClick={() => navigate(`/game/${gameId}`)}
                  style={{
                    padding: "10px 20px",
                    fontSize: "16px",
                    backgroundColor: "#4CAF50",
                    color: "white",
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  Rejoin Game
                </button>
                <p style={{ marginTop: "10px", fontSize: "14px", color: "#666" }}>
                  The game is already in progress. Click to rejoin.
                </p>
              </div>
            )}

            <LobbyActions
              canStartGame={canStartGame}
              onStartGame={handleStartGame}
              onLeaveGame={handleLeaveGame}
              loading={loading}
              isWaiting={gameState?.players && gameState.players.length < 2}
            />
          </div>
        )}
      </div>
    </>
  );
}

export default GameLobby;

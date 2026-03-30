import axios from "axios";
import { useCallback } from "react";
import { createLogger } from "../utils/logger";

// Create logger for GameAPI
const logger = createLogger("GameAPI");

/**
 * Custom hook for managing all game-related API calls
 * Provides functions for game creation, joining, actions, and responses
 */
export function useGameApi({
  gameId,
  playerId,
  setLoading,
  setError,
  setGameData,
  updateGameState,
  setPlayerName,
  saveSession,
  clearSession,
  setWebSocket,
  cleanupWebSocketState,
  API_BASE,
}) {
  const rejoinGame = useCallback(
    async (gameIdToRejoin, playerIdToRejoin, sessionToken = null) => {
      try {
        setLoading(true);

        // Try to get the current game state
        const response = await axios.get(`${API_BASE}/api/v1/games/${gameIdToRejoin}`);

        if (response.data && response.data.players) {
          // Check if the player is still in the game
          const player = response.data.players.find((p) => p.id === playerIdToRejoin);
          if (player) {
            // Set the game data with token for WebSocket authentication
            setGameData({
              gameId: gameIdToRejoin,
              playerId: playerIdToRejoin,
              gameState: response.data,
              token: sessionToken, // Include token from session for WebSocket auth
            });
            setPlayerName(player.name);
          } else {
            clearSession();
            setError("Game session expired");
          }
        } else {
          clearSession();
          setError("Game not found");
        }
      } catch (error) {
        logger.error("Failed to rejoin game:", error);
        // Don't clear session on transient errors (restart, timeout, 500)
        // Only clear on definitive "game/player gone" failures
        const status = error?.response?.status;
        if (status === 404 || status === 401 || status === 403) {
          clearSession();
          setError("Game session expired");
        } else {
          setError("Server unavailable — please refresh to reconnect");
        }
      } finally {
        setLoading(false);
      }
    },
    [API_BASE, setLoading, setGameData, setPlayerName, setError, clearSession],
  );

  const createGame = useCallback(
    async (createdBy = null, enabledExpansions = []) => {
      try {
        // Clean up any existing WebSocket state before creating new game
        if (cleanupWebSocketState) {
          cleanupWebSocketState();
        }

        setLoading(true);
        const response = await axios.post(`${API_BASE}/api/v1/games`, {
          created_by: createdBy,
          enabled_expansions: enabledExpansions,
        });

        // If creator was provided, the backend returns full game data
        if (createdBy && response.data.player_id) {
          // Set the game data just like joinGame does
          setGameData({
            gameId: response.data.game_id,
            playerId: response.data.player_id,
            gameState: response.data.game_state,
            token: response.data.token,
          });
          setPlayerName(createdBy);

          // Save session for persistence
          saveSession(
            response.data.game_id,
            response.data.player_id,
            createdBy,
            response.data.token,
          );
        }

        return response.data.game_id;
      } catch (error) {
        logger.error("Failed to create game:", error);
        setError("Failed to create game");
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [
      API_BASE,
      setLoading,
      setError,
      setGameData,
      setPlayerName,
      saveSession,
      cleanupWebSocketState,
    ],
  );

  const joinGame = useCallback(
    async (gameIdToJoin, playerName) => {
      try {
        // Clean up any existing WebSocket state before joining new game
        if (cleanupWebSocketState) {
          cleanupWebSocketState();
        }

        setLoading(true);

        // Check if this is a debug game (ends with _debug)
        if (gameIdToJoin.endsWith("_debug")) {
          logger.info(`Detected debug game: ${gameIdToJoin}`);

          // First, get the game state to find the player
          const gameStateResponse = await axios.get(
            `${API_BASE}/api/v1/admin/game/${gameIdToJoin}/state`,
          );
          const gameState = gameStateResponse.data;

          // Find the player by name
          const player = gameState.players.find((p) => p.name === playerName);
          if (!player) {
            throw new Error(
              `Player "${playerName}" not found in debug game. Available players: ${gameState.players
                .map((p) => p.name)
                .join(", ")}`,
            );
          }

          // Get the player index
          const playerIndex = gameState.players.findIndex((p) => p.name === playerName);

          // Get debug access token for this player
          const debugResponse = await axios.post(
            `${API_BASE}/api/v1/admin/game/${gameIdToJoin}/debug-access?player_index=${playerIndex}`,
          );

          logger.info(`Debug access granted for player: ${playerName} (${player.id})`);

          // Set game data using debug access info
          setGameData({
            gameId: gameIdToJoin,
            playerId: debugResponse.data.player_id,
            gameState: debugResponse.data.game_state,
            token: debugResponse.data.token,
          });
          setPlayerName(playerName);

          // Save session for persistence (including token)
          saveSession(
            gameIdToJoin,
            debugResponse.data.player_id,
            playerName,
            debugResponse.data.token,
          );
        } else {
          // Regular game join logic
          const response = await axios.post(`${API_BASE}/api/v1/games/${gameIdToJoin}/join`, {
            name: playerName,
          });

          // Backend returns JoinGameResponse with player_id, game_state, and token
          setGameData({
            gameId: gameIdToJoin,
            playerId: response.data.player_id,
            gameState: response.data.game_state,
            token: response.data.token, // Store the JWT token
          });
          setPlayerName(playerName);

          // Save session for persistence (including token)
          saveSession(gameIdToJoin, response.data.player_id, playerName, response.data.token);
        }
      } catch (error) {
        const errorMessage =
          error.response?.data?.detail ||
          error.response?.data?.error ||
          error.message ||
          "Failed to join game";
        setError(errorMessage);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [
      API_BASE,
      setLoading,
      setGameData,
      setPlayerName,
      setError,
      saveSession,
      cleanupWebSocketState,
    ],
  );

  const startGame = useCallback(async () => {
    try {
      setLoading(true);
      const response = await axios.post(`${API_BASE}/api/v1/games/${gameId}/start`);

      // Backend returns StartGameResponse with game_state directly
      updateGameState(response.data.game_state);
    } catch (error) {
      const errorMessage = error.response?.data?.error || error.message || "Failed to start game";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [API_BASE, gameId, setLoading, updateGameState, setError]);

  const performAction = useCallback(
    async (actionType, actionData = {}) => {
      try {
        const response = await axios.post(`${API_BASE}/api/v1/games/${gameId}/action`, {
          player_id: playerId,
          action_type: actionType,
          ...actionData,
        });

        if (!response.data.success) {
          const errorMessage = response.data.error || "Action failed";
          setError(errorMessage);
          return null;
        }

        // Game state will be updated via WebSocket
        return response.data;
      } catch (error) {
        const errorMessage = error.response?.data?.error || error.message || "Action failed";
        setError(errorMessage);
        return null;
      }
    },
    [API_BASE, gameId, playerId, setError],
  );

  // CONSOLIDATION: respondToDogma function removed - all dogma responses now use v2 WebSocket system

  const leaveGame = useCallback(async () => {
    // Centralized game leave logic
    if (gameId && playerId) {
      try {
        // Call the backend leave endpoint
        const response = await axios.post(
          `${API_BASE}/api/v1/games/${gameId}/leave?player_id=${playerId}`,
        );

        if (!response.data.success) {
          logger.error("Failed to leave game:", response.data.error);
        }
      } catch (error) {
        logger.error("Error leaving game:", error);
        // Continue with cleanup even if the API call fails
      }
    }
  }, [API_BASE, gameId, playerId]);

  // Transaction management
  const startTransaction = useCallback(
    async (actionType) => {
      try {
        const response = await axios.post(`${API_BASE}/api/v1/games/${gameId}/transaction/start`, {
          player_id: playerId,
          action_type: actionType,
        });

        if (!response.data.success) {
          const errorMessage = response.data.error || "Failed to start transaction";
          setError(errorMessage);
          return null;
        }

        return response.data;
      } catch (error) {
        const errorMessage =
          error.response?.data?.error || error.message || "Failed to start transaction";
        setError(errorMessage);
        logger.error("Failed to start transaction:", error);
        return null;
      }
    },
    [API_BASE, gameId, playerId, setError],
  );

  const commitTransaction = useCallback(async () => {
    try {
      const response = await axios.post(`${API_BASE}/api/v1/games/${gameId}/transaction/commit`);

      if (!response.data.success) {
        const errorMessage = response.data.error || "Failed to commit transaction";
        setError(errorMessage);
        return null;
      }

      return response.data;
    } catch (error) {
      const errorMessage =
        error.response?.data?.error || error.message || "Failed to commit transaction";
      setError(errorMessage);
      logger.error("Failed to commit transaction:", error);
      return null;
    }
  }, [API_BASE, gameId, setError]);

  const undoTransaction = useCallback(async () => {
    try {
      const response = await axios.post(`${API_BASE}/api/v1/games/${gameId}/transaction/undo`, {
        player_id: playerId,
      });

      if (!response.data.success) {
        const errorMessage = response.data.error || "Failed to undo transaction";
        setError(errorMessage);
        return null;
      }

      return response.data;
    } catch (error) {
      const errorMessage =
        error.response?.data?.error || error.message || "Failed to undo transaction";
      setError(errorMessage);
      logger.error("Failed to undo transaction:", error);
      return null;
    }
  }, [API_BASE, gameId, playerId, setError]);

  return {
    rejoinGame,
    createGame,
    joinGame,
    startGame,
    performAction,
    leaveGame,
    startTransaction,
    commitTransaction,
    undoTransaction,
  };
}

import { useReducer, useCallback } from "react";

const initialState = {
  gameId: null,
  playerId: null,
  playerName: "",
  gameState: null,
  token: null, // JWT token for WebSocket authentication
  isConnected: false,
  websocket: null,
  error: null,
  loading: false,
  // Dogma results display state
  dogmaResults: null,
  showDogmaResults: false,
  // Activity events from backend for activity panel
  activityEvents: [],
  // Transaction state for undo/commit
  currentTransaction: null, // { transaction_id, action_type, started_at }
};

function gameReducer(state, action) {
  switch (action.type) {
    case "SET_LOADING":
      return { ...state, loading: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload, loading: false };
    case "CLEAR_ERROR":
      return { ...state, error: null };
    case "SET_PLAYER_NAME":
      return { ...state, playerName: action.payload };
    case "SET_GAME_DATA":
      return {
        ...state,
        gameId: action.payload.gameId,
        playerId: action.payload.playerId,
        gameState: action.payload.gameState,
        token: action.payload.token || state.token, // Store token if provided
        loading: false,
        error: null,
        // Initialize activity events from backend action_log
        activityEvents: action.payload.gameState?.action_log || [],
        // Initialize transaction state from backend current_transaction
        currentTransaction: action.payload.gameState?.current_transaction || null,
      };
    case "UPDATE_GAME_STATE":
      console.log("🔄 [gameReducer] UPDATE_GAME_STATE:", {
        hasPayload: !!action.payload,
        hasPlayers: !!action.payload?.players,
        playersCount: action.payload?.players?.length,
        gameId: action.payload?.game_id,
      });
      return {
        ...state,
        gameState: action.payload,
        // Sync activity events from backend action_log if present
        activityEvents: action.payload?.action_log || state.activityEvents,
        // Sync transaction state from backend current_transaction if present
        currentTransaction: action.payload?.current_transaction !== undefined
          ? action.payload.current_transaction
          : state.currentTransaction,
      };
    case "UPDATE_GAME_STATE_FUNCTION":
      return { ...state, gameState: action.payload(state.gameState) };
    case "SET_WEBSOCKET":
      return { ...state, websocket: action.payload };
    case "SET_CONNECTED":
      return { ...state, isConnected: action.payload };
    case "SET_DOGMA_RESULTS":
      // DISABLED: DogmaResultsDisplay functionality disabled - results only show in ActionLog
      return {
        ...state,
        dogmaResults: {
          results: action.payload.results,
          cardName: action.payload.cardName,
        },
        showDogmaResults: false, // Always keep this false to prevent popup
      };
    case "HIDE_DOGMA_RESULTS":
      return {
        ...state,
        showDogmaResults: false,
      };
    case "CLEAR_DOGMA_RESULTS":
      return {
        ...state,
        dogmaResults: null,
        showDogmaResults: false,
      };
    case "RESET_GAME":
      return {
        ...initialState,
        playerName: state.playerName,
      };
    case "ADD_ACTIVITY_EVENT":
      return {
        ...state,
        activityEvents: [...state.activityEvents, action.payload].slice(-200),
      };
    case "CLEAR_ACTIVITY":
      return {
        ...state,
        activityEvents: [],
      };
    case "SET_TRANSACTION":
      return {
        ...state,
        currentTransaction: action.payload,
      };
    case "CLEAR_TRANSACTION":
      return {
        ...state,
        currentTransaction: null,
      };
    default:
      return state;
  }
}

/**
 * Custom hook for managing game state using useReducer
 * Provides state and action dispatchers for game management
 */
export function useGameState() {
  const [state, dispatch] = useReducer(gameReducer, initialState);

  // Action creators - wrapped in useCallback for optimization
  const setLoading = useCallback((loading) => {
    dispatch({ type: "SET_LOADING", payload: loading });
  }, []);

  const setError = useCallback((error) => {
    dispatch({ type: "SET_ERROR", payload: error });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: "CLEAR_ERROR" });
  }, []);

  const setPlayerName = useCallback((name) => {
    dispatch({ type: "SET_PLAYER_NAME", payload: name });
  }, []);

  const setGameData = useCallback((gameData) => {
    dispatch({ type: "SET_GAME_DATA", payload: gameData });
  }, []);

  const updateGameState = useCallback((gameState) => {
    // Handle both direct state updates and function-based updates
    if (typeof gameState === "function") {
      dispatch({ type: "UPDATE_GAME_STATE_FUNCTION", payload: gameState });
    } else {
      dispatch({ type: "UPDATE_GAME_STATE", payload: gameState });
    }
  }, []);

  const setWebSocket = useCallback((websocket) => {
    dispatch({ type: "SET_WEBSOCKET", payload: websocket });
  }, []);

  const setConnected = useCallback((connected) => {
    dispatch({ type: "SET_CONNECTED", payload: connected });
  }, []);

  const resetGame = useCallback(() => {
    dispatch({ type: "RESET_GAME" });
  }, []);

  const setDogmaResults = useCallback((results, cardName) => {
    dispatch({ type: "SET_DOGMA_RESULTS", payload: { results, cardName } });
  }, []);

  const hideDogmaResults = useCallback(() => {
    dispatch({ type: "HIDE_DOGMA_RESULTS" });
  }, []);

  const clearDogmaResults = useCallback(() => {
    dispatch({ type: "CLEAR_DOGMA_RESULTS" });
  }, []);

  // Activity events management
  const addActivityEvent = useCallback((event) => {
    dispatch({ type: "ADD_ACTIVITY_EVENT", payload: event });
  }, []);

  const clearActivity = useCallback(() => {
    dispatch({ type: "CLEAR_ACTIVITY" });
  }, []);

  const setTransaction = useCallback((transaction) => {
    dispatch({ type: "SET_TRANSACTION", payload: transaction });
  }, []);

  const clearTransaction = useCallback(() => {
    dispatch({ type: "CLEAR_TRANSACTION" });
  }, []);

  return {
    // State
    ...state,

    // Actions
    setLoading,
    setError,
    clearError,
    setPlayerName,
    setGameData,
    updateGameState,
    setWebSocket,
    setConnected,
    resetGame,
    setDogmaResults,
    hideDogmaResults,
    clearDogmaResults,
    addActivityEvent,
    clearActivity,
    setTransaction,
    clearTransaction,
  };
}

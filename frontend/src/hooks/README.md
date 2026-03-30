# Game Hooks Documentation

This directory contains custom React hooks that have been extracted from the original GameContext.js file for better separation of concerns and maintainability.

## Hook Structure

### `useGameState`

- **Purpose**: Manages all game-related state using useReducer
- **Exports**: State properties and action dispatchers
- **Responsibilities**:
  - Game state (gameId, playerId, playerName, gameState)
  - UI state (loading, error, isConnected)
  - WebSocket state (websocket reference)

### `useWebSocket`

- **Purpose**: Handles WebSocket connection lifecycle and messaging
- **Dependencies**: Requires state and actions from useGameState
- **Responsibilities**:
  - WebSocket connection establishment
  - Automatic reconnection logic
  - Message handling and routing
  - Connection status management

### `useGameApi`

- **Purpose**: Manages all REST API calls to the backend
- **Dependencies**: Requires state and actions from useGameState and useSessionManager
- **Responsibilities**:
  - Game creation and joining
  - Player actions (start, perform action, dogma responses)
  - Session rejoining logic
  - Error handling for API calls

### `useSessionManager`

- **Purpose**: Handles localStorage persistence for game sessions
- **Exports**: Session save, load, and clear functions
- **Responsibilities**:
  - Persisting game session data
  - Loading session on app restart
  - Clearing session data

## Benefits of This Architecture

1. **Separation of Concerns**: Each hook has a single responsibility
2. **Reusability**: Hooks can be used independently or combined
3. **Testability**: Each hook can be tested in isolation
4. **Maintainability**: Changes to one concern don't affect others
5. **Code Readability**: Smaller, focused files are easier to understand

## Usage

The hooks are composed together in `GameContext.js` to maintain backward compatibility with existing components. The refactoring is transparent to consuming components.

```javascript
import { useGameState, useWebSocket, useGameApi, useSessionManager } from '../hooks';

// All hooks work together to provide the same API as before
const gameState = useGameState();
const sessionManager = useSessionManager();
const gameApi = useGameApi({ /* dependencies */ });
const webSocket = useWebSocket({ /* dependencies */ });
```

## Future Improvements

- Consider using React Context for each hook to further decouple dependencies
- Add more granular error handling per hook
- Implement retry logic for failed API calls
- Add TypeScript for better type safety

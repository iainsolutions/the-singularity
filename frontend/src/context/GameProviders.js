import { GameApiProvider } from "./GameApiContext";
import { GameStateProvider } from "./GameStateContext";
import { WebSocketProvider } from "./WebSocketContext";

export function GameProviders({ children, navigate }) {
  return (
    <GameStateProvider>
      <WebSocketProvider>
        <GameApiProvider navigate={navigate}>{children}</GameApiProvider>
      </WebSocketProvider>
    </GameStateProvider>
  );
}

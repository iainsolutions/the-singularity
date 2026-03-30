import React from "react";
import { useNavigate } from "react-router-dom";
import ErrorBoundary from "./ErrorBoundary";

function GameErrorFallback({ error, reset }) {
  const navigate = useNavigate();

  const handleReturnToLobby = () => {
    // Clear any game state and return to lobby
    localStorage.removeItem("gameId");
    localStorage.removeItem("playerId");
    navigate("/");
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "2rem",
        backgroundColor: "#f5f5f5",
      }}
    >
      <div
        style={{
          backgroundColor: "white",
          borderRadius: "8px",
          padding: "2rem",
          boxShadow: "0 2px 10px rgba(0, 0, 0, 0.1)",
          maxWidth: "500px",
          width: "100%",
          textAlign: "center",
        }}
      >
        <h2 style={{ color: "#d32f2f", marginBottom: "1rem" }}>Game Error</h2>
        <p style={{ color: "#666", marginBottom: "1.5rem" }}>
          An error occurred while playing the game. This might be due to a connection issue or an
          unexpected game state.
        </p>

        {import.meta.env.MODE === "development" && (
          <details
            style={{
              textAlign: "left",
              marginBottom: "1.5rem",
              padding: "1rem",
              backgroundColor: "#f5f5f5",
              borderRadius: "4px",
            }}
          >
            <summary style={{ cursor: "pointer", fontWeight: "bold" }}>Error Details</summary>
            <pre
              style={{
                marginTop: "0.5rem",
                fontSize: "0.85rem",
                overflow: "auto",
              }}
            >
              {error?.toString()}
            </pre>
          </details>
        )}

        <div style={{ display: "flex", gap: "1rem", justifyContent: "center" }}>
          <button
            onClick={reset}
            style={{
              padding: "0.5rem 1.5rem",
              backgroundColor: "#1976d2",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "1rem",
            }}
          >
            Try Again
          </button>
          <button
            onClick={handleReturnToLobby}
            style={{
              padding: "0.5rem 1.5rem",
              backgroundColor: "#757575",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "1rem",
            }}
          >
            Return to Lobby
          </button>
        </div>
      </div>
    </div>
  );
}

function GameErrorBoundary({ children }) {
  return (
    <ErrorBoundary
      fallback={(error, reset) => <GameErrorFallback error={error} reset={reset} />}
      message="An error occurred during the game. Please try rejoining or starting a new game."
    >
      {children}
    </ErrorBoundary>
  );
}

export default GameErrorBoundary;

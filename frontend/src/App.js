import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import GameLobby from "./components/GameLobby";
import GameBoard from "./components/GameBoard";
import { GameProvider } from "./context/GameContext";
import ErrorBoundary from "./components/ErrorBoundary";
import GameErrorBoundary from "./components/GameErrorBoundary";
import ToastContainer from "./components/ToastContainer";
import theme from "./theme";
import styles from "./App.module.css";

// Initialize debug controls (available in browser console)
import "./utils/debugControl";

// Inner component that has access to useNavigate
function AppRoutes() {
  const navigate = useNavigate();

  return (
    <GameProvider navigate={navigate}>
      <div className={styles.app}>
        <Routes>
          <Route
            path="/"
            element={
              <ErrorBoundary message="An error occurred in the game lobby. Please refresh the page.">
                <GameLobby />
              </ErrorBoundary>
            }
          />
          <Route
            path="/game/:gameId"
            element={
              <GameErrorBoundary>
                <GameBoard />
              </GameErrorBoundary>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </GameProvider>
  );
}

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <ErrorBoundary>
        <Router>
          <AppRoutes />
        </Router>
        <ToastContainer />
      </ErrorBoundary>
    </ThemeProvider>
  );
}

export default App;

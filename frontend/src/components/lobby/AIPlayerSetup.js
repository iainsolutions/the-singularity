import { useState, useEffect } from "react";
import styles from "./AIPlayerSetup.module.css";
import { getApiBase } from "../../utils/config";

function AIPlayerSetup({ gameId, onAIAdded, onAIRemoved }) {
  const [aiEnabled, setAiEnabled] = useState(false);
  const [providers, setProviders] = useState([]);
  const [currentProvider, setCurrentProvider] = useState("");
  const [selectedProvider, setSelectedProvider] = useState(() => {
    // Load saved provider preference from localStorage
    return localStorage.getItem("innovation_ai_provider") || "";
  });
  const [difficulties, setDifficulties] = useState([]);
  const [selectedDifficulty, setSelectedDifficulty] = useState(() => {
    // Load saved difficulty preference from localStorage
    return localStorage.getItem("innovation_ai_difficulty") || "beginner";
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check AI service status on mount
  useEffect(() => {
    const checkAIStatus = async () => {
      try {
        const API_BASE = getApiBase();
        console.log("🤖 AIPlayerSetup: Checking AI status at:", `${API_BASE}/api/v1/ai/status`);
        const response = await fetch(`${API_BASE}/api/v1/ai/status`);
        const data = await response.json();
        console.log("🤖 AIPlayerSetup: AI status response:", data);

        if (data.enabled) {
          console.log("🤖 AIPlayerSetup: AI is enabled, showing component");
          setAiEnabled(true);
          setDifficulties(data.available_difficulties || []);

          // Filter to only show providers that have API keys configured
          const configuredProviders = (data.available_providers || []).filter(p => p.available);
          setProviders(configuredProviders);
          setCurrentProvider(data.default_provider || "anthropic");

          // Set selected provider (use default provider if no saved preference)
          const savedProvider = localStorage.getItem("innovation_ai_provider");
          const validProvider = configuredProviders.find(p => p.name === savedProvider);

          if (!validProvider) {
            // Use default provider from backend
            const defaultProvider = data.default_provider || configuredProviders[0]?.name || "anthropic";
            setSelectedProvider(defaultProvider);
            localStorage.setItem("innovation_ai_provider", defaultProvider);
          }

          // Only update selectedDifficulty if the saved preference is invalid
          const savedDifficulty = localStorage.getItem("innovation_ai_difficulty");
          const validDifficulties = data.available_difficulties?.map((d) => d.id) || [];

          // If saved preference is invalid or doesn't exist, use first available
          if (!savedDifficulty || !validDifficulties.includes(savedDifficulty)) {
            if (data.available_difficulties && data.available_difficulties.length > 0) {
              const defaultDifficulty = data.available_difficulties[0].id;
              setSelectedDifficulty(defaultDifficulty);
              localStorage.setItem("innovation_ai_difficulty", defaultDifficulty);
            }
          }
        } else {
          console.log("🤖 AIPlayerSetup: AI is disabled, hiding component");
        }
      } catch (err) {
        console.error("🤖 AIPlayerSetup: Failed to check AI status:", err);
        setAiEnabled(false);
      }
    };

    checkAIStatus();
  }, []);

  const handleAddAI = async () => {
    setLoading(true);
    setError(null);

    try {
      const API_BASE = getApiBase();
      const requestBody = {
        difficulty: selectedDifficulty,
      };

      // Always include provider selection (backend uses default if not specified)
      if (selectedProvider) {
        requestBody.provider = selectedProvider;
      }

      const response = await fetch(`${API_BASE}/api/v1/games/${gameId}/add_ai_player`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (data.success) {
        if (onAIAdded) {
          onAIAdded(data);
        }
      } else {
        setError(data.error || "Failed to add AI player");
      }
    } catch (err) {
      setError("Network error: Could not add AI player");
      console.error("Error adding AI player:", err);
    } finally {
      setLoading(false);
    }
  };

  if (!aiEnabled) {
    console.log("🤖 AIPlayerSetup: Component not rendering (aiEnabled=false)");
    return null; // Don't show AI controls if service is disabled
  }

  console.log("🤖 AIPlayerSetup: Rendering component");

  const selectedDifficultyInfo = difficulties.find((d) => d.id === selectedDifficulty);

  // Determine which model and cost to display based on selected provider
  const displayModel = selectedDifficultyInfo?.models?.[selectedProvider]
    || selectedDifficultyInfo?.openai_model  // Legacy fallback
    || selectedDifficultyInfo?.model;         // Legacy fallback

  const displayCost = selectedDifficultyInfo?.costs?.[selectedProvider]
    || selectedDifficultyInfo?.estimated_cost_per_game;  // Legacy fallback

  // Show provider selector if 2+ providers configured
  const showProviderSelector = providers.length >= 2;

  return (
    <div className={styles.aiSetup}>
      <h3 className={styles.aiSetup__title}>Add AI Player</h3>

      {error && <div className={styles.aiSetup__error}>{error}</div>}

      <div className={styles.aiSetup__controls}>
        {/* Provider selector - only show if multiple providers available */}
        {showProviderSelector && (
          <div className={styles.aiSetup__providerSelect}>
            <label htmlFor="ai-provider">Provider:</label>
            <select
              id="ai-provider"
              value={selectedProvider}
              onChange={(e) => {
                const newProvider = e.target.value;
                setSelectedProvider(newProvider);
                // Save preference to localStorage
                localStorage.setItem("innovation_ai_provider", newProvider);
              }}
              disabled={loading}
              className={styles.aiSetup__select}
            >
              {providers.map((provider) => (
                <option key={provider.name} value={provider.name}>
                  {provider.display_name}
                  {provider.is_default ? " (default)" : ""}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className={styles.aiSetup__difficultySelect}>
          <label htmlFor="ai-difficulty">Difficulty:</label>
          <select
            id="ai-difficulty"
            value={selectedDifficulty}
            onChange={(e) => {
              const newDifficulty = e.target.value;
              setSelectedDifficulty(newDifficulty);
              // Save preference to localStorage
              localStorage.setItem("innovation_ai_difficulty", newDifficulty);
            }}
            disabled={loading}
            className={styles.aiSetup__select}
          >
            {difficulties.map((diff) => (
              <option key={diff.id} value={diff.id}>
                {diff.name}
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleAddAI} disabled={loading} className={styles.aiSetup__addButton}>
          {loading ? "Adding..." : "Add AI Player"}
        </button>
      </div>

      {selectedDifficultyInfo && (
        <div className={styles.aiSetup__info}>
          <p className={styles.aiSetup__description}>{selectedDifficultyInfo.description}</p>
          <p className={styles.aiSetup__cost}>
            Estimated cost: {displayCost} per game
          </p>
          <p className={styles.aiSetup__model}>
            Provider: {selectedProvider} | Model: {displayModel}
          </p>
        </div>
      )}
    </div>
  );
}

export default AIPlayerSetup;

import { useState, useEffect } from "react";
import styles from "./AICostMonitor.module.css";
import { getApiBase } from "../../utils/config";

function AICostMonitor({ gameId }) {
  const [costStats, setCostStats] = useState(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCostStats = async () => {
      try {
        const API_BASE = getApiBase();
        const response = await fetch(`${API_BASE}/api/v1/ai/cost_stats`);
        const data = await response.json();
        setCostStats(data);
      } catch (err) {
        console.error("Failed to fetch cost stats:", err);
      } finally {
        setLoading(false);
      }
    };

    // Fetch immediately
    fetchCostStats();

    // Refresh every 5 seconds while component is mounted
    const interval = setInterval(fetchCostStats, 5000);

    return () => clearInterval(interval);
  }, [gameId]);

  if (loading || !costStats) {
    return null;
  }

  // Find current game's cost
  const gameCost = costStats.per_game_costs?.[gameId] || costStats.average_cost_per_game || 0;
  const totalCost = costStats.daily_spent || costStats.total_costs || 0;
  const dailyLimit = costStats.daily_limit || 50;
  const dailyRemaining = costStats.daily_remaining || (dailyLimit - totalCost);
  const dailyPercentUsed = (totalCost / dailyLimit) * 100;

  return (
    <div className={styles.costMonitor}>
      <button
        className={styles.costMonitor__toggle}
        onClick={() => setIsExpanded(!isExpanded)}
        title="AI Cost Monitor"
      >
        <span className={styles.costMonitor__icon}>💰</span>
        <span className={styles.costMonitor__summary}>${gameCost.toFixed(2)}</span>
      </button>

      {isExpanded && (
        <div className={styles.costMonitor__panel}>
          <div className={styles.costMonitor__header}>
            <h4>AI Cost Monitor</h4>
            <button className={styles.costMonitor__close} onClick={() => setIsExpanded(false)}>
              ×
            </button>
          </div>

          <div className={styles.costMonitor__section}>
            <h5>Current Game</h5>
            <div className={styles.costMonitor__stat}>
              <span className={styles.costMonitor__label}>Cost:</span>
              <span className={styles.costMonitor__value}>${gameCost.toFixed(2)}</span>
            </div>
          </div>

          <div className={styles.costMonitor__section}>
            <h5>Daily Usage</h5>
            <div className={styles.costMonitor__stat}>
              <span className={styles.costMonitor__label}>Total:</span>
              <span className={styles.costMonitor__value}>
                ${totalCost.toFixed(2)} / ${dailyLimit.toFixed(2)}
              </span>
            </div>
            <div className={styles.costMonitor__stat}>
              <span className={styles.costMonitor__label}>Remaining:</span>
              <span className={styles.costMonitor__value}>${dailyRemaining.toFixed(2)}</span>
            </div>
            <div className={styles.costMonitor__progressBar}>
              <div
                className={styles.costMonitor__progressFill}
                style={{
                  width: `${Math.min(dailyPercentUsed, 100)}%`,
                  backgroundColor:
                    dailyPercentUsed > 90
                      ? "#dc3545"
                      : dailyPercentUsed > 70
                        ? "#ffc107"
                        : "#28a745",
                }}
              />
            </div>
            <div className={styles.costMonitor__percentage}>
              {dailyPercentUsed.toFixed(1)}% used
            </div>
          </div>

          {costStats.by_difficulty && (
            <div className={styles.costMonitor__section}>
              <h5>By Difficulty</h5>
              {Object.entries(costStats.by_difficulty).map(([difficulty, cost]) => (
                <div key={difficulty} className={styles.costMonitor__stat}>
                  <span className={styles.costMonitor__label}>{difficulty}:</span>
                  <span className={styles.costMonitor__value}>${cost.toFixed(2)}</span>
                </div>
              ))}
            </div>
          )}

          <div className={styles.costMonitor__footer}>
            <small>Updates every 5 seconds</small>
          </div>
        </div>
      )}
    </div>
  );
}

export default AICostMonitor;

import { memo, useEffect, useState } from "react";
import styles from "./Toast.module.css";

/**
 * Toast notification component for displaying temporary messages
 *
 * Features:
 * - Auto-dismiss after duration
 * - Different types: info, success, warning, error
 * - Slide-in animation
 * - Stacking support for multiple toasts
 */
const Toast = memo(function Toast({ message, type = "info", duration = 3000, onClose }) {
  const [isVisible, setIsVisible] = useState(false);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    // Trigger slide-in animation
    const showTimer = setTimeout(() => setIsVisible(true), 10);

    // Auto-dismiss
    const dismissTimer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(() => {
        setIsVisible(false);
        if (onClose) onClose();
      }, 300); // Match CSS transition duration
    }, duration);

    return () => {
      clearTimeout(showTimer);
      clearTimeout(dismissTimer);
    };
  }, [duration, onClose]);

  const toastClasses = [
    styles.toast,
    styles[type] || styles.info,
    isVisible ? styles.visible : "",
    isExiting ? styles.exiting : ""
  ].filter(Boolean).join(" ");

  // Icon based on toast type
  const icon = {
    info: "ℹ️",
    success: "✅",
    warning: "⚠️",
    error: "❌",
    city: "🏙️" // Special type for city draws
  }[type] || "ℹ️";

  return (
    <div className={toastClasses} role="alert">
      <span className={styles.icon}>{icon}</span>
      <span className={styles.message}>{message}</span>
    </div>
  );
});

export default Toast;

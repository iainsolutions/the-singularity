import { memo, useCallback, useEffect, useState } from "react";
import Toast from "./Toast";
import styles from "./ToastContainer.module.css";

/**
 * ToastContainer manages multiple toast notifications
 * Uses event-based system to allow toasts to be triggered from anywhere
 */
const ToastContainer = memo(function ToastContainer() {
  const [toasts, setToasts] = useState([]);

  // Listen for toast events
  useEffect(() => {
    const handleToastEvent = (event) => {
      const { message, type = "info", duration = 3000 } = event.detail;
      const id = Date.now() + Math.random();

      setToasts((prev) => [
        ...prev,
        { id, message, type, duration }
      ]);
    };

    window.addEventListener("showToast", handleToastEvent);
    return () => window.removeEventListener("showToast", handleToastEvent);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return (
    <div className={styles.toastContainer}>
      {toasts.map((toast, index) => (
        <div
          key={toast.id}
          className={styles.toastWrapper}
          style={{ bottom: `${20 + index * 80}px` }}
        >
          <Toast
            message={toast.message}
            type={toast.type}
            duration={toast.duration}
            onClose={() => removeToast(toast.id)}
          />
        </div>
      ))}
    </div>
  );
});

export default ToastContainer;

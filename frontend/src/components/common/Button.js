import { memo, useMemo } from "react";
import styles from "./Button.module.css";

const Button = memo(
  function Button({ variant = "primary", size = "medium", className = "", children, ...props }) {
    // Memoize class calculation to prevent unnecessary recalculations
    const classes = useMemo(
      () =>
        [styles.btn, styles[`btn-${variant}`] || "", styles[`btn-${size}`] || "", className]
          .join(" ")
          .trim(),
      [variant, size, className],
    );
    return (
      <button className={classes} {...props}>
        {children}
      </button>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    return (
      prevProps.variant === nextProps.variant &&
      prevProps.size === nextProps.size &&
      prevProps.className === nextProps.className &&
      prevProps.children === nextProps.children &&
      prevProps.disabled === nextProps.disabled &&
      prevProps.onClick === nextProps.onClick
    );
  },
);

export default Button;

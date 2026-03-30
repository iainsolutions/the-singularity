import { useState, memo, useMemo, useRef, useCallback, useEffect } from "react";
import styles from "./Card.module.css";
import { getCardImagePath } from "../utils/cardImageMapping";

const Card = memo(
  function Card({
    card,
    isClickable = false,
    isSelected = false,
    showCheckbox = false,
    onClick,
    size = "normal",
    lazy = false,
    priority = false,
    showBack = false,
    isSelecting = false, // Add prop to indicate card selection mode
    isEligible = false, // Add prop to indicate card is eligible for selection
    isActivatable = false, // UI Hint: Card can activate dogma (from computed_state)
  }) {
    // Removed isExpanded state - using CSS hover instead
    const [imageLoaded, setImageLoaded] = useState(false);
    const [imageError, setImageError] = useState(false);
    const [isInView, setIsInView] = useState(!lazy);
    const cardRef = useRef(null);
    const intersectionObserverRef = useRef(null);

    // Get image path if we have a card with an image
    const imagePath = useMemo(() => {
      if (!card) return null;
      // If showBack is true, get the back image instead of front
      return getCardImagePath(card, showBack ? "back" : "front");
    }, [card, showBack]);

    // Intersection Observer for lazy loading
    const setupIntersectionObserver = useCallback(() => {
      if (!lazy || isInView || !cardRef.current) return;

      intersectionObserverRef.current = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setIsInView(true);
            intersectionObserverRef.current?.disconnect();
          }
        },
        {
          rootMargin: "50px", // Start loading 50px before card comes into view
          threshold: 0.1,
        },
      );

      intersectionObserverRef.current.observe(cardRef.current);
    }, [lazy, isInView]);

    // Set up intersection observer using useEffect for side effects
    useEffect(() => {
      if (lazy && cardRef.current && !isInView) {
        setupIntersectionObserver();
      }

      // Cleanup function
      return () => {
        intersectionObserverRef.current?.disconnect();
      };
    }, [lazy, isInView, setupIntersectionObserver]);

    // Memoize card classes to prevent unnecessary recalculations
    const cardClasses = useMemo(
      () =>
        [
          styles.card,
          styles[size] || "",
          card?.color ? styles[card.color] : "",
          isClickable ? styles.clickable : "",
          isSelected ? styles.selected : "",
          isSelecting ? styles.selecting : "", // Add selecting class
          isEligible ? styles.eligible : "", // Add eligible class for highlighting
          isActivatable ? styles.activatable : "", // UI Hint: Dogma-activatable glow
          !imageLoaded && imagePath && isInView ? styles.imageLoading : "",
          imageError ? styles.imageError : "",
          imageLoaded ? styles.imageLoaded : "",
          priority ? styles.priority : "",
        ]
          .filter(Boolean)
          .join(" "),
      [
        size,
        card?.color,
        isClickable,
        isSelected,
        isSelecting,
        isEligible,
        isActivatable,
        imageLoaded,
        imagePath,
        imageError,
        isInView,
        priority,
      ],
    );

    const handleClick = () => {
      if (isClickable && onClick) {
        onClick(card);
      }
    };

    // Removed microscope click handler - using CSS hover instead

    const handleImageLoad = useCallback(() => {
      setImageLoaded(true);
      setImageError(false);
    }, []);

    const handleImageError = useCallback(() => {
      setImageLoaded(false);
      setImageError(true);
    }, []);

    if (!card) {
      return (
        <div className={`${styles.card} ${styles.empty} ${styles[size] || ""}`}>
          <div className={styles.cardPlaceholder}>Empty</div>
        </div>
      );
    }

    return (
      <div
        ref={cardRef}
        className={cardClasses}
        onClick={handleClick}
        role={isClickable ? "button" : undefined}
        aria-label={
          card
            ? `${card.name}, Age ${card.age}${card.is_achievement ? " (Achievement)" : ""}`
            : "Empty card"
        }
        tabIndex={isClickable ? 0 : -1}
        data-achievement={card?.is_achievement ? "true" : "false"}
      >
        {/* Card image */}
        {imagePath && isInView ? (
          <img
            src={imagePath}
            alt={`${card.name} card, Age ${card.age}${card.is_achievement ? " Achievement" : ""}`}
            className={styles.cardImage}
            onLoad={handleImageLoad}
            onError={handleImageError}
            loading={priority ? "eager" : "lazy"}
            decoding="async"
            style={{
              display: imageError ? "none" : "block",
              opacity: imageLoaded ? 1 : 0,
            }}
          />
        ) : imagePath && !isInView ? (
          <div className={styles.lazySkeleton}>
            <div className={styles.skeletonContent}>
              <div className={styles.cardName}>{card.name}</div>
              <div className={styles.cardAge}>Age {card.age}</div>
              <div className={styles.loadingText}>Loading...</div>
            </div>
          </div>
        ) : (
          <div className={styles.cardPlaceholder}>
            <div className={styles.cardName}>{card.name}</div>
            <div className={styles.cardAge}>Age {card.age}</div>
            <div className={styles.noImageText}>No image available</div>
          </div>
        )}

        {/* Show loading indicator while image loads */}
        {imagePath && !imageLoaded && !imageError && (
          <div className={styles.loadingOverlay}>
            <div className={styles.loadingSpinner}></div>
          </div>
        )}

        {/* Show error state if image fails to load */}
        {imageError && (
          <div className={styles.errorOverlay}>
            <div className={styles.cardName}>{card.name}</div>
            <div className={styles.cardAge}>Age {card.age}</div>
            <div className={styles.errorText}>Image failed to load</div>
          </div>
        )}

        {/* Removed microscope icon - using CSS hover to expand instead */}

        {card.is_achievement && imageLoaded && !imageError && (
          <div className={styles.achievementMarker}>🏆 Achievement</div>
        )}

        {/* Selection checkmark overlay - only show when selected */}
        {isSelected && (
          <div className={styles.selectionCheckmark}>
            <div className={styles.checkmarkIcon}>✓</div>
          </div>
        )}
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison function for React.memo
    // Only re-render if these specific props change
    return (
      prevProps.card?.name === nextProps.card?.name &&
      prevProps.card?.age === nextProps.card?.age &&
      prevProps.card?.color === nextProps.card?.color &&
      prevProps.card?.expansion === nextProps.card?.expansion &&
      prevProps.card?.special_icons?.length === nextProps.card?.special_icons?.length &&
      prevProps.isClickable === nextProps.isClickable &&
      prevProps.isSelected === nextProps.isSelected &&
      prevProps.isSelecting === nextProps.isSelecting &&
      prevProps.size === nextProps.size &&
      prevProps.onClick === nextProps.onClick
    );
  },
);

export default Card;

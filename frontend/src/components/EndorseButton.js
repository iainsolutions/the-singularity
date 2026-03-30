import React, { useState } from 'react';
import { Button, Tooltip, Badge } from '@mui/material';
import { Star as StarIcon, StarBorder as StarBorderIcon } from '@mui/icons-material';
import EndorseDialog from './EndorseDialog';
import styles from './EndorseButton.module.css';

/**
 * EndorseButton - Button to initiate endorse action during dogma
 *
 * Displays in the dogma action UI and opens EndorseDialog when clicked.
 * Shows tooltip with endorse requirements and availability status.
 *
 * @param {Object} props
 * @param {Object} props.dogmaCard - Card being dogma'd
 * @param {Array} props.eligibleCities - Cities that can be used for endorse
 * @param {Array} props.playerHand - Player's hand cards
 * @param {boolean} props.endorseUsedThisTurn - Whether endorse was used this turn
 * @param {boolean} props.citiesEnabled - Whether Cities expansion is enabled
 * @param {Function} props.onEndorseConfirm - Handler when endorse is confirmed (cityId, junkCardId)
 */
export default function EndorseButton({
  dogmaCard,
  eligibleCities = [],
  playerHand = [],
  endorseUsedThisTurn = false,
  citiesEnabled = false,
  onEndorseConfirm,
}) {
  const [dialogOpen, setDialogOpen] = useState(false);

  // Don't show button if Cities expansion is not enabled
  if (!citiesEnabled) {
    return null;
  }

  const canEndorse = eligibleCities.length > 0 && !endorseUsedThisTurn;
  const hasEligibleJunkCards = eligibleCities.some(city =>
    playerHand.some(card => card.age <= city.age)
  );

  const getTooltipText = () => {
    if (endorseUsedThisTurn) {
      return 'Endorse already used this turn';
    }
    if (eligibleCities.length === 0) {
      const featuredIcon = dogmaCard?.dogma_resource;
      return `No eligible cities (need top city with ${featuredIcon} icon)`;
    }
    if (!hasEligibleJunkCards) {
      const minCityAge = Math.min(...eligibleCities.map(c => c.age));
      return `No cards in hand with age ≤ ${minCityAge} to junk`;
    }
    return 'Endorse: Double your dogma effects (costs city + junk card)';
  };

  const handleClick = () => {
    if (canEndorse && hasEligibleJunkCards) {
      setDialogOpen(true);
    }
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
  };

  const handleDialogConfirm = (cityId, junkCardId) => {
    if (onEndorseConfirm) {
      onEndorseConfirm(cityId, junkCardId);
    }
    setDialogOpen(false);
  };

  return (
    <>
      <Tooltip title={getTooltipText()} arrow placement="top">
        <span>
          <Button
            variant={canEndorse ? 'contained' : 'outlined'}
            color="secondary"
            startIcon={canEndorse ? <StarIcon /> : <StarBorderIcon />}
            onClick={handleClick}
            disabled={!canEndorse || !hasEligibleJunkCards}
            className={`${styles.endorseButton} ${canEndorse ? styles.available : ''}`}
            size="large"
          >
            {endorseUsedThisTurn && (
              <Badge
                badgeContent="Used"
                color="error"
                sx={{ position: 'absolute', top: 8, right: 8 }}
              />
            )}
            Endorse
          </Button>
        </span>
      </Tooltip>

      <EndorseDialog
        open={dialogOpen}
        onClose={handleDialogClose}
        onConfirm={handleDialogConfirm}
        dogmaCard={dogmaCard}
        eligibleCities={eligibleCities}
        playerHand={playerHand}
        endorseUsedThisTurn={endorseUsedThisTurn}
      />
    </>
  );
}

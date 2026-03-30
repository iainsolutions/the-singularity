import React, { useState, useMemo } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Grid,
  Card as MuiCard,
  CardContent,
  CardActionArea,
  Chip,
  Alert,
} from '@mui/material';
import styles from './EndorseDialog.module.css';

/**
 * EndorseDialog - Modal for selecting city and junk card for endorse action
 *
 * Endorse Requirements:
 * 1. Choose a top city with the featured icon (dogma resource)
 * 2. Junk a card from hand with age <= city age
 * 3. Once per turn limitation
 *
 * @param {Object} props
 * @param {boolean} props.open - Dialog open state
 * @param {Function} props.onClose - Close handler
 * @param {Function} props.onConfirm - Confirm handler (cityId, junkCardId)
 * @param {Object} props.dogmaCard - Card being dogma'd
 * @param {Array} props.eligibleCities - Cities that can be used for endorse
 * @param {Array} props.playerHand - Player's hand cards
 * @param {boolean} props.endorseUsedThisTurn - Whether endorse was already used
 */
export default function EndorseDialog({
  open,
  onClose,
  onConfirm,
  dogmaCard,
  eligibleCities = [],
  playerHand = [],
  endorseUsedThisTurn = false,
}) {
  const [selectedCity, setSelectedCity] = useState(null);
  const [selectedJunkCard, setSelectedJunkCard] = useState(null);

  // Get featured icon from dogma card
  const featuredIcon = dogmaCard?.dogma_resource;

  // Filter eligible junk cards based on selected city
  const eligibleJunkCards = useMemo(() => {
    if (!selectedCity) return [];
    return playerHand.filter(card => card.age <= selectedCity.age);
  }, [selectedCity, playerHand]);

  const handleCitySelect = (city) => {
    setSelectedCity(city);
    setSelectedJunkCard(null); // Reset junk card selection
  };

  const handleJunkCardSelect = (card) => {
    setSelectedJunkCard(card);
  };

  const handleConfirm = () => {
    if (selectedCity && selectedJunkCard) {
      onConfirm(selectedCity.card_id, selectedJunkCard.card_id);
      handleClose();
    }
  };

  const handleClose = () => {
    setSelectedCity(null);
    setSelectedJunkCard(null);
    onClose();
  };

  const canConfirm = selectedCity && selectedJunkCard;

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="md"
      fullWidth
      className={styles.dialog}
    >
      <DialogTitle className={styles.title}>
        <Typography variant="h5" component="div">
          Endorse: {dogmaCard?.name}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Double your dogma effects by spending a city and junking a card
        </Typography>
      </DialogTitle>

      <DialogContent className={styles.content}>
        {endorseUsedThisTurn && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            You have already used Endorse this turn
          </Alert>
        )}

        {eligibleCities.length === 0 && (
          <Alert severity="error" sx={{ mb: 2 }}>
            No eligible cities found. You need a top city with {featuredIcon} icon.
          </Alert>
        )}

        {/* Step 1: Select City */}
        <Box className={styles.section}>
          <Typography variant="h6" gutterBottom>
            Step 1: Choose City
            {featuredIcon && (
              <Chip
                label={`Must have ${featuredIcon} icon`}
                size="small"
                color="primary"
                sx={{ ml: 1 }}
              />
            )}
          </Typography>

          <Grid container spacing={2}>
            {eligibleCities.map(city => (
              <Grid item xs={12} sm={6} md={4} key={city.card_id}>
                <MuiCard
                  className={`${styles.cityCard} ${
                    selectedCity?.card_id === city.card_id ? styles.selected : ''
                  }`}
                  elevation={selectedCity?.card_id === city.card_id ? 8 : 2}
                >
                  <CardActionArea onClick={() => handleCitySelect(city)}>
                    <CardContent>
                      <Typography variant="h6" component="div">
                        {city.name}
                      </Typography>
                      <Typography color="text.secondary" gutterBottom>
                        Age {city.age} • {city.color}
                      </Typography>
                      <Box className={styles.symbolList}>
                        {city.symbols?.map((symbol, idx) => (
                          <Chip
                            key={idx}
                            label={symbol}
                            size="small"
                            variant={symbol === featuredIcon ? 'filled' : 'outlined'}
                            color={symbol === featuredIcon ? 'primary' : 'default'}
                          />
                        ))}
                      </Box>
                    </CardContent>
                  </CardActionArea>
                </MuiCard>
              </Grid>
            ))}
          </Grid>
        </Box>

        {/* Step 2: Select Card to Junk */}
        {selectedCity && (
          <Box className={styles.section}>
            <Typography variant="h6" gutterBottom>
              Step 2: Choose Card to Junk
              <Chip
                label={`Age ≤ ${selectedCity.age}`}
                size="small"
                color="secondary"
                sx={{ ml: 1 }}
              />
            </Typography>

            {eligibleJunkCards.length === 0 && (
              <Alert severity="warning">
                No cards in your hand with age ≤ {selectedCity.age}
              </Alert>
            )}

            <Grid container spacing={2}>
              {eligibleJunkCards.map(card => (
                <Grid item xs={12} sm={6} md={4} key={card.card_id}>
                  <MuiCard
                    className={`${styles.junkCard} ${
                      selectedJunkCard?.card_id === card.card_id ? styles.selected : ''
                    }`}
                    elevation={selectedJunkCard?.card_id === card.card_id ? 8 : 2}
                  >
                    <CardActionArea onClick={() => handleJunkCardSelect(card)}>
                      <CardContent>
                        <Typography variant="h6" component="div">
                          {card.name}
                        </Typography>
                        <Typography color="text.secondary">
                          Age {card.age} • {card.color}
                        </Typography>
                      </CardContent>
                    </CardActionArea>
                  </MuiCard>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}

        {/* Summary */}
        {selectedCity && selectedJunkCard && (
          <Alert severity="success" className={styles.summary}>
            <Typography variant="body1" fontWeight="bold">
              Endorse Summary
            </Typography>
            <Typography variant="body2">
              • Using: <strong>{selectedCity.name}</strong> (Age {selectedCity.age})
            </Typography>
            <Typography variant="body2">
              • Junking: <strong>{selectedJunkCard.name}</strong> (Age {selectedJunkCard.age})
            </Typography>
            <Typography variant="body2" sx={{ mt: 1, fontStyle: 'italic' }}>
              Your non-demand effects will execute TWICE
            </Typography>
          </Alert>
        )}
      </DialogContent>

      <DialogActions className={styles.actions}>
        <Button onClick={handleClose} color="secondary">
          Cancel
        </Button>
        <Button
          onClick={handleConfirm}
          variant="contained"
          color="primary"
          disabled={!canConfirm || endorseUsedThisTurn}
        >
          Confirm Endorse
        </Button>
      </DialogActions>
    </Dialog>
  );
}

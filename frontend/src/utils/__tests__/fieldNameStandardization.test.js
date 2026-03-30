/**
 * Test to ensure field name mismatch bug stays fixed
 * This test validates that frontend consistently uses 'eligible_cards' field
 * and that the backend StandardInteractionBuilder format is correctly handled
 */
import { isCardEligibleForDogma } from '../gameLogic';

describe('Field Name Standardization - Prevent Regression', () => {
  const testCard = {
    card_id: 'test-card-123',
    name: 'Tools',
    age: 1,
    color: 'blue'
  };

  describe('StandardInteractionBuilder format', () => {
    test('handles direct StandardInteractionBuilder format with eligible_cards', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            eligible_cards: [
              { card_id: 'test-card-123', name: 'Tools' },
              { card_id: 'other-card', name: 'Other' }
            ]
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(true);
    });

    test('handles enhancedPendingAction format with context.eligible_cards', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          eligible_cards: [
            { card_id: 'test-card-123', name: 'Tools' },
            { card_id: 'other-card', name: 'Other' }
          ]
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(true);
    });

    test('handles nested interaction_data format with eligible_cards', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          interaction_data: {
            data: {
              eligible_cards: [
                { card_id: 'test-card-123', name: 'Tools' },
                { card_id: 'other-card', name: 'Other' }
              ]
            }
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(true);
    });
  });

  describe('Field name consistency verification', () => {
    test('rejects cards not in eligible_cards list', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            eligible_cards: [
              { card_id: 'other-card', name: 'Other' }
            ]
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(false);
    });

    test('returns false when eligible_cards is empty', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            eligible_cards: []
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(false);
    });

    test('returns false when eligible_cards field is missing', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            // No eligible_cards field - should fail fast
            some_other_field: 'value'
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(false);
    });
  });

  describe('String card IDs support', () => {
    test('handles string card IDs in eligible_cards', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            eligible_cards: ['test-card-123', 'other-card']
          }
        }
      };

      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(true);
    });

    test('matches by card name when card_id not available', () => {
      const cardWithoutId = {
        name: 'Tools',
        age: 1,
        color: 'blue'
      };

      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          data: {
            eligible_cards: ['Tools', 'Other Card']
          }
        }
      };

      const result = isCardEligibleForDogma(cardWithoutId, pendingAction);
      expect(result).toBe(true);
    });
  });

  describe('Achievement selection special case', () => {
    test('disallows hand/board card clicks during achievement selection', () => {
      const pendingAction = {
        action_type: 'dogma_v2_interaction',
        context: {
          interaction_data: {
            data: {
              type: 'select_achievement',
              eligible_cards: [
                { card_id: 'test-card-123', name: 'Tools' }
              ]
            }
          }
        }
      };

      // Even though the card is in eligible_cards, achievement selection should not allow hand/board card clicks
      const result = isCardEligibleForDogma(testCard, pendingAction);
      expect(result).toBe(false);
    });
  });
});
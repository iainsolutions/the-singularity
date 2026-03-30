/**
 * MeldSourceModal Component Tests
 *
 * Tests for the meld source selection modal (Unseen expansion).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MeldSourceModal from './MeldSourceModal';

describe('MeldSourceModal Component', () => {
  const mockSafe = {
    player_id: 'player1',
    card_count: 3,
    secret_ages: [2, 5, 7],
    cards: null,
  };

  const mockHandCards = [
    { id: 'card1', name: 'Agriculture', age: 1 },
    { id: 'card2', name: 'Tools', age: 1 },
  ];

  const defaultProps = {
    open: true,
    onClose: jest.fn(),
    onConfirm: jest.fn(),
    handCards: mockHandCards,
    safe: mockSafe,
    targetColor: null,
    loading: false,
    error: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Modal Display', () => {
    test('renders when open', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/Choose Meld Source/)).toBeInTheDocument();
    });

    test('does not render when closed', () => {
      render(<MeldSourceModal {...defaultProps} open={false} />);

      expect(screen.queryByText(/Choose Meld Source/)).not.toBeInTheDocument();
    });

    test('returns null when safe is null', () => {
      const { container } = render(<MeldSourceModal {...defaultProps} safe={null} />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Source Selection Options', () => {
    test('shows hand option', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/Meld from Hand/)).toBeInTheDocument();
    });

    test('shows safe option', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/Meld from Safe \(Reveal Secret\)/)).toBeInTheDocument();
    });

    test('shows hand card count', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/2 cards in hand/)).toBeInTheDocument();
    });

    test('shows safe secret count', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/3 secrets in Safe/)).toBeInTheDocument();
    });

    test('defaults to hand selection', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      expect(handRadio).toBeChecked();
    });
  });

  describe('Hand Selection', () => {
    test('allows selecting hand when cards available', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      fireEvent.click(handRadio);

      expect(handRadio).toBeChecked();
    });

    test('disables hand option when no cards', () => {
      render(<MeldSourceModal {...defaultProps} handCards={[]} />);

      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      expect(handRadio).toBeDisabled();
    });

    test('shows "No cards in hand" when empty', () => {
      render(<MeldSourceModal {...defaultProps} handCards={[]} />);

      expect(screen.getByText(/No cards in hand/)).toBeInTheDocument();
    });

    test('shows singular "card" for 1 card', () => {
      render(<MeldSourceModal {...defaultProps} handCards={[mockHandCards[0]]} />);

      expect(screen.getByText(/1 card in hand/)).toBeInTheDocument();
    });
  });

  describe('Safe Selection', () => {
    test('allows selecting safe when secrets available', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      expect(safeRadio).toBeChecked();
    });

    test('disables safe option when no secrets', () => {
      const emptySafe = { ...mockSafe, card_count: 0, secret_ages: [] };
      render(<MeldSourceModal {...defaultProps} safe={emptySafe} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      expect(safeRadio).toBeDisabled();
    });

    test('shows "No secrets in Safe" when empty', () => {
      const emptySafe = { ...mockSafe, card_count: 0, secret_ages: [] };
      render(<MeldSourceModal {...defaultProps} safe={emptySafe} />);

      expect(screen.getByText(/No secrets in Safe/)).toBeInTheDocument();
    });

    test('shows singular "secret" for 1 secret', () => {
      const oneSafe = { ...mockSafe, card_count: 1, secret_ages: [3] };
      render(<MeldSourceModal {...defaultProps} safe={oneSafe} />);

      expect(screen.getByText(/1 secret in Safe/)).toBeInTheDocument();
    });

    test('shows secrets grid when safe selected', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      expect(screen.getByText(/Select Secret to Reveal:/)).toBeInTheDocument();
      const secrets = screen.getAllByText(/Secret #/);
      expect(secrets).toHaveLength(3);
    });

    test('allows selecting specific secret', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[1].closest('div'));

      expect(screen.getByText(/✓ Selected/)).toBeInTheDocument();
    });
  });

  describe('Target Color Display', () => {
    test('shows target color when provided', () => {
      render(<MeldSourceModal {...defaultProps} targetColor="blue" />);

      expect(screen.getByText(/Melding to blue stack/)).toBeInTheDocument();
    });

    test('does not show target color when null', () => {
      render(<MeldSourceModal {...defaultProps} targetColor={null} />);

      expect(screen.queryByText(/Melding to/)).not.toBeInTheDocument();
    });
  });

  describe('Warning Messages', () => {
    test('shows warning when safe is selected', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      expect(screen.getByText(/Revealing a secret from your Safe will show the card to all players/)).toBeInTheDocument();
    });

    test('does not show warning when hand is selected', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      fireEvent.click(handRadio);

      expect(screen.queryByText(/Revealing a secret/)).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    test('displays error message', () => {
      const error = 'Failed to meld: Invalid card';
      render(<MeldSourceModal {...defaultProps} error={error} />);

      expect(screen.getByText(error)).toBeInTheDocument();
    });

    test('error has proper severity styling', () => {
      const { container } = render(<MeldSourceModal {...defaultProps} error="Test error" />);

      const errorAlert = container.querySelector('[class*="MuiAlert-standardError"]');
      expect(errorAlert).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    test('shows loading spinner when loading', () => {
      render(<MeldSourceModal {...defaultProps} loading={true} />);

      expect(screen.getByText(/Melding.../)).toBeInTheDocument();
    });

    test('disables buttons when loading', () => {
      render(<MeldSourceModal {...defaultProps} loading={true} />);

      const cancelButton = screen.getByText('Cancel');
      const confirmButton = screen.getByText(/Melding.../);

      expect(cancelButton).toBeDisabled();
      expect(confirmButton).toBeDisabled();
    });
  });

  describe('Confirm Button Behavior', () => {
    test('enabled for hand selection', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const confirmButton = screen.getByText(/Meld from Hand/);
      expect(confirmButton).not.toBeDisabled();
    });

    test('disabled for safe selection without secret selected', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      const confirmButton = screen.getByText(/Reveal & Meld from Safe/);
      expect(confirmButton).toBeDisabled();
    });

    test('enabled for safe selection with secret selected', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      const confirmButton = screen.getByText(/Reveal & Meld from Safe/);
      expect(confirmButton).not.toBeDisabled();
    });

    test('shows correct button text for hand', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/Meld from Hand/)).toBeInTheDocument();
    });

    test('shows correct button text for safe', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      expect(screen.getByText(/Reveal & Meld from Safe/)).toBeInTheDocument();
    });
  });

  describe('Action Callbacks', () => {
    test('Cancel button closes modal', () => {
      const mockClose = jest.fn();
      render(<MeldSourceModal {...defaultProps} onClose={mockClose} />);

      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);

      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    test('Confirm with hand calls onConfirm correctly', () => {
      const mockConfirm = jest.fn();
      render(<MeldSourceModal {...defaultProps} onConfirm={mockConfirm} />);

      const confirmButton = screen.getByText(/Meld from Hand/);
      fireEvent.click(confirmButton);

      expect(mockConfirm).toHaveBeenCalledWith('hand');
    });

    test('Confirm with safe calls onConfirm correctly', () => {
      const mockConfirm = jest.fn();
      render(<MeldSourceModal {...defaultProps} onConfirm={mockConfirm} />);

      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);

      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[1].closest('div')); // Select index 1 (age 5)

      const confirmButton = screen.getByText(/Reveal & Meld from Safe/);
      fireEvent.click(confirmButton);

      expect(mockConfirm).toHaveBeenCalledWith('safe', 1);
    });

    test('closes modal after confirm', () => {
      const mockClose = jest.fn();
      render(<MeldSourceModal {...defaultProps} onClose={mockClose} />);

      const confirmButton = screen.getByText(/Meld from Hand/);
      fireEvent.click(confirmButton);

      expect(mockClose).toHaveBeenCalled();
    });
  });

  describe('Modal Lifecycle', () => {
    test('resets selection when modal closed', () => {
      const { rerender } = render(<MeldSourceModal {...defaultProps} />);

      // Select safe and secret
      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });
      fireEvent.click(safeRadio);
      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      // Close modal
      rerender(<MeldSourceModal {...defaultProps} open={false} />);

      // Reopen modal
      rerender(<MeldSourceModal {...defaultProps} open={true} />);

      // Should default back to hand
      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      expect(handRadio).toBeChecked();
    });
  });

  describe('Accessibility', () => {
    test('uses radio buttons for source selection', () => {
      render(<MeldSourceModal {...defaultProps} />);

      const handRadio = screen.getByRole('radio', { name: /Meld from Hand/i });
      const safeRadio = screen.getByRole('radio', { name: /Meld from Safe/i });

      expect(handRadio).toBeInTheDocument();
      expect(safeRadio).toBeInTheDocument();
    });

    test('provides clear instructions', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/Choose whether to meld a card from your hand/)).toBeInTheDocument();
    });

    test('shows card counts for context', () => {
      render(<MeldSourceModal {...defaultProps} />);

      expect(screen.getByText(/2 cards in hand/)).toBeInTheDocument();
      expect(screen.getByText(/3 secrets in Safe/)).toBeInTheDocument();
    });
  });

  describe('Component Memoization', () => {
    test('component is memoized', () => {
      expect(MeldSourceModal.displayName).toBe('MeldSourceModal');
    });
  });

  describe('Edge Cases', () => {
    test('handles empty hand and empty safe', () => {
      const emptySafe = { ...mockSafe, card_count: 0, secret_ages: [] };
      render(<MeldSourceModal {...defaultProps} handCards={[]} safe={emptySafe} />);

      expect(screen.getByText(/No cards in hand/)).toBeInTheDocument();
      expect(screen.getByText(/No secrets in Safe/)).toBeInTheDocument();
    });

    test('handles safe with null secret_ages', () => {
      const nullSafe = { ...mockSafe, secret_ages: null };
      render(<MeldSourceModal {...defaultProps} safe={nullSafe} />);

      // Should handle gracefully
      expect(screen.getByText(/Choose Meld Source/)).toBeInTheDocument();
    });

    test('handles undefined handCards', () => {
      render(<MeldSourceModal {...defaultProps} handCards={undefined} />);

      expect(screen.getByText(/No cards in hand/)).toBeInTheDocument();
    });
  });
});

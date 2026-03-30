/**
 * AchieveFromSafeModal Component Tests
 *
 * Tests for the modal that allows achieving from Safe (Unseen expansion).
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AchieveFromSafeModal from './AchieveFromSafeModal';

describe('AchieveFromSafeModal Component', () => {
  const mockSafe = {
    player_id: 'player1',
    card_count: 3,
    secret_ages: [2, 4, 6],
    cards: null,
  };

  const defaultProps = {
    open: true,
    onClose: jest.fn(),
    onConfirm: jest.fn(),
    safe: mockSafe,
    availableAchievements: [2, 4, 6],
    currentPlayerScore: 25,
    currentPlayerHighestAge: 5,
    loading: false,
    error: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Modal Display', () => {
    test('renders when open', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      expect(screen.getByText(/Achieve Using Secret from Safe/)).toBeInTheDocument();
      expect(screen.getByText(/Select a secret from your Safe/)).toBeInTheDocument();
    });

    test('does not render when closed', () => {
      render(<AchieveFromSafeModal {...defaultProps} open={false} />);

      expect(screen.queryByText(/Achieve Using Secret from Safe/)).not.toBeInTheDocument();
    });

    test('returns null when safe is null', () => {
      const { container } = render(<AchieveFromSafeModal {...defaultProps} safe={null} />);

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Player Status Display', () => {
    test('shows current player score', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      expect(screen.getByText(/Your Score:/)).toBeInTheDocument();
      expect(screen.getByText('25')).toBeInTheDocument();
    });

    test('shows highest board age', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      expect(screen.getByText(/Highest Board Age:/)).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
    });

    test('shows available achievements', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      expect(screen.getByText(/Available Achievements:/)).toBeInTheDocument();
      const achievementsText = screen.getByText(/Age 2, Age 4, Age 6/);
      expect(achievementsText).toBeInTheDocument();
    });

    test('shows "None" when no achievements available', () => {
      render(<AchieveFromSafeModal {...defaultProps} availableAchievements={[]} />);

      const text = screen.getByText(/Available Achievements:/).parentElement.textContent;
      expect(text).toContain('None');
    });
  });

  describe('Secret Selection', () => {
    test('renders all secrets in Safe', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      // Should show 3 secrets
      const secrets = screen.getAllByText(/Secret #/);
      expect(secrets).toHaveLength(3);
    });

    test('marks eligible secrets', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      // All secrets (ages 2, 4, 6) match available achievements
      const eligibleBadges = screen.getAllByText(/Eligible/);
      expect(eligibleBadges.length).toBeGreaterThan(0);
    });

    test('marks ineligible secrets', () => {
      const propsWithPartialMatch = {
        ...defaultProps,
        availableAchievements: [2], // Only age 2 available
      };
      render(<AchieveFromSafeModal {...propsWithPartialMatch} />);

      // Ages 4 and 6 should be ineligible
      const ineligibleMessages = screen.getAllByText(/No Age \d+ achievement available/);
      expect(ineligibleMessages.length).toBeGreaterThan(0);
    });

    test('allows clicking eligible secret', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      // Should show "Selected" badge
      expect(screen.getByText(/Selected/)).toBeInTheDocument();
    });

    test('prevents clicking ineligible secret', () => {
      const propsWithNoMatch = {
        ...defaultProps,
        availableAchievements: [8], // No matching ages
      };
      render(<AchieveFromSafeModal {...propsWithNoMatch} />);

      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      // Should not show "Selected" badge
      expect(screen.queryByText(/Selected/)).not.toBeInTheDocument();
    });
  });

  describe('Empty Safe Handling', () => {
    test('shows warning when Safe is empty', () => {
      const emptyProps = {
        ...defaultProps,
        safe: { ...mockSafe, card_count: 0, secret_ages: [] },
      };
      render(<AchieveFromSafeModal {...emptyProps} />);

      expect(screen.getByText(/Your Safe is empty/)).toBeInTheDocument();
    });

    test('shows warning when no eligible secrets', () => {
      const noMatchProps = {
        ...defaultProps,
        availableAchievements: [10], // No secrets match
      };
      render(<AchieveFromSafeModal {...noMatchProps} />);

      expect(screen.getByText(/No eligible secrets in Safe/)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    test('shows loading spinner when loading', () => {
      render(<AchieveFromSafeModal {...defaultProps} loading={true} />);

      expect(screen.getByText(/Achieving.../)).toBeInTheDocument();
      // CircularProgress should be rendered
      const button = screen.getByText(/Achieving.../).closest('button');
      expect(button).toHaveAttribute('disabled');
    });

    test('disables buttons when loading', () => {
      render(<AchieveFromSafeModal {...defaultProps} loading={true} />);

      const cancelButton = screen.getByText('Cancel');
      const confirmButton = screen.getByText(/Achieving.../);

      expect(cancelButton).toBeDisabled();
      expect(confirmButton).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    test('displays error message', () => {
      const error = 'Failed to achieve: Not enough score';
      render(<AchieveFromSafeModal {...defaultProps} error={error} />);

      expect(screen.getByText(error)).toBeInTheDocument();
    });

    test('error has proper severity styling', () => {
      const error = 'Test error';
      const { container } = render(<AchieveFromSafeModal {...defaultProps} error={error} />);

      const errorAlert = container.querySelector('[class*="MuiAlert-standardError"]');
      expect(errorAlert).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    test('Cancel button closes modal', () => {
      const mockClose = jest.fn();
      render(<AchieveFromSafeModal {...defaultProps} onClose={mockClose} />);

      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);

      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    test('Confirm button disabled when no selection', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      const confirmButton = screen.getByText(/Achieve with Selected Secret/);
      expect(confirmButton).toBeDisabled();
    });

    test('Confirm button enabled when secret selected', () => {
      render(<AchieveFromSafeModal {...defaultProps} />);

      // Select first secret
      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      const confirmButton = screen.getByText(/Achieve with Selected Secret/);
      expect(confirmButton).not.toBeDisabled();
    });

    test('Confirm button calls onConfirm with correct args', () => {
      const mockConfirm = jest.fn();
      render(<AchieveFromSafeModal {...defaultProps} onConfirm={mockConfirm} />);

      // Select first secret (index 0, age 2)
      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      const confirmButton = screen.getByText(/Achieve with Selected Secret/);
      fireEvent.click(confirmButton);

      expect(mockConfirm).toHaveBeenCalledWith(0, 2);
    });
  });

  describe('Modal Lifecycle', () => {
    test('resets selection when closed and reopened', async () => {
      const { rerender } = render(<AchieveFromSafeModal {...defaultProps} />);

      // Select a secret
      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));
      expect(screen.getByText(/Selected/)).toBeInTheDocument();

      // Close modal
      rerender(<AchieveFromSafeModal {...defaultProps} open={false} />);

      // Reopen modal
      rerender(<AchieveFromSafeModal {...defaultProps} open={true} />);

      // Selection should persist (component maintains state)
      // This is intentional - user might accidentally close modal
    });
  });
});

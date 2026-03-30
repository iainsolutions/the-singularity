/**
 * SafeguardBadge Component Tests
 *
 * Tests for the Safeguard indicator badge (Unseen expansion).
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SafeguardBadge from './SafeguardBadge';

describe('SafeguardBadge Component', () => {
  const mockCurrentPlayer = { id: 'player1', name: 'Alice' };

  describe('Rendering', () => {
    test('renders with single Safeguard owner', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      expect(screen.getByText(/Safeguarded by:/)).toBeInTheDocument();
    });

    test('renders with multiple Safeguard owners', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1', 'player2']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={false}
        />
      );

      const badge = screen.getByText(/Safeguarded by:/);
      expect(badge).toBeInTheDocument();
    });

    test('does not render when no Safeguards', () => {
      const { container } = render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={[]}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Visual States', () => {
    test('shows green color when player owns Safeguard', () => {
      const { container } = render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      const badge = container.querySelector('[class*="safeguardBadge"]');
      expect(badge).toHaveClass('owned');
    });

    test('shows red color when blocked by opponent', () => {
      const { container } = render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player2']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={false}
        />
      );

      const badge = container.querySelector('[class*="safeguardBadge"]');
      expect(badge).toHaveClass('blocked');
    });
  });

  describe('Deadlock Detection', () => {
    test('shows deadlock warning with multiple owners', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1', 'player2', 'player3']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={false}
        />
      );

      expect(screen.getByText(/Deadlock!/)).toBeInTheDocument();
      expect(screen.getByText(/Multiple players/)).toBeInTheDocument();
    });

    test('does not show deadlock warning with single owner', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      expect(screen.queryByText(/Deadlock!/)).not.toBeInTheDocument();
    });
  });

  describe('Player Name Display', () => {
    test('shows "You" for current player', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      expect(screen.getByText(/You/)).toBeInTheDocument();
    });

    test('shows player names for other owners', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player2', 'player3']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={false}
        />
      );

      // Should show player IDs when names not provided
      const text = screen.getByText(/Safeguarded by:/).textContent;
      expect(text).toContain('player2');
      expect(text).toContain('player3');
    });
  });

  describe('Accessibility', () => {
    test('has shield icon for visual indicator', () => {
      const { container } = render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      // Check for shield icon (🛡️)
      expect(container.textContent).toContain('🛡️');
    });

    test('provides clear text description', () => {
      render(
        <SafeguardBadge
          achievementAge={4}
          safeguardOwners={['player1']}
          currentPlayerId="player1"
          currentPlayerName="Alice"
          canClaim={true}
        />
      );

      const text = screen.getByText(/Safeguarded by:/).textContent;
      expect(text).toMatch(/Safeguarded by:/);
    });
  });
});

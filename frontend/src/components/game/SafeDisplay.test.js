/**
 * SafeDisplay Component Tests
 *
 * Tests for the Safe display component (Unseen expansion).
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SafeDisplay from './SafeDisplay';

describe('SafeDisplay Component', () => {
  const mockSafe = {
    player_id: 'player1',
    card_count: 3,
    secret_ages: [2, 4, 6],
    cards: null,
  };

  describe('Rendering', () => {
    test('renders with empty Safe', () => {
      const emptySafe = { ...mockSafe, card_count: 0, secret_ages: [] };
      render(<SafeDisplay safe={emptySafe} isOwner={true} currentLimit={5} />);

      expect(screen.getByText('The Safe')).toBeInTheDocument();
      expect(screen.getByText('No secrets in Safe')).toBeInTheDocument();
      expect(screen.getByText('0/5')).toBeInTheDocument();
    });

    test('renders owner view with secret ages', () => {
      render(<SafeDisplay safe={mockSafe} isOwner={true} currentLimit={5} />);

      expect(screen.getByText('The Safe')).toBeInTheDocument();
      expect(screen.getByText('3/5')).toBeInTheDocument();
      // Should show 3 SecretCardBack components
      const secretElements = screen.getAllByText(/Secret #/);
      expect(secretElements).toHaveLength(3);
    });

    test('renders opponent view without ages', () => {
      const opponentSafe = { ...mockSafe, secret_ages: null };
      render(<SafeDisplay safe={opponentSafe} isOwner={false} currentLimit={5} />);

      expect(screen.getByText('The Safe')).toBeInTheDocument();
      expect(screen.getByText('3/5')).toBeInTheDocument();
      // Opponents should see card backs but no age info
    });

    test('renders null when Safe is null', () => {
      const { container } = render(<SafeDisplay safe={null} isOwner={true} currentLimit={5} />);
      expect(container.firstChild).toBeNull();
    });
  });

  describe('Safe Limit Indicator', () => {
    test('shows green color when below limit', () => {
      render(<SafeDisplay safe={mockSafe} isOwner={true} currentLimit={5} />);

      const limitIndicator = screen.getByText('3/5');
      expect(limitIndicator).toHaveStyle({ color: '#4caf50' });
    });

    test('shows red color when at limit', () => {
      const fullSafe = { ...mockSafe, card_count: 5, secret_ages: [1, 2, 3, 4, 5] };
      render(<SafeDisplay safe={fullSafe} isOwner={true} currentLimit={5} />);

      const limitIndicator = screen.getByText('5/5');
      expect(limitIndicator).toHaveStyle({ color: '#ff5252' });
    });

    test('shows red color when over limit', () => {
      const overLimit = { ...mockSafe, card_count: 6, secret_ages: [1, 2, 3, 4, 5, 6] };
      render(<SafeDisplay safe={overLimit} isOwner={true} currentLimit={5} />);

      const limitIndicator = screen.getByText('6/5');
      expect(limitIndicator).toHaveStyle({ color: '#ff5252' });
    });

    test('shows tooltip on hover', () => {
      render(<SafeDisplay safe={mockSafe} isOwner={true} currentLimit={5} />);

      const limitIndicator = screen.getByText('3/5');
      expect(limitIndicator.parentElement).toHaveAttribute('title');
    });
  });

  describe('Limit Warning', () => {
    test('shows warning when owner is at limit', () => {
      const fullSafe = { ...mockSafe, card_count: 5, secret_ages: [1, 2, 3, 4, 5] };
      render(<SafeDisplay safe={fullSafe} isOwner={true} currentLimit={5} />);

      expect(screen.getByText(/Safe is at capacity/)).toBeInTheDocument();
    });

    test('does not show warning when below limit', () => {
      render(<SafeDisplay safe={mockSafe} isOwner={true} currentLimit={5} />);

      expect(screen.queryByText(/Safe is at capacity/)).not.toBeInTheDocument();
    });

    test('does not show warning to opponents even at limit', () => {
      const fullSafe = { ...mockSafe, card_count: 5, secret_ages: null };
      render(<SafeDisplay safe={fullSafe} isOwner={false} currentLimit={5} />);

      expect(screen.queryByText(/Safe is at capacity/)).not.toBeInTheDocument();
    });
  });

  describe('Click Handling', () => {
    test('calls onSecretClick when secret is clicked (owner)', () => {
      const mockOnClick = jest.fn();
      render(
        <SafeDisplay
          safe={mockSafe}
          isOwner={true}
          currentLimit={5}
          onSecretClick={mockOnClick}
        />
      );

      // Click first secret (index 0, age 2)
      const secrets = screen.getAllByText(/Secret #/);
      fireEvent.click(secrets[0].closest('div'));

      expect(mockOnClick).toHaveBeenCalledWith(0, 2);
    });

    test('does not call onClick for opponents', () => {
      const mockOnClick = jest.fn();
      const opponentSafe = { ...mockSafe, secret_ages: null };
      render(
        <SafeDisplay
          safe={opponentSafe}
          isOwner={false}
          currentLimit={5}
          onSecretClick={mockOnClick}
        />
      );

      // Opponents can't click secrets
      expect(mockOnClick).not.toHaveBeenCalled();
    });
  });

  describe('Splay-based Limit', () => {
    test.each([
      [5, 'None'],
      [6, 'Left'],
      [7, 'Right'],
      [8, 'Up'],
      [9, 'Aslant'],
    ])('displays correct limit of %i for %s splay', (limit, splayType) => {
      render(<SafeDisplay safe={mockSafe} isOwner={true} currentLimit={limit} />);

      expect(screen.getByText(`3/${limit}`)).toBeInTheDocument();
    });
  });
});

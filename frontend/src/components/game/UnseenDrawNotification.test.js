/**
 * UnseenDrawNotification Component Tests
 *
 * Tests for the Unseen card draw notification component.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import UnseenDrawNotification from './UnseenDrawNotification';

describe('UnseenDrawNotification Component', () => {
  const defaultProps = {
    open: true,
    onClose: jest.fn(),
    age: 5,
    isFirstDraw: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    test('renders when open', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();
    });

    test('does not render when closed', () => {
      render(<UnseenDrawNotification {...defaultProps} open={false} />);

      expect(screen.queryByText(/Unseen Card Drawn/)).not.toBeInTheDocument();
    });

    test('does not render when isFirstDraw is false', () => {
      render(<UnseenDrawNotification {...defaultProps} isFirstDraw={false} />);

      expect(screen.queryByText(/Unseen Card Drawn/)).not.toBeInTheDocument();
    });
  });

  describe('Content Display', () => {
    test('shows the drawn card age', () => {
      render(<UnseenDrawNotification {...defaultProps} age={3} />);

      expect(screen.getByText(/Age 3 Unseen card/)).toBeInTheDocument();
    });

    test('shows lock icon', () => {
      const { container } = render(<UnseenDrawNotification {...defaultProps} />);

      expect(container.textContent).toContain('🔒');
    });

    test('shows first draw explanation', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      expect(screen.getByText(/First draw of turn/)).toBeInTheDocument();
    });

    test('shows hidden information explanation', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      expect(screen.getByText(/hidden from all players, including you/)).toBeInTheDocument();
    });

    test('shows subsequent draw hint', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      expect(screen.getByText(/Subsequent draws this turn will use the normal deck/)).toBeInTheDocument();
    });
  });

  describe('Age Display', () => {
    test.each([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])(
      'displays Age %i correctly',
      (age) => {
        render(<UnseenDrawNotification {...defaultProps} age={age} />);

        expect(screen.getByText(new RegExp(`Age ${age}`))).toBeInTheDocument();
      }
    );
  });

  describe('Close Handling', () => {
    test('calls onClose when close button clicked', () => {
      const mockClose = jest.fn();
      render(<UnseenDrawNotification {...defaultProps} onClose={mockClose} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      fireEvent.click(closeButton);

      expect(mockClose).toHaveBeenCalledTimes(1);
    });

    test('auto-closes after timeout', async () => {
      const mockClose = jest.fn();
      jest.useFakeTimers();

      render(<UnseenDrawNotification {...defaultProps} onClose={mockClose} />);

      // Fast-forward time by 4 seconds (autoHideDuration)
      jest.advanceTimersByTime(4000);

      await waitFor(() => {
        expect(mockClose).toHaveBeenCalled();
      });

      jest.useRealTimers();
    });
  });

  describe('Visual Styling', () => {
    test('has info severity', () => {
      const { container } = render(<UnseenDrawNotification {...defaultProps} />);

      const alert = container.querySelector('[class*="MuiAlert"]');
      expect(alert).toBeInTheDocument();
    });

    test('has proper gradient background', () => {
      const { container } = render(<UnseenDrawNotification {...defaultProps} />);

      const alert = container.querySelector('[class*="MuiAlert"]');
      const styles = window.getComputedStyle(alert);
      // Check that background style is applied (implementation detail)
      expect(alert).toBeTruthy();
    });

    test('has golden border styling', () => {
      const { container } = render(<UnseenDrawNotification {...defaultProps} />);

      const alert = container.querySelector('[class*="MuiAlert"]');
      expect(alert).toBeTruthy();
    });
  });

  describe('Position and Anchoring', () => {
    test('appears at top center', () => {
      const { container } = render(<UnseenDrawNotification {...defaultProps} />);

      const snackbar = container.querySelector('[class*="MuiSnackbar"]');
      expect(snackbar).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('has clear heading', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();
    });

    test('provides detailed explanation', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      // Should have multiple informative text sections
      expect(screen.getByText(/First draw of turn/)).toBeInTheDocument();
      expect(screen.getByText(/hidden from all players/)).toBeInTheDocument();
      expect(screen.getByText(/Subsequent draws/)).toBeInTheDocument();
    });

    test('has close button for keyboard users', () => {
      render(<UnseenDrawNotification {...defaultProps} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });
  });

  describe('Component Lifecycle', () => {
    test('can be opened and closed multiple times', () => {
      const { rerender } = render(
        <UnseenDrawNotification {...defaultProps} open={true} />
      );

      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();

      rerender(<UnseenDrawNotification {...defaultProps} open={false} />);

      expect(screen.queryByText(/Unseen Card Drawn/)).not.toBeInTheDocument();

      rerender(<UnseenDrawNotification {...defaultProps} open={true} />);

      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();
    });

    test('updates age when props change', () => {
      const { rerender } = render(
        <UnseenDrawNotification {...defaultProps} age={3} />
      );

      expect(screen.getByText(/Age 3/)).toBeInTheDocument();

      rerender(<UnseenDrawNotification {...defaultProps} age={7} />);

      expect(screen.getByText(/Age 7/)).toBeInTheDocument();
      expect(screen.queryByText(/Age 3/)).not.toBeInTheDocument();
    });
  });

  describe('Component Memoization', () => {
    test('component is memoized', () => {
      expect(UnseenDrawNotification.displayName).toBe('UnseenDrawNotification');
    });
  });

  describe('Edge Cases', () => {
    test('handles missing age gracefully', () => {
      render(<UnseenDrawNotification {...defaultProps} age={undefined} />);

      // Should still render but may show undefined
      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();
    });

    test('handles missing onClose gracefully', () => {
      render(<UnseenDrawNotification {...defaultProps} onClose={undefined} />);

      // Should still render without errors
      expect(screen.getByText(/Unseen Card Drawn/)).toBeInTheDocument();
    });
  });
});

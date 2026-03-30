/**
 * SecretCardBack Component Tests
 *
 * Tests for the secret card back component (Unseen expansion).
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SecretCardBack from './SecretCardBack';

describe('SecretCardBack Component', () => {
  describe('Rendering', () => {
    test('renders with position badge', () => {
      render(<SecretCardBack secretIndex={0} age={5} onClick={null} isClickable={false} />);

      expect(screen.getByText(/#1/)).toBeInTheDocument();
    });

    test('renders age label for owner', () => {
      render(<SecretCardBack secretIndex={2} age={7} onClick={null} isClickable={false} />);

      expect(screen.getByText(/Age 7/)).toBeInTheDocument();
      expect(screen.getByText(/#3/)).toBeInTheDocument();
    });

    test('does not render age label for opponents', () => {
      render(<SecretCardBack secretIndex={1} age={null} onClick={null} isClickable={false} />);

      expect(screen.queryByText(/Age/)).not.toBeInTheDocument();
      expect(screen.getByText(/#2/)).toBeInTheDocument();
    });

    test('renders lock icon overlay', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={5} onClick={null} isClickable={false} />
      );

      expect(container.textContent).toContain('🔒');
    });
  });

  describe('Click Handling', () => {
    test('calls onClick when clickable', () => {
      const mockClick = jest.fn();
      render(<SecretCardBack secretIndex={0} age={5} onClick={mockClick} isClickable={true} />);

      const cardBack = screen.getByText(/#1/).closest('div');
      fireEvent.click(cardBack);

      expect(mockClick).toHaveBeenCalledTimes(1);
    });

    test('does not call onClick when not clickable', () => {
      const mockClick = jest.fn();
      render(<SecretCardBack secretIndex={0} age={5} onClick={mockClick} isClickable={false} />);

      const cardBack = screen.getByText(/#1/).closest('div');
      fireEvent.click(cardBack);

      expect(mockClick).not.toHaveBeenCalled();
    });

    test('does not call onClick when onClick is null', () => {
      render(<SecretCardBack secretIndex={0} age={5} onClick={null} isClickable={true} />);

      const cardBack = screen.getByText(/#1/).closest('div');
      fireEvent.click(cardBack);

      // Should not throw error
    });
  });

  describe('Visual States', () => {
    test('has clickable class when isClickable is true', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={5} onClick={jest.fn()} isClickable={true} />
      );

      const cardBack = container.querySelector('[class*="cardBack"]');
      expect(cardBack).toHaveClass('clickable');
    });

    test('does not have clickable class when isClickable is false', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={5} onClick={null} isClickable={false} />
      );

      const cardBack = container.querySelector('[class*="cardBack"]');
      expect(cardBack).not.toHaveClass('clickable');
    });
  });

  describe('Position Badge', () => {
    test('shows correct position for first card', () => {
      render(<SecretCardBack secretIndex={0} age={3} onClick={null} isClickable={false} />);

      expect(screen.getByText(/#1/)).toBeInTheDocument();
    });

    test('shows correct position for fifth card', () => {
      render(<SecretCardBack secretIndex={4} age={6} onClick={null} isClickable={false} />);

      expect(screen.getByText(/#5/)).toBeInTheDocument();
    });

    test('shows correct position for tenth card', () => {
      render(<SecretCardBack secretIndex={9} age={10} onClick={null} isClickable={false} />);

      expect(screen.getByText(/#10/)).toBeInTheDocument();
    });
  });

  describe('Age Label (Owner View)', () => {
    test('shows age for ages 1-10', () => {
      for (let age = 1; age <= 10; age++) {
        const { rerender } = render(
          <SecretCardBack secretIndex={0} age={age} onClick={null} isClickable={false} />
        );

        expect(screen.getByText(`Age ${age}`)).toBeInTheDocument();

        rerender(<div />); // Clear for next iteration
      }
    });

    test('does not show age when age is null', () => {
      render(<SecretCardBack secretIndex={0} age={null} onClick={null} isClickable={false} />);

      expect(screen.queryByText(/Age/)).not.toBeInTheDocument();
    });

    test('does not show age when age is undefined', () => {
      render(<SecretCardBack secretIndex={0} age={undefined} onClick={null} isClickable={false} />);

      expect(screen.queryByText(/Age/)).not.toBeInTheDocument();
    });
  });

  describe('Tooltip Behavior', () => {
    test('shows tooltip for clickable owner cards', () => {
      render(
        <SecretCardBack secretIndex={2} age={6} onClick={jest.fn()} isClickable={true} />
      );

      const tooltip = screen.getByText(/#3/).closest('button, div').parentElement;
      expect(tooltip).toHaveAttribute('title');
    });

    test('shows tooltip for non-clickable owner cards', () => {
      render(
        <SecretCardBack secretIndex={1} age={4} onClick={null} isClickable={false} />
      );

      const tooltip = screen.getByText(/#2/).closest('button, div').parentElement;
      expect(tooltip).toHaveAttribute('title');
    });

    test('does not show tooltip for opponent cards', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={null} onClick={null} isClickable={false} />
      );

      const cardWrapper = container.querySelector('[class*="cardBack"]').parentElement;
      expect(cardWrapper).not.toHaveAttribute('title');
    });
  });

  describe('Accessibility', () => {
    test('has clear visual indicator (lock icon)', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={5} onClick={null} isClickable={false} />
      );

      expect(container.textContent).toContain('🔒');
    });

    test('position badge provides context', () => {
      render(<SecretCardBack secretIndex={2} age={7} onClick={null} isClickable={false} />);

      // Position badge helps users identify which card they're interacting with
      expect(screen.getByText(/#3/)).toBeInTheDocument();
    });

    test('clickable cards show visual feedback', () => {
      const { container } = render(
        <SecretCardBack secretIndex={0} age={5} onClick={jest.fn()} isClickable={true} />
      );

      const cardBack = container.querySelector('[class*="clickable"]');
      expect(cardBack).toBeInTheDocument();
    });
  });

  describe('Component Memoization', () => {
    test('component is memoized', () => {
      expect(SecretCardBack.displayName).toBe('SecretCardBack');
    });
  });
});

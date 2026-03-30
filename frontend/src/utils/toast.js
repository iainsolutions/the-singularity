/**
 * Toast notification utility
 *
 * Usage:
 * import { showToast } from '../utils/toast';
 *
 * showToast('City drawn!', 'city');
 * showToast('Error occurred', 'error', 5000);
 */

export const showToast = (message, type = 'info', duration = 3000) => {
  const event = new CustomEvent('showToast', {
    detail: { message, type, duration }
  });
  window.dispatchEvent(event);
};

// Convenience methods
export const showCityDrawToast = (cityName, reason) => {
  const reasonText = reason === 'new_color' ? 'new color' : 'new splay direction';
  showToast(`🏙️ Drew city: ${cityName} (${reasonText})`, 'city', 4000);
};

export const showInfoToast = (message, duration) => {
  showToast(message, 'info', duration);
};

export const showSuccessToast = (message, duration) => {
  showToast(message, 'success', duration);
};

export const showWarningToast = (message, duration) => {
  showToast(message, 'warning', duration);
};

export const showErrorToast = (message, duration) => {
  showToast(message, 'error', duration);
};

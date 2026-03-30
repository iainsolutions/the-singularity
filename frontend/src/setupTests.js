import "@testing-library/jest-dom";
import { vi } from "vitest";

// Mock axios globally
vi.mock("axios", () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: {} })),
    get: vi.fn(() => Promise.resolve({ data: {} })),
  },
}));

// Mock WebSocket globally
global.WebSocket = vi.fn(() => ({
  onopen: null,
  onmessage: null,
  onclose: null,
  onerror: null,
  close: vi.fn(),
  send: vi.fn(),
}));

// Mock IntersectionObserver for Card component tests
global.IntersectionObserver = class IntersectionObserver {
  constructor(callback, options) {
    this.callback = callback;
    this.options = options;
  }

  observe(target) {
    // Immediately trigger callback to simulate element being in view
    this.callback([
      {
        isIntersecting: true,
        target,
        intersectionRatio: 1,
        boundingClientRect: {},
        intersectionRect: {},
        rootBounds: {},
        time: Date.now(),
      },
    ]);
  }

  unobserve() {
    // No-op
  }

  disconnect() {
    // No-op
  }
};

// Mock image loading behavior for Card tests
Object.defineProperty(HTMLImageElement.prototype, "src", {
  set(src) {
    this._src = src;
    // Simulate immediate load for test images
    if (src && src.includes("/cards/")) {
      setTimeout(() => {
        if (this.onload) {
          this.onload(new Event("load"));
        }
      }, 0);
    }
  },
  get() {
    return this._src;
  },
});

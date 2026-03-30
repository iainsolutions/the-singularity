import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
    coverage: {
      provider: "v8",
      reportsDirectory: "coverage",
      reporter: ["text", "lcov", "html"],
      include: ["src/**/*.{js,jsx}"],
      exclude: [
        "**/__mocks__/**",
        "src/setupTests.js",
        "node_modules/**",
        "dist/**",
        "build/**",
      ],
    },
  },
  esbuild: {
    loader: "jsx",
    include: /src\/.*\.js$/,
    exclude: [],
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        ".js": "jsx",
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ws/, ""),
      },
    },
  },
  resolve: {
    extensions: [".js", ".jsx", ".json"],
  },
  build: {
    outDir: "build",
    sourcemap: true,
  },
});

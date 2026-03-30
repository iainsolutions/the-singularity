import { createTheme } from "@mui/material/styles";

// Innovation game theme with cohesive color scheme
const theme = createTheme({
  palette: {
    mode: "light",
    secondary: {
      main: "#5d4037", // Brown secondary for earth/history theme
      light: "#8d6e63",
      dark: "#3e2723",
      contrastText: "#ffffff",
    },
    background: {
      default: "#f8f9fa", // Light gray background
      paper: "#ffffff",
    },
    // Custom surface colors for components
    text: {
      primary: "#212121",
      secondary: "#666666",
    },
    divider: "rgba(0, 0, 0, 0.12)",
    // Game-specific colors
    gameColors: {
      blue: "#1976d2",
      red: "#d32f2f",
      green: "#388e3c",
      yellow: "#f57c00",
      purple: "#7b1fa2",
    },
    // Status colors
    success: {
      main: "#4caf50",
      light: "#81c784",
      dark: "#388e3c",
      50: "#e8f5e8",
      200: "#a5d6a7",
    },
    warning: {
      main: "#ff9800",
      light: "#ffb74d",
      dark: "#f57c00",
      50: "#fff3e0",
      200: "#ffcc02",
      800: "#e65100",
    },
    error: {
      main: "#f44336",
      light: "#e57373",
      dark: "#d32f2f",
      50: "#ffebee",
      200: "#ef9a9a",
    },
    info: {
      main: "#2196f3",
      light: "#64b5f6",
      dark: "#1976d2",
      50: "#e3f2fd",
      200: "#90caf9",
    },
    primary: {
      main: "#4a90e2", // Pale blue
      light: "#7bb3f0",
      dark: "#2e69b3",
      contrastText: "#ffffff",
      50: "#e8f2fd",
      200: "#90c5f5",
    },
  },
  typography: {
    fontFamily: [
      "-apple-system",
      "BlinkMacSystemFont",
      '"Segoe UI"',
      "Roboto",
      '"Helvetica Neue"',
      "Arial",
      "sans-serif",
    ].join(","),
    h1: {
      fontSize: "2.5rem",
      fontWeight: 600,
      color: "#4a90e2",
    },
    h2: {
      fontSize: "2rem",
      fontWeight: 600,
      color: "#4a90e2",
    },
    h3: {
      fontSize: "1.5rem",
      fontWeight: 600,
      color: "#4a90e2",
    },
    h4: {
      fontSize: "1.25rem",
      fontWeight: 600,
      color: "#212121",
    },
    h5: {
      fontSize: "1.1rem",
      fontWeight: 500,
      color: "#212121",
    },
    h6: {
      fontSize: "1rem",
      fontWeight: 500,
      color: "#212121",
    },
    body1: {
      fontSize: "1rem",
      lineHeight: 1.5,
      color: "#212121",
    },
    body2: {
      fontSize: "0.875rem",
      lineHeight: 1.4,
      color: "#666666",
    },
    button: {
      fontWeight: 600,
      textTransform: "none", // Don't uppercase buttons
    },
  },
  spacing: 8, // Base spacing unit (8px)
  shape: {
    borderRadius: 8, // Rounded corners
  },
  components: {
    // Button styling
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: "none",
          fontWeight: 600,
          boxShadow: "none",
          padding: "8px 16px",
          minHeight: "36px",
          transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
          "&:hover": {
            boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          },
          "&:focus-visible": {
            outline: "3px solid",
            outlineColor: "currentColor",
            outlineOffset: "2px",
          },
          "&:disabled": {
            opacity: 0.6,
            cursor: "not-allowed",
          },
        },
        contained: {
          "&:hover": {
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
          },
          "&:active": {
            transform: "translateY(1px)",
          },
        },
        outlined: {
          "&:hover": {
            transform: "translateY(-1px)",
          },
          "&:active": {
            transform: "translateY(0px)",
          },
        },
        small: {
          padding: "6px 12px",
          fontSize: "0.875rem",
        },
        medium: {
          padding: "8px 16px",
          fontSize: "1rem",
        },
        large: {
          padding: "12px 24px",
          fontSize: "1.125rem",
        },
      },
      variants: [
        {
          props: { variant: "action" },
          style: {
            borderWidth: "2px",
            fontWeight: 700,
            "&:hover": {
              borderWidth: "2px",
              transform: "translateY(-2px)",
              boxShadow: "0 4px 16px rgba(0,0,0,0.2)",
            },
          },
        },
      ],
    },
    // Paper (cards, panels) styling
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
        elevation1: {
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
        },
        elevation2: {
          boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
        },
        elevation3: {
          boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        },
      },
    },
    // Card styling
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
          "&:hover": {
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          },
        },
      },
    },
    // Chip styling (for tags, counters)
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 16,
        },
      },
    },
    // Typography adjustments
    MuiTypography: {
      styleOverrides: {
        root: {
          color: "inherit",
        },
      },
    },
  },
  // Custom breakpoints for responsive design
  breakpoints: {
    values: {
      xs: 0,
      sm: 600,
      md: 900,
      lg: 1200,
      xl: 1536,
    },
  },
  // Custom mixins for game layout
  mixins: {
    gameContainer: {
      padding: "16px",
      maxWidth: "100vw",
      margin: "0 auto",
      "@media (max-width: 600px)": {
        padding: "8px",
      },
    },
    cardStack: {
      position: "relative",
      minHeight: "120px",
      "& .card:not(:last-child)": {
        position: "absolute",
        opacity: 0.8,
        transform: "scale(0.95)",
      },
    },
    playerBoard: {
      backgroundColor: "#ffffff",
      border: "1px solid rgba(0,0,0,0.12)",
      borderRadius: "8px",
      padding: "16px",
      margin: "8px 0",
      "@media (max-width: 600px)": {
        padding: "12px",
        margin: "4px 0",
      },
    },
    // Accessibility helpers
    srOnly: {
      position: "absolute",
      width: "1px",
      height: "1px",
      padding: 0,
      margin: "-1px",
      overflow: "hidden",
      clip: "rect(0, 0, 0, 0)",
      border: 0,
    },
    // High contrast mode support
    "@media (prefers-contrast: high)": {
      "& .MuiButton-outlined": {
        borderWidth: "3px !important",
      },
      "& .MuiChip-outlined": {
        borderWidth: "2px !important",
      },
    },
    // Reduced motion support
    "@media (prefers-reduced-motion: reduce)": {
      "& *": {
        transition: "none !important",
        animation: "none !important",
      },
    },
  },
});

export default theme;

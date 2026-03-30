import { memo } from "react";
import { Box, Container, useTheme, useMediaQuery } from "@mui/material";

/**
 * ResponsiveGameLayout - Provides consistent responsive layout for game components
 * Handles mobile, tablet, and desktop layouts with proper spacing and navigation
 */
const ResponsiveGameLayout = memo(function ResponsiveGameLayout({
  header,
  actions,
  achievements,
  mainContent,
  sideContent,
  children,
}) {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const isTablet = useMediaQuery(theme.breakpoints.between("md", "lg"));

  return (
    <Container
      maxWidth="xl"
      sx={{
        px: { xs: 1, sm: 2, md: 3 },
        py: { xs: 1, sm: 2 },
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header Section */}
      {header && (
        <Box
          sx={{
            mb: { xs: 1, sm: 2 },
            flexShrink: 0,
          }}
        >
          {header}
        </Box>
      )}

      {/* Actions Panel */}
      {actions && (
        <Box
          sx={{
            mb: { xs: 1.5, sm: 2 },
            flexShrink: 0,
          }}
        >
          {actions}
        </Box>
      )}

      {/* Achievements Row */}
      {achievements && (
        <Box
          sx={{
            mb: { xs: 1.5, sm: 2 },
            flexShrink: 0,
            display: "flex",
            justifyContent: "center",
            overflow: "hidden",
          }}
        >
          {achievements}
        </Box>
      )}

      {/* Main Content Area */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: { xs: "column", lg: "row" },
          gap: { xs: 1, sm: 2, lg: 3 },
          minHeight: 0, // Allow flex children to shrink
        }}
      >
        {/* Main Game Content */}
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {mainContent}
        </Box>

        {/* Side Content (Action Log, etc.) */}
        {sideContent && (
          <Box
            sx={{
              width: { xs: "100%", lg: "300px" },
              flexShrink: 0,
              maxHeight: { xs: "300px", lg: "100%" },
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {sideContent}
          </Box>
        )}
      </Box>

      {/* Additional children content */}
      {children && <Box sx={{ mt: "auto", pt: 2 }}>{children}</Box>}
    </Container>
  );
});

export default ResponsiveGameLayout;

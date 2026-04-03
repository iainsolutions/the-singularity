import { memo, useState, useEffect, useRef } from "react";
import { Box, Typography } from "@mui/material";
import { fetchLore } from "../../services/loreService";

const ERA_COLORS = {
  1: "#8B7355",
  2: "#4A6741",
  3: "#5B4A8A",
  4: "#8A5A3A",
  5: "#3A5A8A",
  6: "#6A3A3A",
  7: "#2A6A6A",
  8: "#4A4A7A",
  9: "#7A3A5A",
  10: "#1A1A4A",
};

const EraLoreBanner = memo(function EraLoreBanner({ currentAge }) {
  const [eraLore, setEraLore] = useState({});
  const prevAgeRef = useRef(currentAge);
  const [animateIn, setAnimateIn] = useState(false);

  useEffect(() => {
    fetchLore().then((data) => {
      setEraLore(data.era_lore || {});
    });
  }, []);

  // Animate when era changes
  useEffect(() => {
    if (prevAgeRef.current !== currentAge && currentAge) {
      setAnimateIn(true);
      const timer = setTimeout(() => setAnimateIn(false), 1500);
      prevAgeRef.current = currentAge;
      return () => clearTimeout(timer);
    }
  }, [currentAge]);

  const era = eraLore[String(currentAge)];
  if (!era || !currentAge) return null;

  const color = ERA_COLORS[currentAge] || "#3A3A5A";

  return (
    <Box
      sx={{
        background: `linear-gradient(135deg, ${color}22 0%, ${color}11 100%)`,
        border: `1px solid ${color}33`,
        borderRadius: 1,
        px: 2,
        py: 0.75,
        mb: 1,
        transition: "all 0.3s ease",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <Typography
          variant="caption"
          sx={{
            fontFamily: "'Orbitron', sans-serif",
            fontWeight: 700,
            color: color,
            letterSpacing: 1,
            fontSize: "0.7rem",
            opacity: 0.9,
          }}
        >
          ERA {currentAge}
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontStyle: "italic",
            color: `${color}CC`,
            fontSize: "0.7rem",
          }}
        >
          {era.name}
        </Typography>
      </Box>
      <Typography
        variant="body2"
        sx={{
          color: `${color}AA`,
          fontSize: "0.72rem",
          lineHeight: 1.5,
          mt: 0.5,
          fontStyle: "italic",
          animation: animateIn ? "loreFadeIn 1s ease-in" : "none",
          "@keyframes loreFadeIn": {
            "0%": { opacity: 0, transform: "translateY(-4px)" },
            "100%": { opacity: 1, transform: "translateY(0)" },
          },
        }}
      >
        {era.lore}
      </Typography>
    </Box>
  );
});

export default EraLoreBanner;

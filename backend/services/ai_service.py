"""
AI Service Manager

Manages AI player agents across all games.
"""

import os

from logging_config import get_logger

from services.ai_player_agent import AIPlayerAgent, fetch_available_models
from services.ai_providers.model_config import (
    get_difficulty_model_map,
    get_fallback_model,
    get_supported_difficulties,
)

logger = get_logger(__name__)


class AIService:
    """Manages AI player agents across games"""

    def __init__(self):
        self.agents: dict[str, AIPlayerAgent] = {}  # player_id -> agent

        # Check which providers have API keys configured
        self.provider_api_keys = {}

        # Check for Anthropic API key
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.provider_api_keys["anthropic"] = anthropic_key

        # Check for OpenAI API key
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.provider_api_keys["openai"] = openai_key

        # Check for Gemini API key
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            self.provider_api_keys["gemini"] = gemini_key

        # Check for Ollama (free local LLM)
        ollama_enabled = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
        if ollama_enabled:
            # Ollama uses a placeholder API key
            self.provider_api_keys["ollama"] = os.getenv("OLLAMA_API_KEY", "ollama")
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            logger.info(f"Ollama free local LLM enabled (endpoint: {ollama_url})")

        # Check if AI is globally enabled
        ai_enabled = os.getenv("AI_ENABLED", "true").lower() == "true"

        # Service is enabled if at least one provider has a key
        self.enabled = bool(self.provider_api_keys) and ai_enabled

        # Legacy: AI_PROVIDER for backward compatibility (optional now)
        self.default_provider = os.getenv("AI_PROVIDER", "").lower()
        if not self.default_provider and self.provider_api_keys:
            # No default set, use first available provider
            self.default_provider = sorted(self.provider_api_keys.keys())[0]

        if not self.enabled:
            if not self.provider_api_keys:
                logger.warning(
                    "AI service disabled: no API keys configured "
                    "(set ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, or enable OLLAMA_ENABLED=true)"
                )
            else:
                logger.warning("AI service disabled: AI_ENABLED=false")
        else:
            # Use debug level to avoid exposing provider configuration in logs
            providers_list = ", ".join(sorted(self.provider_api_keys.keys()))
            logger.info(f"AI service initialized with {len(self.provider_api_keys)} provider(s)")
            logger.debug(f"Available AI providers: {providers_list}")

    async def initialize_models(self):
        """
        Fetch available models from all configured providers.
        Call this once at application startup.
        """
        if not self.enabled:
            return

        # Validate cost monitor has all difficulty levels configured
        from services.ai_cost_monitor import cost_monitor

        valid_difficulties = get_supported_difficulties()
        cost_monitor.validate_difficulty_levels(valid_difficulties)

        # Fetch models for all configured providers
        successful_providers = []
        for provider_name, api_key in self.provider_api_keys.items():
            logger.info(f"Fetching available models from {provider_name} provider...")
            try:
                await fetch_available_models(api_key, provider_name=provider_name)
                successful_providers.append(provider_name)
            except Exception as e:
                logger.error(f"Failed to initialize {provider_name} provider: {e}")

        # If all providers fail, disable the service
        if not successful_providers:
            logger.error("All AI providers failed to initialize - disabling AI service")
            self.enabled = False
        elif len(successful_providers) < len(self.provider_api_keys):
            logger.warning(
                f"Some providers failed to initialize. "
                f"Available: {', '.join(successful_providers)}"
            )

    def create_agent(
        self, player_id: str, difficulty: str, config: dict | None = None
    ) -> AIPlayerAgent:
        """Create new AI agent for player"""
        if not self.enabled:
            raise RuntimeError(
                "AI service not enabled. Set ANTHROPIC_API_KEY or OPENAI_API_KEY and AI_ENABLED=true"
            )

        # Validate difficulty (8 levels)
        valid_difficulties = get_supported_difficulties()
        if difficulty not in valid_difficulties:
            raise ValueError(
                f"Invalid difficulty: {difficulty}. "
                f"Must be one of: {valid_difficulties}"
            )

        # Determine which provider to use
        agent_config = dict(config or {})
        provider_name = agent_config.get("provider", self.default_provider)

        # Validate provider has API key
        if provider_name not in self.provider_api_keys:
            available = ", ".join(sorted(self.provider_api_keys.keys()))
            raise ValueError(
                f"Provider '{provider_name}' not configured. "
                f"Available providers: {available}"
            )

        # Get API key for this provider
        api_key = self.provider_api_keys[provider_name]

        # Set provider in config
        agent_config["provider"] = provider_name

        agent = AIPlayerAgent(
            player_id=player_id,
            difficulty=difficulty,
            api_key=api_key,
            config=agent_config,
        )

        self.agents[player_id] = agent
        logger.info(f"Created AI agent: player_id={player_id}, difficulty={difficulty}")

        return agent

    def get_agent(self, player_id: str) -> AIPlayerAgent | None:
        """Get existing AI agent"""
        return self.agents.get(player_id)

    def remove_agent(self, player_id: str):
        """Remove AI agent"""
        if player_id in self.agents:
            del self.agents[player_id]
            logger.info(f"Removed AI agent: player_id={player_id}")

    def is_ai_player(self, player_id: str) -> bool:
        """Check if player is AI"""
        return player_id in self.agents

    def get_available_providers(self) -> list[str]:
        """Get list of providers that have API keys configured"""
        return sorted(self.provider_api_keys.keys())

    def get_all_stats(self) -> dict:
        """Get statistics for all AI agents"""
        return {
            "enabled": self.enabled,
            "active_agents": len(self.agents),
            "available_providers": self.get_available_providers(),
            "default_provider": self.default_provider,
            "agents": {
                player_id: agent.get_stats() for player_id, agent in self.agents.items()
            },
        }

    def get_available_difficulties(self) -> list:
        """
        Get list of available difficulty levels (8 levels).

        Note: Cost estimates are Anthropic-specific. OpenAI costs are typically
        12x higher (~$0.44/game vs $0.035/game for intermediate difficulty).
        """
        model_map = get_difficulty_model_map()
        fallback_model = get_fallback_model()

        return [
            {
                "id": "novice",
                "name": "Novice",
                "description": "Just learning the rules, makes mistakes",
                "estimated_cost_per_game": "$0.03-0.08",
                "model": model_map.get("novice", fallback_model),
            },
            {
                "id": "beginner",
                "name": "Beginner",
                "description": "Understands basics, random legal moves",
                "estimated_cost_per_game": "$0.05-0.15",
                "model": model_map.get("beginner", fallback_model),
            },
            {
                "id": "intermediate",
                "name": "Intermediate",
                "description": "Tactical play with basic strategy",
                "estimated_cost_per_game": "$0.10-0.20",
                "model": model_map.get("intermediate", fallback_model),
            },
            {
                "id": "skilled",
                "name": "Skilled",
                "description": "Consistent strategy, good card evaluation",
                "estimated_cost_per_game": "$0.50-0.80",
                "model": model_map.get("skilled", fallback_model),
            },
            {
                "id": "advanced",
                "name": "Advanced",
                "description": "Strategic planning and combos",
                "estimated_cost_per_game": "$0.60-1.00",
                "model": model_map.get("advanced", fallback_model),
            },
            {
                "id": "pro",
                "name": "Pro",
                "description": "Strong positional play, anticipates opponent",
                "estimated_cost_per_game": "$0.80-1.20",
                "model": model_map.get("pro", fallback_model),
            },
            {
                "id": "expert",
                "name": "Expert",
                "description": "Near-optimal play with deep analysis",
                "estimated_cost_per_game": "$2.50-3.50",
                "model": model_map.get("expert", fallback_model),
            },
            {
                "id": "master",
                "name": "Master",
                "description": "Maximum strategic depth, tournament-level",
                "estimated_cost_per_game": "$3.00-4.50",
                "model": model_map.get("master", fallback_model),
            },
        ]


# Global instance
ai_service = AIService()

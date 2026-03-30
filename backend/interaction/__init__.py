"""
Interaction module for handling dogma interactions.

This module provides the StandardInteractionBuilder as the single source of truth
for all dogma interaction request creation, eliminating field name inconsistencies
and simplifying the interaction flow.
"""

from .builder import StandardInteractionBuilder

__all__ = ["StandardInteractionBuilder"]

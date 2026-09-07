"""
Storage and Persistence Subsystem for PLOT / The Cultural Atlas.
Provides local-first SQLite persistence for questions, slates, responses, and hex aggregates.
"""

from .database import AtlasDatabase

__all__ = ["AtlasDatabase"]

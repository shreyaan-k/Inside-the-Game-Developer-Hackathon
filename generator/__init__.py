"""Synthetic football match generator for Why?"""
from .schema import SCHEMA_VERSION, validate_event, validate_match
from .sim import simulate_match

__all__ = ["SCHEMA_VERSION", "validate_event", "validate_match", "simulate_match"]
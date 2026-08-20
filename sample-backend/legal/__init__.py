"""Durable legal case domain.

Infrastructure models are imported by their consumers rather than eagerly here. This keeps
deterministic domain tools and the evaluation harness independent from Flask initialization.
"""

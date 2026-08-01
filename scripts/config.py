"""Shared configuration for the animated GitHub profile README.

Change USERNAME (and PROMPT / PROFILE_NAME) to your own details.
Every env var can also be set in CI to override these defaults.
"""
import os

# ── Change these to your own details ─────────────────────────────────────
USERNAME = os.environ.get("GITHUB_USERNAME", "SankalpPandey-56")
PROMPT = os.environ.get("PROMPT", "sankalp@github")      # shown in title bars
PROFILE_NAME = os.environ.get("PROFILE_NAME", "Sankalp Pandey")  # whoami output

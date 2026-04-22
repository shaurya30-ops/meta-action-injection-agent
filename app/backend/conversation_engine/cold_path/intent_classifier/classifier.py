"""
Compatibility shim for the current classifier implementation.

The production classifier still lives under the legacy module while the folder
restructure settles. Future cold-path implementations should replace this shim.
"""

from intent_classifier.classifier import *  # noqa: F401,F403


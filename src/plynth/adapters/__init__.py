"""Framework adapters for Plynth (Django, FastAPI, Flask — planned).

This package is reserved for thin bridging modules that connect Plynth's
core to specific web frameworks. Adapters depend on the core through its
public interfaces only; no framework assumptions leak back into the core.

See ADR-0002 for the layer responsibility definitions.
"""

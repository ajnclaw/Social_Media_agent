"""
Agent re-exports Agent lazily so that importing a narrow submodule
(e.g. `agent.image_server`, which only needs agent.image_gen) doesn't
force the whole planner/executor/ollama stack to load. A machine that
only runs the image server shouldn't need ollama installed at all.
"""

__all__ = ["Agent"]


def __getattr__(name):
    if name == "Agent":
        from .core import Agent

        return Agent

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

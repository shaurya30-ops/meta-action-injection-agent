"""
Compatibility wrapper for the current transition resolver.
"""


def resolve_transition(*args, **kwargs):
    import state_machine.resolver as legacy_resolver

    if hasattr(legacy_resolver, "resolve_transition"):
        return legacy_resolver.resolve_transition(*args, **kwargs)
    return legacy_resolver.resolve_next_state(*args, **kwargs)


__all__ = ["resolve_transition"]

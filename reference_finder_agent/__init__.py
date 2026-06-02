def create_reference_finder(*args, **kwargs):
    from .reference_finder_agent import create_reference_finder as _create
    return _create(*args, **kwargs)

__all__ = ["create_reference_finder"]

"""PLAT-C document intelligence and lifecycle projection package.

Package initialization stays side-effect free so shared ORM registration cannot recurse
through File Center resolver imports. Consumers import concrete services from their
own modules.
"""

__all__: tuple[str, ...] = ()

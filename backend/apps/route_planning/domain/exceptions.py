class DomainError(Exception):
    """Base class for violations of domain invariants."""


class InvalidLoadWeight(DomainError):
    pass


class InvalidGeometry(DomainError):
    pass


class InvalidTimingProfile(DomainError):
    pass

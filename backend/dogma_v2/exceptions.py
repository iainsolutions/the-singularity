"""
Exception classes for the dogma v2 system
"""


class DogmaError(Exception):
    """Base class for dogma errors"""

    def __init__(self, message: str, context, recoverable: bool = False):
        super().__init__(message)
        self.context = context
        self.recoverable = recoverable
        self.transaction_id = context.transaction_id if context else None


class ValidationError(DogmaError):
    """Validation failed"""

    pass


class StateError(DogmaError):
    """Invalid state transition"""

    pass


class InteractionError(DogmaError):
    """Interaction handling error"""

    pass


class TransactionError(DogmaError):
    """Transaction management error"""

    pass


class RollbackError(DogmaError):
    """Failed to rollback transaction"""

    pass

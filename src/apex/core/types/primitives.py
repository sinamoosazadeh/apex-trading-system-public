"""Strong-typed primitive wrappers for type safety."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import math
from typing import Union

@dataclass(frozen=True)
class Price:
    """Immutable price value object with validation."""
    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            try:
                object.__setattr__(self, 'value', Decimal(str(self.value)))
            except InvalidOperation:
                raise ValueError(f"Invalid price value: {self.value}")
        
        if self.value < 0:
            raise ValueError(f"Price cannot be negative: {self.value}")
        if math.isnan(float(self.value)) or math.isinf(float(self.value)):
            raise ValueError(f"Price must be finite: {self.value}")

    def __float__(self) -> float:
        return float(self.value)

    def __add__(self, other: 'Price') -> 'Price':
        return Price(self.value + other.value)

@dataclass(frozen=True)
class Probability:
    """Probability value strictly in [0, 1]."""
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Probability must be in [0, 1], got {self.value}")
        if math.isnan(self.value) or math.isinf(self.value):
            raise ValueError(f"Probability must be finite: {self.value}")

    def __float__(self) -> float:
        return self.value

    def complement(self) -> 'Probability':
        return Probability(1.0 - self.value)

@dataclass(frozen=True)
class Confidence:
    """Confidence score in [0, 1]."""
    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise ValueError(f"Confidence must be in [0, 1], got {self.value}")

    def __float__(self) -> float:
        return self.value

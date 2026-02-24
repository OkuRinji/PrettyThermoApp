from dataclasses import dataclass


@dataclass
class Component:
    id: int
    name: str
    formula: str
    enthalpy: float

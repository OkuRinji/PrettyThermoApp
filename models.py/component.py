#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль компонента термодинамической смеси.

Определяет класс Component для представления химического компонента
с его основными свойствами.
"""

from dataclasses import dataclass, field


@dataclass
class Component:
    """
    Компонент термодинамической смеси.

    Представляет химический компонент с уникальным идентификатором,
    названием, формулой и стандартной энтальпией образования.

    Attributes:
        id: Уникальный идентификатор компонента (положительное целое число).
        name: Название компонента (непустая строка).
        formula: Химическая формула (непустая строка).
        enthalpy: Стандартная энтальпия образования при 298K (кДж/кг).

    Raises:
        ValueError: При некорректных значениях полей.

    Example:
        >>> comp = Component(id=1, name="Вода", formula="H2O", enthalpy=-241.8)
        >>> print(comp)
        Component(id=1, name='Вода', formula='H2O', enthalpy=-241.8)
    """

    id: int = field(default=0)
    name: str = field(default="")
    formula: str = field(default="")
    enthalpy: float = field(default=0.0)

    def __post_init__(self) -> None:
        """
        Валидация полей после инициализации.

        Raises:
            ValueError: Если ID <= 0, name пустое или formula пустое.
        """
        if self.id <= 0:
            raise ValueError(f"ID должен быть положительным числом, получено: {self.id}")
        if not self.name or not self.name.strip():
            raise ValueError("Название компонента не может быть пустым")
        if not self.formula or not self.formula.strip():
            raise ValueError("Формула компонента не может быть пустой")

    def __str__(self) -> str:
        """Строковое представление компонента."""
        return f"{self.name} ({self.formula})"

    def __repr__(self) -> str:
        """Представление компонента для отладки."""
        return (
            f"Component(id={self.id}, name='{self.name}', "
            f"formula='{self.formula}', enthalpy={self.enthalpy})"
        )

    def to_dict(self) -> dict:
        """
        Преобразование компонента в словарь.

        Returns:
            Словарь с полями компонента.
        """
        return {
            "id": self.id,
            "name": self.name,
            "formula": self.formula,
            "enthalpy": self.enthalpy,
        }

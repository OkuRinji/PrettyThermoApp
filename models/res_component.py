"""
Модуль данных для парсера файлов .res.

Определяет классы для представления данных из файлов термохимической программы TERMPS.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models.results import Result


@dataclass
class ResComponent:
    """
    Компонент смеси из .res файла.

    Attributes:
        name: Название компонента (химическая формула).
        hf298: Энтальпия образования при 298 K.
    """

    name: str
    hf298: float

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь."""
        return {"name": self.name, "hf298": self.hf298}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResComponent":
        """Создание из словаря."""
        return cls(name=data["name"], hf298=data["hf298"])


@dataclass
class ResData:
    """
    Данные из .res файла.

    Attributes:
        filename: Имя файла.
        mixture_name: Название смеси.
        mixture_density: Плотность смеси.
        components: Список компонентов смеси.
        element_composition: Элементный состав.
        calculations: Список результатов расчётов.
    """

    filename: str
    mixture_name: str = ""
    mixture_density: float = 0.0
    components: list[ResComponent] = field(default_factory=list)
    element_composition: dict = field(default_factory=dict)
    calculations: list[Result] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """
        Преобразование в словарь для сохранения.

        Returns:
            Словарь с данными.
        """
        return {
            "filename": self.filename,
            "mixture_name": self.mixture_name,
            "mixture_density": self.mixture_density,
            "components": [comp.to_dict() for comp in self.components],
            "element_composition": self.element_composition,
            "calculations": [calc.to_dict() for calc in self.calculations],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResData":
        """
        Создание из словаря.

        Args:
            data: Словарь с данными.

        Returns:
            Экземпляр ResData.
        """
        return cls(
            filename=data["filename"],
            mixture_name=data.get("mixture_name", ""),
            mixture_density=data.get("mixture_density", 0.0),
            components=[ResComponent.from_dict(c) for c in data.get("components", [])],
            element_composition=data.get("element_composition", {}),
            calculations=[Result(**calc) for calc in data.get("calculations", [])],
        )

    def save_to_json(self, filepath: str | Path) -> None:
        """
        Сохранение данных в JSON файл.

        Args:
            filepath: Путь к файлу для сохранения.
        """
        filepath = Path(filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str | Path) -> "ResData":
        """
        Загрузка данных из JSON файла.

        Args:
            filepath: Путь к файлу для загрузки.

        Returns:
            Экземпляр ResData.
        """
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

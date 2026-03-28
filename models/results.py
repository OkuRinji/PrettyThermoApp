"""
Модуль результатов термодинамического расчёта.

Определяет класс Result для представления результатов расчёта горения смеси.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from models.res_component import ResComponent


def _default_composition() -> list[float]:
    return []


def _default_equilibrium_gas() -> dict[str, float]:
    return {}


def _default_equilibrium_condensed() -> dict[str, float]:
    return {}


@dataclass
class Result:
    """
    Результаты термодинамического расчёта смеси.

    Attributes:
        id: Идентификатор расчёта.
        composition_percent: Процентный состав компонентов.
        pressure: Давление в системе (МПа).
        temperature: Температура (K).
        enthalpy: Энтальпия.
        entropy: Энтропия.
        heat_capacity: Теплоёмкость.
        density: Плотность.
        molar_mass: Молярная масса.
        adiabatic_index: Показатель адиабаты.
        volume_gas: Объём газовой фазы.
        condensed_fraction: Доля конденсированных продуктов.
        equilibrium_gas: Равновесный состав газовой фазы.
        equilibrium_condensed: Равновесный состав конденсированных продуктов.
        calculation_date: Дата расчёта.
        calculation_time: Время расчёта.

    Raises:
        ValueError: При некорректных значениях полей.
    """

    id: int = field(default=1)
    composition_percent: list[float] = field(default_factory=_default_composition)
    pressure: float = field(default=0.0)
    temperature: float = field(default=0.0)
    enthalpy: float = field(default=0.0)
    entropy: float = field(default=0.0)
    heat_capacity: float = field(default=0.0)
    density: float = field(default=0.0)
    molar_mass: float = field(default=0.0)
    adiabatic_index: float = field(default=0.0)
    volume_gas: float = field(default=0.0)
    condensed_fraction: float = field(default=0.0)
    equilibrium_gas: dict[str, float] = field(default_factory=_default_equilibrium_gas)
    equilibrium_condensed: dict[str, float] = field(
        default_factory=_default_equilibrium_condensed
    )
    calculation_date: str = field(default="")
    calculation_time: str = field(default="")

    def __post_init__(self) -> None:
        """
        Валидация полей после инициализации.

        Raises:
            ValueError: Если значения полей некорректны.
        """
        # Валидация ID
        if self.id <= 0:
            raise ValueError(
                f"ID должен быть положительным числом, получено: {self.id}"
            )

        # Валидация числовых параметров
        if self.pressure < 0:
            raise ValueError(f"Pressure должен быть >= 0, получено: {self.pressure}")
        if self.temperature < 0:
            raise ValueError(
                f"Temperature должен быть >= 0, получено: {self.temperature}"
            )
        if self.density < 0:
            raise ValueError(f"Density должен быть >= 0, получено: {self.density}")
        if self.molar_mass < 0:
            raise ValueError(
                f"Molar mass должен быть >= 0, получено: {self.molar_mass}"
            )
        if self.adiabatic_index < 0:
            raise ValueError(
                f"Adiabatic index должен быть >= 0, получено: {self.adiabatic_index}"
            )
        if self.volume_gas < 0:
            raise ValueError(
                f"Volume gas должен быть >= 0, получено: {self.volume_gas}"
            )
        if self.condensed_fraction < 0 or self.condensed_fraction > 1:
            raise ValueError(
                f"Condensed fraction должен быть в диапазоне [0, 1], "
                f"получено: {self.condensed_fraction}"
            )

        # Валидация composition_percent
        if not isinstance(self.composition_percent, list):
            raise ValueError(
                f"'composition_percent' должен быть списком, "
                f"получено: {type(self.composition_percent)}"
            )
        for i, conc in enumerate(self.composition_percent):
            if not isinstance(conc, (int, float)):
                raise ValueError(
                    f"composition_percent[{i}] должен быть числом, "
                    f"получено: {type(conc)}"
                )
            if conc < 0:
                raise ValueError(
                    f"composition_percent[{i}] должен быть >= 0, получено: {conc}"
                )

        # Проверка суммы концентраций (если есть)
        if self.composition_percent:
            total = sum(self.composition_percent)
            if abs(total - 100.0) > 0.1:
                raise ValueError(
                    f"Сумма концентраций должна быть 100%, получено: {total:.2f}%"
                )

        # Валидация equilibrium_gas
        if not isinstance(self.equilibrium_gas, dict):
            raise ValueError(
                f"'equilibrium_gas' должен быть dict, "
                f"получено: {type(self.equilibrium_gas)}"
            )
        for comp, value in self.equilibrium_gas.items():
            if not isinstance(comp, str):
                raise ValueError(
                    f"Ключ equilibrium_gas должен быть str, получено: {type(comp)}"
                )
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Значение equilibrium_gas['{comp}'] должно быть числом, "
                    f"получено: {type(value)}"
                )
            if value < 0:
                raise ValueError(
                    f"Значение equilibrium_gas['{comp}'] должно быть >= 0, "
                    f"получено: {value}"
                )

        # Валидация equilibrium_condensed
        if not isinstance(self.equilibrium_condensed, dict):
            raise ValueError(
                f"'equilibrium_condensed' должен быть dict, "
                f"получено: {type(self.equilibrium_condensed)}"
            )
        for comp, value in self.equilibrium_condensed.items():
            if not isinstance(comp, str):
                raise ValueError(
                    f"Ключ equilibrium_condensed должен быть str, "
                    f"получено: {type(comp)}"
                )
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Значение equilibrium_condensed['{comp}'] должно быть числом, "
                    f"получено: {type(value)}"
                )
            if value < 0:
                raise ValueError(
                    f"Значение equilibrium_condensed['{comp}'] должно быть >= 0, "
                    f"получено: {value}"
                )

    def __str__(self) -> str:
        """Строковое представление результатов."""
        return (
            f"Result(id={self.id}, T={self.temperature:.2f}K, P={self.pressure:.4f}МПа)"
        )

    def __repr__(self) -> str:
        """Представление результатов для отладки."""
        return (
            f"Result(id={self.id}, temperature={self.temperature}, "
            f"pressure={self.pressure}, enthalpy={self.enthalpy})"
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Преобразование результатов в словарь.

        Returns:
            Словарь с полями результатов.
        """
        return {
            "id": self.id,
            "composition_percent": self.composition_percent,
            "pressure": self.pressure,
            "temperature": self.temperature,
            "enthalpy": self.enthalpy,
            "entropy": self.entropy,
            "heat_capacity": self.heat_capacity,
            "density": self.density,
            "molar_mass": self.molar_mass,
            "adiabatic_index": self.adiabatic_index,
            "volume_gas": self.volume_gas,
            "condensed_fraction": self.condensed_fraction,
            "equilibrium_gas": self.equilibrium_gas,
            "equilibrium_condensed": self.equilibrium_condensed,
            "calculation_date": self.calculation_date,
            "calculation_time": self.calculation_time,
        }


@dataclass
class ResultSeries:
    """
    Серия результатов термодинамического расчёта.

    Хранит все результаты, относящиеся к одной серии расчетов (например,
    оптимизация состава или параметрическое исследование).

    Attributes:
        results: Список экземпляров Result, относящихся к этой серии.
        mixture_name: Название смеси (если есть).
        mixture_density: Плотность смеси (если есть).
        element_composition: Элементный состав смеси.
        components: Список компонентов смеси.
        params: Параметры, использованные для расчетов.
    """

    results: list[Result] = field(default_factory=list)
    mixture_name: str = ""
    mixture_density: float = 0.0
    element_composition: dict = field(default_factory=dict)
    components: list["ResComponent"] = field(default_factory=list)
    params: Any | None = None

    def add_result(self, result: Result) -> None:
        """
        Добавить результат в серию.

        Args:
            result: Результат расчета для добавления.
        """
        self.results.append(result)

    def get_result_by_id(self, result_id: int) -> Result | None:
        """
        Получить результат по ID.

        Args:
            result_id: ID результата.

        Returns:
            Результат или None, если не найден.
        """
        for result in self.results:
            if result.id == result_id:
                return result
        return None

    def __len__(self) -> int:
        """Количество результатов в серии."""
        return len(self.results)

    def __iter__(self):
        """Итератор по результатам."""
        return iter(self.results)

    def to_dict(self) -> dict[str, Any]:
        """
        Преобразование серии результатов в словарь.

        Returns:
            Словарь с данными серии.
        """

        return {
            "results": [r.to_dict() for r in self.results],
            "mixture_name": self.mixture_name,
            "mixture_density": self.mixture_density,
            "element_composition": self.element_composition,
            "components": [c.to_dict() for c in self.components],
            "params": self.params.to_dict() if self.params else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResultSeries":
        """
        Создание серии результатов из словаря.

        Args:
            data: Словарь с данными.

        Returns:
            Экземпляр ResultSeries.
        """
        from models.params import Params
        from models.res_component import ResComponent

        series = cls()
        series.results = [Result(**r) for r in data.get("results", [])]
        series.mixture_name = data.get("mixture_name", "")
        series.mixture_density = data.get("mixture_density", 0.0)
        series.element_composition = data.get("element_composition", {})
        series.components = [
            ResComponent.from_dict(c) for c in data.get("components", [])
        ]
        params_data = data.get("params")
        if params_data:
            series.params = Params(**params_data)
        return series

    def save_to_json(self, filepath: str | Path) -> None:
        """
        Сохранение серии результатов в JSON файл.

        Args:
            filepath: Путь к файлу для сохранения.
        """
        filepath = Path(filepath)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_from_json(cls, filepath: str | Path) -> "ResultSeries":
        """
        Загрузка серии результатов из JSON файла.

        Args:
            filepath: Путь к файлу для загрузки.

        Returns:
            Экземпляр ResultSeries.
        """
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

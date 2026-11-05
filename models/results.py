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

    Поддерживает как одиночные значения (режим "Горение без расширения"),
    так и множественные (режим "Генераторный" с N точками: камера,
    критическое сечение, срез и т.д.).
    """

    id: int = field(default=1)
    res_type: str = field(default="Горение без расширения")
    composition_percent: list[float] = field(default_factory=_default_composition)
    
    # Все термодинамические параметры — списки
    pressure: list[float] = field(default_factory=list)
    temperature: list[float] = field(default_factory=list)
    enthalpy: list[float] = field(default_factory=list)
    entropy: list[float] = field(default_factory=list)
    heat_capacity: list[float] = field(default_factory=list)
    density: list[float] = field(default_factory=list)
    molar_mass: list[float] = field(default_factory=list)
    adiabatic_index: list[float] = field(default_factory=list)
    volume_gas: list[float] = field(default_factory=list)
    condensed_fraction: list[float] = field(default_factory=list)
    
    # Равновесный состав: для каждого компонента — список значений по точкам
    equilibrium_gas: dict[str, list[float]] = field(
        default_factory=_default_equilibrium_gas
    )
    equilibrium_condensed: dict[str, list[float]] = field(
        default_factory=_default_equilibrium_condensed
    )
    
    calculation_date: str = field(default="")
    calculation_time: str = field(default="")

    def __post_init__(self) -> None:
        if self.id <= 0:
            raise ValueError(f"ID должен быть положительным, получено: {self.id}")

        # Группируем числовые списки для единой проверки
        numeric_lists = {
            "pressure": self.pressure,
            "temperature": self.temperature,
            "enthalpy": self.enthalpy,
            "entropy": self.entropy,
            "heat_capacity": self.heat_capacity,
            "density": self.density,
            "molar_mass": self.molar_mass,
            "adiabatic_index": self.adiabatic_index,
            "volume_gas": self.volume_gas,
        }

        # Проверка согласованности длин (все точки должны быть заполнены)
        lengths = {name: len(lst) for name, lst in numeric_lists.items() if lst}
        if lengths:
            unique_lengths = set(lengths.values())
            if len(unique_lengths) > 1:
                raise ValueError(
                    f"Все числовые списки должны иметь одинаковую длину. "
                    f"Получены длины: {lengths}"
                )

        # Валидация каждого числового списка
        # for name, lst in numeric_lists.items():
        #     self._validate_numeric_list(name, lst, min_value=0.0)

        # Доля конденсата — каждое значение в [0, 1]
        self._validate_numeric_list(
            "condensed_fraction", self.condensed_fraction,
            min_value=0.0, max_value=1.0,
        )

        # composition_percent
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
        if self.composition_percent:
            total = sum(self.composition_percent)
            if abs(total - 100.0) > 0.1:
                raise ValueError(
                    f"Сумма концентраций должна быть 100%, получено: {total:.2f}%"
                )

        # Равновесный состав
        self._validate_equilibrium_dict("equilibrium_gas", self.equilibrium_gas)
        self._validate_equilibrium_dict(
            "equilibrium_condensed", self.equilibrium_condensed
        )

    def _validate_numeric_list(
        self,
        name: str,
        lst: list,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        if not isinstance(lst, list):
            raise ValueError(f"'{name}' должен быть списком, получено: {type(lst)}")
        for i, val in enumerate(lst):
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"{name}[{i}] должен быть числом, получено: {type(val)}"
                )
            if min_value is not None and val < min_value:
                raise ValueError(
                    f"{name}[{i}] должен быть >= {min_value}, получено: {val}"
                )
            if max_value is not None and val > max_value:
                raise ValueError(
                    f"{name}[{i}] должен быть <= {max_value}, получено: {val}"
                )

    def _validate_equilibrium_dict(self, name: str, data: dict) -> None:
        if not isinstance(data, dict):
            raise ValueError(f"'{name}' должен быть dict, получено: {type(data)}")
        for comp, values in data.items():
            if not isinstance(comp, str):
                raise ValueError(
                    f"Ключ {name} должен быть str, получено: {type(comp)}"
                )
            if not isinstance(values, list):
                raise ValueError(
                    f"Значение {name}['{comp}'] должно быть списком, "
                    f"получено: {type(values)}"
                )
            for i, val in enumerate(values):
                if not isinstance(val, (int, float)):
                    raise ValueError(
                        f"{name}['{comp}'][{i}] должно быть числом, "
                        f"получено: {type(val)}"
                    )
                # if val < 0:
                #     raise ValueError(
                #         f"{name}['{comp}'][{i}] должно быть >= 0, получено: {val}"
                #     )

    def __str__(self) -> str:
        """Строковое представление: первая точка + кол-во точек."""
        t = self.temperature[0] if self.temperature else 0.0
        p = self.pressure[0] if self.pressure else 0.0
        n = len(self.pressure)
        return (
            f"Result(id={self.id}, type={self.res_type!r}, "
            f"T[0]={t:.2f}K, P[0]={p:.4f}МПа, points={n})"
        )

    def __repr__(self) -> str:
        return (
            f"Result(id={self.id}, res_type={self.res_type!r}, "
            f"temperature={self.temperature}, pressure={self.pressure}, "
            f"enthalpy={self.enthalpy})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "res_type": self.res_type,
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
    def save_to_text(self,filepath: str| Path):
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(self.to_dict))
        

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

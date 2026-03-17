"""
Модуль параметров термодинамической смеси.

Определяет класс Params для набора параметров расчёта горения смеси.
"""

from dataclasses import dataclass, field
from typing import Any


def _default_directives() -> dict:
    return {
        "LDY": False,
        "LNN": True,
        "TABL": True,
        "WPS": False,
        "LVM": False,
    }


def _default_variants() -> list:
    return [{"id": 1, "concentrations": [50.0, 50.0]}]


def _default_components() -> list:
    return [
        {"id": 0, "name": "", "enthalpy": 0.0, "formula": ""},
        {"id": 1, "name": "", "enthalpy": 0.0, "formula": ""},
    ]


def _default_al_variants() -> list:
    return [{"id": 1, "concentrations": [100.0]}]


@dataclass
class Params:
    """
    Набор параметров горения смеси.

    Attributes:
        author: Сотрудник/Студент, выполняющий расчет.
        code: Код шифра.
        directives: Директивы, применяемые в данном расчете.
        variants: Вариации содержания компонентов.
        components: Список компонентов.
        PK: Давление на срезе.
        PC: Давление в камере.
        AL: Степень участия внешнего окислителя.
        N: Количество компонентов.
        NB: Количество вариаций.
        AL_N: Количество внешних окислителей.
        AL_NB: Количество вариаций внешних окислителей.

    Raises:
        ValueError: При некорректных значениях полей.
    """

    author: str = field(default="Белобородов")
    code: str = field(default="*")
    directives: dict[str, Any] = field(default_factory=_default_directives)
    PK: float = field(default=0.1)
    PC: float = field(default=0.1)
    AL: float = field(default=0)
    N: float = field(default=1)
    NB: float = field(default=2)
    AL_N: float = field(default=1)
    AL_NB: float = field(default=1)
    variants: list[dict[str, Any]] = field(default_factory=_default_variants)
    components: list[dict[str, Any]] = field(default_factory=_default_components)
    al_variants: list[dict[str, Any]] = field(default_factory=_default_al_variants)

    def __post_init__(self) -> None:
        """
        Валидация полей после инициализации.

        Raises:
            ValueError: Если значения полей некорректны.
        """
        # Валидация строковых полей
        if not self.author or not self.author.strip():
            raise ValueError("Поле 'author' не может быть пустым")
        if not self.code or not self.code.strip():
            raise ValueError("Поле 'code' не может быть пустым")

        # Валидация директив
        if not isinstance(self.directives, dict):
            raise ValueError(
                f"'directives' должен быть dict, получено: {type(self.directives)}"
            )
        required_directives = {"LDY", "LNN", "TABL", "WPS", "LVM"}
        for key in required_directives:
            if key not in self.directives:
                raise ValueError(f"В 'directives' отсутствует обязательный ключ: {key}")

        # Валидация числовых параметров
        if self.PK <= 0:
            raise ValueError(f"PK должен быть > 0, получено: {self.PK}")
        if self.PC <= 0:
            raise ValueError(f"PC должен быть > 0, получено: {self.PC}")
        if self.AL < 0:
            raise ValueError(f"AL должен быть >= 0, получено: {self.AL}")
        if self.N < 1:
            raise ValueError(f"N должен быть >= 1, получено: {self.N}")
        if self.NB < 1:
            raise ValueError(f"NB должен быть >= 1, получено: {self.NB}")
        if self.AL_N < 0:
            raise ValueError(f"AL_N должен быть >= 0, получено: {self.AL_N}")
        if self.AL_NB < 0:
            raise ValueError(f"AL_NB должен быть >= 0, получено: {self.AL_NB}")

        # Валидация variants
        if not isinstance(self.variants, list) or len(self.variants) == 0:
            raise ValueError("'variants' должен быть непустым списком")
        for i, variant in enumerate(self.variants):
            if not isinstance(variant, dict):
                raise ValueError(f"variant[{i}] должен быть dict")
            if "id" not in variant or "concentrations" not in variant:
                raise ValueError(
                    f"variant[{i}] должен содержать 'id' и 'concentrations'"
                )
            if not isinstance(variant["concentrations"], list):
                raise ValueError(f"variant[{i}]['concentrations'] должен быть списком")

        # Валидация components
        if not isinstance(self.components, list) or len(self.components) == 0:
            raise ValueError("'components' должен быть непустым списком")
        for i, comp in enumerate(self.components):
            if not isinstance(comp, dict):
                raise ValueError(f"component[{i}] должен быть dict")
            required_keys = {"id", "name", "enthalpy", "formula"}
            for key in required_keys:
                if key not in comp:
                    raise ValueError(
                        f"component[{i}] отсутствует обязательное поле: {key}"
                    )

        # Валидация al_variants
        if not isinstance(self.al_variants, list) or len(self.al_variants) == 0:
            raise ValueError("'al_variants' должен быть непустым списком")
        for i, al_var in enumerate(self.al_variants):
            if not isinstance(al_var, dict):
                raise ValueError(f"al_variant[{i}] должен быть dict")
            if "id" not in al_var or "concentrations" not in al_var:
                raise ValueError(
                    f"al_variant[{i}] должен содержать 'id' и 'concentrations'"
                )

    def __str__(self) -> str:
        """Строковое представление параметров."""
        return f"Params(code='{self.code}', author='{self.author}', PC={self.PC}, PK={self.PK})"

    def __repr__(self) -> str:
        """Представление параметров для отладки."""
        return (
            f"Params(author='{self.author}', code='{self.code}', "
            f"PC={self.PC}, PK={self.PK}, AL={self.AL}, N={self.N}, NB={self.NB})"
        )

    def to_dict(self) -> dict:
        """
        Преобразование параметров в словарь.

        Returns:
            Словарь с полями параметров.
        """
        return {
            "author": self.author,
            "code": self.code,
            "directives": self.directives,
            "PK": self.PK,
            "PC": self.PC,
            "AL": self.AL,
            "N": self.N,
            "NB": self.NB,
            "AL_N": self.AL_N,
            "AL_NB": self.AL_NB,
            "variants": self.variants,
            "components": self.components,
            "al_variants": self.al_variants,
        }

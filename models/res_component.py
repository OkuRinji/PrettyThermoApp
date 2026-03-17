"""
Модуль данных для парсера файлов .res.

Определяет классы для представления данных из файлов термохимической программы TERMPS.
"""

from dataclasses import dataclass, field

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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль оптимизации состава смеси по параметрам горения.

Предоставляет классы и методы для оптимизации состава термодинамической смеси
по целевым параметрам (температура, энтальпия, плотность и др.).
"""

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from core.ps_generator import PSGenerator
from core.res_parser import ResParser
from core.runner import OTVDMMRunner
from models.results import Result

logger = logging.getLogger(__name__)


class OptimizationTarget(Enum):
    """Целевые параметры для оптимизации"""

    TEMPERATURE = "temperature"  # Температура
    ENTHALPY = "enthalpy"  # Энтальпия
    DENSITY = "density"  # Плотность
    MOLAR_MASS = "molar_mass"  # Молярная масса
    ADIABATIC_INDEX = "adiabatic_index"  # Показатель адиабаты
    VOLUME_GAS = "volume_gas"  # Объём газовой фазы
    CUSTOM = "custom"  # Пользовательская функция


class OptimizationMode(Enum):
    """Режим оптимизации"""

    MAXIMIZE = "maximize"  # Максимизация
    MINIMIZE = "minimize"  # Минимизация
    TARGET_VALUE = "target"  # Достижение конкретного значения


@dataclass
class OptimizationResult:
    """Результат оптимизации"""

    success: bool  # Успешно ли завершена
    best_concentrations: List[float]  # Лучшие концентрации
    best_value: float  # Лучшее значение целевого параметра
    iterations: int  # Количество итераций
    history: List[Dict] = field(default_factory=list)  # История итераций
    message: str = ""  # Сообщение о результате


@dataclass
class OptimizationParams:
    """Параметры оптимизации"""

    target_param: OptimizationTarget  # Целевой параметр
    mode: OptimizationMode  # Режим (мин/макс/значение)
    comp1_idx: int  # Индекс первого компонента
    comp2_idx: int  # Индекс второго компонента
    other_concentrations: List[float]  # Концентрации остальных компонентов
    min_conc: float = 0.0  # Минимальная концентрация
    max_conc: float = 100.0  # Максимальная концентрация
    tolerance: float = 0.1  # Точность оптимизации
    max_iterations: int = 20  # Максимум итераций
    custom_func: Optional[Callable] = None  # Пользовательская функция
    on_iteration: Optional[Callable] = None  # Обратный вызов на итерации
    target_value: Optional[float] = None  # Целевое значение (для режима TARGET_VALUE)
    target_tolerance: float = 1.0  # Допуск для целевого значения (%)


class OptimizerBase(ABC):
    """Базовый класс для всех методов оптимизации."""

    def __init__(
        self,
        runner: OTVDMMRunner,
        ps_generator: PSGenerator,
        work_dir: str,
        base_params: Dict,
    ):
        self.runner = runner
        self.ps_generator = ps_generator
        self.work_dir = work_dir
        self.base_params = base_params
        self.current_params: Dict = {}
        self._stop_flag = False
        self._target_param: Optional[OptimizationTarget] = None

    def stop(self) -> None:
        """Остановка оптимизации."""
        self._stop_flag = True

    def reset(self) -> None:
        """Сброс флага остановки."""
        self._stop_flag = False

    @abstractmethod
    def optimize(self, params: OptimizationParams) -> OptimizationResult:
        """
        Метод оптимизации состава смеси.

        Args:
            params: Параметры оптимизации (целевой параметр, режим, ограничения).

        Returns:
            Результат оптимизации с лучшими концентрациями и историей итераций.

        Raises:
            NotImplementedError: Если метод не реализован в подклассе.
        """
        pass

    def _evaluate(
        self,
        conc1: float,
        conc2: float,
        other_conc: List[float],
        comp1_idx: int,
        comp2_idx: int,
        point_name: str = "",
    ) -> Tuple[float, Dict]:
        """
        Вычисление целевого параметра для заданных концентраций.

        Выполняет расчет для указанной комбинации концентраций и возвращает
        значение целевого параметра и полные данные расчета.

        Args:
            conc1: Концентрация первого компонента (%).
            conc2: Концентрация второго компонента (%).
            other_conc: Концентрации остальных компонентов (%).
            comp1_idx: Индекс первого компонента в списке.
            comp2_idx: Индекс второго компонента в списке.
            point_name: Имя точки для имени PS-файла (x1, x2, x3, extremum).

        Returns:
            Кортеж из (значение_целевого_параметра, данные_расчета).
            Данные расчета включают все термодинамические параметры.
        """
        # Расставляем концентрации по местам
        concentrations = [0.0] * len(other_conc) + [conc1, conc2]

        # Расставляем концентрации по местам
        other_idx = 0
        for i in range(len(concentrations)):
            if i != comp1_idx and i != comp2_idx:
                concentrations[i] = other_conc[other_idx]
                other_idx += 1

        # Обновляем параметры
        self.current_params = self.base_params.copy()
        self.current_params["variants"] = [{"id": 1, "concentrations": concentrations}]

        # Генерируем PS файл с коротким именем (макс 6 символов + .ps = 9)
        if point_name:
            ps_file = f"{point_name}.ps"
        else:
            timestamp = int(time.time() * 1000) % 100000
            ps_file = f"o{timestamp}.ps"

        self.ps_generator.generate(self.current_params, ps_file)

        # Запускаем расчет
        self.runner.run(ps_file=ps_file, hidden=True, async_mode=False)

        # Ждем завершения записи файла результатов
        time.sleep(0.5)

        # Читаем результаты - имя .res файла совпадает с .ps
        res_file = f"{ps_file[:-3]}.res"  # Заменяем .ps на .res
        res_path = os.path.join(self.work_dir, res_file)
        if not os.path.exists(res_path):
            # Пытаемся найти последний созданный .res файл
            import glob

            res_files = glob.glob(os.path.join(self.work_dir, "*.res"))
            if res_files:
                res_path = max(res_files, key=os.path.getctime)
            else:
                return 0.0, {}

        try:
            parser = ResParser(res_path)
            data = parser.parse()

            if not data.calculations:
                return 0.0, {}

            calc = data.calculations[0]
            value = self._extract_target_value(calc, self._target_param)

            calc_data = {
                "temperature": calc.temperature,
                "enthalpy": calc.enthalpy,
                "density": calc.density,
                "molar_mass": calc.molar_mass,
                "adiabatic_index": calc.adiabatic_index,
                "volume_gas": calc.volume_gas,
                "concentrations": concentrations.copy(),
            }

            return value, calc_data

        except Exception as e:
            logger.error(f"Ошибка чтения результатов: {e}")
            return 0.0, {}

    def _build_full_concentrations(
        self,
        conc1: float,
        conc2: float,
        other_conc: List[float],
        comp1_idx: int,
        comp2_idx: int,
    ) -> List[float]:
        """
        Сборка полных концентраций всех компонентов.

        Args:
            conc1: Концентрация первого компонента (%).
            conc2: Концентрация второго компонента (%).
            other_conc: Концентрации остальных компонентов (%).
            comp1_idx: Индекс первого компонента.
            comp2_idx: Индекс второго компонента.

        Returns:
            Список концентраций всех компонентов в правильном порядке.
        """
        n_components = len(other_conc) + 2
        concentrations: List[float] = [0.0] * n_components
        concentrations[comp1_idx] = conc1
        concentrations[comp2_idx] = conc2

        other_idx = 0
        for i in range(n_components):
            if i != comp1_idx and i != comp2_idx:
                concentrations[i] = other_conc[other_idx]
                other_idx += 1

        return concentrations

    def _extract_target_value(
        self,
        calc: "Result",
        target: OptimizationTarget,
    ) -> float:
        """
        Извлечение значения целевого параметра из результатов расчета.

        Args:
            calc: Результаты расчета с термодинамическими параметрами.
            target: Целевой параметр для извлечения.

        Returns:
            Значение целевого параметра или 0.0 если параметр отсутствует.
        """
        target_extractors = {
            OptimizationTarget.TEMPERATURE: lambda c: c.temperature,
            OptimizationTarget.ENTHALPY: lambda c: c.enthalpy,
            OptimizationTarget.DENSITY: lambda c: c.density,
            OptimizationTarget.MOLAR_MASS: lambda c: c.molar_mass,
            OptimizationTarget.ADIABATIC_INDEX: lambda c: c.adiabatic_index,
            OptimizationTarget.VOLUME_GAS: lambda c: c.volume_gas,
            OptimizationTarget.CUSTOM: lambda c: 0.0,
        }

        extractor = target_extractors.get(target)
        if extractor:
            value = extractor(calc)
            return value if value is not None else 0.0
        return 0.0

    def _get_target_value(
        self,
        calc_data: Dict[str, float],
        target: OptimizationTarget,
    ) -> float:
        """
        Получение значения целевого параметра из словаря данных.

        Args:
            calc_data: Словарь с данными расчета.
            target: Целевой параметр для извлечения.

        Returns:
            Значение целевого параметра или 0.0.
        """
        return calc_data.get(target.value, 0.0)


class OptimizationManager:
    """
    Менеджер оптимизации — фабрика для создания оптимизаторов.

    Предоставляет единый интерфейс для создания оптимизаторов
    различных методов.
    """

    @staticmethod
    def create_optimizer(
        method: str,
        runner: OTVDMMRunner,
        ps_generator: PSGenerator,
        work_dir: str,
        base_params: Dict,
    ) -> OptimizerBase:
        """
        Создание оптимизатора указанного метода.

        Args:
            method: Название метода ("quadratic", "golden", "gradient", etc.).
            runner: Раннер для запуска расчетов.
            ps_generator: Генератор PS файлов.
            work_dir: Рабочая директория.
            base_params: Базовые параметры расчета.

        Returns:
            Экземпляр оптимизатора указанного метода.

        Raises:
            ValueError: Если метод не поддерживается.
        """
        # Отложенный импорт для избежания циклической зависимости
        from core.optimizers.grad import GradientOptimizer
        from core.optimizers.quad import QuadraticOptimizer

        methods: Dict[str, type[OptimizerBase]] = {
            "quadratic": QuadraticOptimizer,
            "gradient": GradientOptimizer,
        }

        if method.lower() not in methods:
            raise ValueError(f"Неизвестный метод оптимизации: {method}")

        return methods[method.lower()](runner, ps_generator, work_dir, base_params)

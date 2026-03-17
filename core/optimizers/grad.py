#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Градиентный метод оптимизации состава смеси.

Использует численный градиент для поиска экстремума целевой функции.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from core.optimizers.base_model import (
    OptimizationMode,
    OptimizationParams,
    OptimizationResult,
    OptimizerBase,
)

logger = logging.getLogger(__name__)


@dataclass
class GradientOptimizerParams:
    """Дополнительные параметры для градиентного метода"""

    learning_rate: float = 5.0  # Начальный шаг градиента
    min_learning_rate: float = 0.5  # Минимальный шаг
    max_learning_rate: float = 15.0  # Максимальный шаг
    momentum: float = 0.8  # Коэффициент инерции
    use_momentum: bool = True  # Использовать ли моментум


class GradientOptimizer(OptimizerBase):
    """
    Оптимизатор на основе градиентного спуска.

    Алгоритм:
    1. Вычисляем градиент методом конечных разностей.
    2. Делаем шаг в направлении антиградиента (для минимизации) или градиента (для максимизации).
    3. Повторяем до сходимости.
    """

    def optimize(
        self, params: OptimizationParams, grad_params: GradientOptimizerParams
    ) -> OptimizationResult:
        """
        Оптимизация градиентным методом.

        Args:
            params: Параметры оптимизации.

        Returns:
            Результат оптимизации с лучшими концентрациями.
        """
        self.reset()
        self._target_param = params.target_param

        history: List[Dict] = []
        iteration = 0

        # Вычисляем доступный диапазон
        other_sum = sum(params.other_concentrations)
        available = 100.0 - other_sum

        # Начальная концентрация первого компонента
        conc1 = available / 2

        best_result: Optional[Dict] = None
        best_value = float("-inf")

        # Параметры градиентного спуска
        learning_rate = grad_params.learning_rate
        min_learning_rate = grad_params.min_learning_rate
        gradient_step = grad_params.max_learning_rate
        momentum = grad_params.momentum
        use_momentum = grad_params.use_momentum

        # Переменные для моментума
        prev_grad_c1 = 0.0

        target_reached = False
        no_improvement_count = 0

        while (
            iteration < params.max_iterations
            and not self._stop_flag
            and not target_reached
        ):
            # Ограничиваем концентрацию
            conc1 = max(params.min_conc, min(params.max_conc, conc1, available))
            conc2 = available - conc1

            # Вычисляем текущее значение
            current_value, current_data = self._evaluate(
                conc1,
                conc2,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
                point_name=f"g{iteration}",
            )

            # Вызываем обратный вызов
            full_conc = self._build_full_concentrations(
                conc1,
                conc2,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
            )

            if params.on_iteration:
                params.on_iteration(
                    iteration + 1, params.max_iterations, current_value, full_conc
                )

            # Преобразуем значение в зависимости от режима
            if params.mode == OptimizationMode.MINIMIZE:
                current_value_transformed = (
                    -current_value if current_value > 0 else float("-inf")
                )
            elif (
                params.mode == OptimizationMode.TARGET_VALUE
                and params.target_value is not None
            ):
                current_value_transformed = -abs(current_value - params.target_value)
            else:  # MAXIMIZE
                current_value_transformed = current_value

            # Проверяем на лучшее значение
            is_better = current_value_transformed > best_value
            if params.mode == OptimizationMode.MINIMIZE:
                is_better = is_better and current_value > 0

            if is_better:
                best_value = current_value_transformed
                best_result = {
                    "conc1": conc1,
                    "conc2": conc2,
                    "value": current_value,
                    "data": current_data,
                    "full_concentrations": full_conc,
                }
                no_improvement_count = 0
            else:
                no_improvement_count += 1

            # Вычисляем градиент методом конечных разностей
            h = gradient_step

            # Приращение по первому параметру
            c1_plus = self._clip(
                conc1 + h, params.min_conc, min(available, params.max_conc)
            )
            c2_plus = available - c1_plus

            f_plus, _ = self._evaluate(
                c1_plus,
                c2_plus,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
            )

            # Преобразуем для градиента
            if params.mode == OptimizationMode.MINIMIZE:
                f_plus_transformed = -f_plus if f_plus > 0 else float("-inf")
            elif (
                params.mode == OptimizationMode.TARGET_VALUE
                and params.target_value is not None
            ):
                f_plus_transformed = -abs(f_plus - params.target_value)
            else:
                f_plus_transformed = f_plus

            grad_c1 = (f_plus_transformed - current_value_transformed) / h

            # Проверка на сходимость (градиент почти нулевой)
            if abs(grad_c1) < params.tolerance:
                logger.info("Градиент слишком мал. Сходимость достигнута.")
                break

            # Применяем моментум
            if use_momentum:
                grad_c1 = momentum * prev_grad_c1 + (1 - momentum) * grad_c1

            prev_grad_c1 = grad_c1

            # Делаем шаг в направлении антиградиента (т.к. мы минимизируем loss)
            if params.mode == OptimizationMode.MAXIMIZE:
                new_conc1 = conc1 + learning_rate * grad_c1
            else:
                new_conc1 = conc1 - learning_rate * grad_c1

            # Ограничиваем границы
            new_conc1 = self._clip(
                new_conc1, params.min_conc, min(available, params.max_conc)
            )

            # Проверка, что параметры перестали меняться
            if abs(new_conc1 - conc1) < params.tolerance:
                logger.info("Параметры перестали меняться. Сходимость.")
                break

            conc1 = new_conc1

            # Добавляем в историю
            history.append(
                {
                    "iteration": iteration + 1,
                    "conc1": conc1,
                    "conc2": available - conc1,
                    "value": current_value,
                    "target": params.target_value
                    if params.mode == OptimizationMode.TARGET_VALUE
                    else None,
                    "full_concentrations": full_conc,
                }
            )

            # Проверяем целевое значение
            if (
                params.mode == OptimizationMode.TARGET_VALUE
                and params.target_value is not None
                and best_result is not None
            ):
                if (
                    abs(best_result["value"] - params.target_value)
                    <= params.target_tolerance
                ):
                    target_reached = True
                    logger.info("Целевое значение достигнуто.")

            # Если долго нет улучшений - уменьшаем шаг
            if no_improvement_count > 3:
                learning_rate = max(min_learning_rate, learning_rate / 2)
                no_improvement_count = 0

            iteration += 1

        # Формируем результат
        if best_result:
            return OptimizationResult(
                success=True,
                best_concentrations=best_result.get("full_concentrations", []),
                best_value=best_result["value"],
                iterations=iteration + 1,
                history=history,
                message=f"Найден оптимум: {self._target_param.value} = {best_result['value']:.2f}",
            )
        else:
            return OptimizationResult(
                success=False,
                best_concentrations=[],
                best_value=0.0,
                iterations=iteration + 1,
                history=history,
                message="Оптимум не найден",
            )

    def _clip(self, value: float, min_val: float, max_val: float) -> float:
        """Ограничивает значение в допустимых пределах."""
        return max(min_val, min(value, max_val))

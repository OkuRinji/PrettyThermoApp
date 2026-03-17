import math
from typing import Dict, List, Optional

from core.optimizers.base_model import (
    OptimizationMode,
    OptimizationParams,
    OptimizationResult,
    OptimizerBase,
)


class QuadraticOptimizer(OptimizerBase):
    """
    Оптимизатор на основе квадратичной аппроксимации.

    Алгоритм:
    1. Вычисляем целевую функцию в трёх точках.
    2. Строим квадратичный интерполянт.
    3. Находим экстремум параболы.
    4. Сдвигаемся к экстремуму и повторяем.
    """

    def optimize(self, params: OptimizationParams) -> OptimizationResult:
        """
        Оптимизация методом квадратичной аппроксимации.

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

        # Инициализация лучшего значения в зависимости от режима
        # После преобразования для всех режимов "больше = лучше"
        best_value = float("-inf")

        target_reached = False
        no_improvement_count = 0  # Счетчик итераций без улучшения

        # История концентраций
        conc1_history = []
        oscillation_detected = False

        # Флаг для оценки граничных точек на ранних итерациях
        boundary_evaluated = False

        # Инициализация шага
        step = max(2.0, min(15.0, available / 3))

        while (
            iteration < params.max_iterations
            and not self._stop_flag
            and not target_reached
        ):
            # Ограничиваем концентрацию
            conc1 = max(params.min_conc, min(params.max_conc, conc1, available))

            # Обнаружение колебаний: если концентрация меняется в пределах диапазона
            if len(conc1_history) >= 5:
                conc_range = max(conc1_history) - min(conc1_history)
                if conc_range < 3.0 and no_improvement_count >= 2:
                    oscillation_detected = True

            # Адаптивный шаг с учётом обнаружения колебаний
            if oscillation_detected:
                # При обнаружении колебаний - резко уменьшаем шаг
                step = max(1.0, min(3.0, step / 2))
            else:
                # Первые 70% итераций - исследуем весь диапазон
                exploration_ratio = 1.0 - (iteration / (params.max_iterations * 0.7))
                exploration_ratio = max(0.3, min(1.0, exploration_ratio))

                # Базовый шаг зависит от фазы: сначала большой, потом уменьшается
                base_step = available * exploration_ratio / 3
                step = max(2.0, min(15.0, base_step))

            x1 = max(params.min_conc, min(params.max_conc, conc1 - step))
            x2 = conc1
            x3 = max(params.min_conc, min(params.max_conc, available, conc1 + step))

            # Вычисляем значения в трёх точках с короткими именами файлов
            f1, data1 = self._evaluate(
                x1,
                available - x1,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
                point_name=f"a{iteration}",
            )

            # Собираем полные концентрации для истории
            full_conc1 = self._build_full_concentrations(
                x1,
                available - x1,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
            )

            # Вызываем обратный вызов после первой точки
            if params.on_iteration:
                params.on_iteration(
                    iteration * 3 + 1, params.max_iterations * 3, f1, full_conc1
                )

            f2, data2 = self._evaluate(
                x2,
                available - x2,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
                point_name=f"b{iteration}",
            )

            full_conc2 = self._build_full_concentrations(
                x2,
                available - x2,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
            )

            # Вызываем обратный вызов после второй точки
            if params.on_iteration:
                params.on_iteration(
                    iteration * 3 + 2, params.max_iterations * 3, f2, full_conc2
                )

            f3, data3 = self._evaluate(
                x3,
                available - x3,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
                point_name=f"c{iteration}",
            )

            full_conc3 = self._build_full_concentrations(
                x3,
                available - x3,
                params.other_concentrations,
                params.comp1_idx,
                params.comp2_idx,
            )

            # Вызываем обратный вызов после третьей точки
            if params.on_iteration:
                params.on_iteration(
                    iteration * 3 + 3, params.max_iterations * 3, f3, full_conc3
                )

            # Проверяем целевое значение сразу после вычислений
            if (
                params.mode == OptimizationMode.TARGET_VALUE
                and params.target_value is not None
            ):
                for f_val, x_val, full_conc in [
                    (f1, x1, full_conc1),
                    (f2, x2, full_conc2),
                    (f3, x3, full_conc3),
                ]:
                    if abs(f_val - params.target_value) <= params.target_tolerance:
                        target_reached = True
                        best_result = {
                            "conc1": x_val,
                            "conc2": available - x_val,
                            "value": f_val,
                            "data": data1
                            if x_val == x1
                            else (data2 if x_val == x2 else data3),
                            "full_concentrations": full_conc,
                        }
                        best_value = f_val
                        break

                if target_reached:
                    break

            # Преобразуем значения в зависимости от режима
            if params.mode == OptimizationMode.MINIMIZE:
                f1_val, f2_val, f3_val = -f1, -f2, -f3
            elif (
                params.mode == OptimizationMode.TARGET_VALUE
                and params.target_value is not None
            ):
                f1_val = -abs(f1 - params.target_value)
                f2_val = -abs(f2 - params.target_value)
                f3_val = -abs(f3 - params.target_value)
            else:  # MAXIMIZE
                f1_val, f2_val, f3_val = f1, f2, f3

            # На первой итерации оценим граничные точки для лучшего исследования диапазона
            if iteration == 0 and not boundary_evaluated:
                # Оценим левую границу (с учётом max_conc)
                left_conc = max(params.min_conc, min(params.max_conc, params.min_conc))
                f_left, data_left = self._evaluate(
                    left_conc,
                    available - left_conc,
                    params.other_concentrations,
                    params.comp1_idx,
                    params.comp2_idx,
                    point_name="left",
                )
                full_conc_left = self._build_full_concentrations(
                    left_conc,
                    available - left_conc,
                    params.other_concentrations,
                    params.comp1_idx,
                    params.comp2_idx,
                )
                if params.on_iteration:
                    params.on_iteration(
                        1, params.max_iterations * 3, f_left, full_conc_left
                    )

                # Оценим правую границу только если она в пределах max_conc
                # и не приводит к невалидным результатам (температура = 0)
                right_conc = max(params.min_conc, min(params.max_conc, available))
                f_right, data_right = None, None
                full_conc_right = None

                # При минимизации не оцениваем точку, где второй компонент = 0
                # (это приводит к невалидным результатам с температурой = 0)
                second_component_conc = available - right_conc
                if (
                    params.mode != OptimizationMode.MINIMIZE
                    or second_component_conc > 0
                ):
                    f_right, data_right = self._evaluate(
                        right_conc,
                        available - right_conc,
                        params.other_concentrations,
                        params.comp1_idx,
                        params.comp2_idx,
                        point_name="rght",
                    )
                    full_conc_right = self._build_full_concentrations(
                        right_conc,
                        available - right_conc,
                        params.other_concentrations,
                        params.comp1_idx,
                        params.comp2_idx,
                    )
                    if params.on_iteration:
                        params.on_iteration(
                            2, params.max_iterations * 3, f_right, full_conc_right
                        )

                # Преобразуем значения границ в зависимости от режима
                if params.mode == OptimizationMode.MINIMIZE:
                    f_left_val = -f_left
                    f_right_val = -f_right if f_right is not None else float("-inf")
                elif (
                    params.mode == OptimizationMode.TARGET_VALUE
                    and params.target_value is not None
                ):
                    f_left_val = -abs(f_left - params.target_value)
                    f_right_val = (
                        -abs(f_right - params.target_value)
                        if f_right is not None
                        else float("-inf")
                    )
                else:
                    f_left_val = f_left
                    f_right_val = f_right if f_right is not None else float("-inf")

                # Найдём лучшую точку среди всех оценённых (исключая невалидные)
                all_values = [
                    (f1_val, x1, f1, data1, full_conc1),
                    (f2_val, x2, f2, data2, full_conc2),
                    (f3_val, x3, f3, data3, full_conc3),
                    (f_left_val, left_conc, f_left, data_left, full_conc_left),
                ]
                if (
                    f_right is not None and f_right > 0
                ):  # Исключаем невалидные результаты
                    all_values.append(
                        (f_right_val, right_conc, f_right, data_right, full_conc_right)
                    )

                best = max(all_values, key=lambda x: x[0])
                best_value = best[0]
                conc1 = max(params.min_conc, min(params.max_conc, best[1]))
                best_result = {
                    "conc1": conc1,
                    "conc2": available - best[1],
                    "value": best[2],
                    "data": best[3],
                    "full_concentrations": best[4],
                }
                oscillation_detected = False  # Сбрасываем при нахождении лучшей точки

                boundary_evaluated = True

            # Находим лучшую точку из трёх
            # Для всех режимов f_val уже преобразовано так, что "больше = лучше"
            # Исключаем невалидные результаты (температура = 0)
            best_local_idx = 0
            best_local_val = (
                f1_val
                if (params.mode == OptimizationMode.MINIMIZE and f1 > 0)
                or params.mode != OptimizationMode.MINIMIZE
                else float("-inf")
            )

            for i, (f_val, conc, f_orig) in enumerate(
                [(f2_val, full_conc2, f2), (f3_val, full_conc3, f3)]
            ):
                # Пропускаем невалидные результаты при минимизации
                if params.mode == OptimizationMode.MINIMIZE and f_orig <= 0:
                    continue
                if best_local_val == float("-inf") or f_val > best_local_val:
                    best_local_val = f_val
                    best_local_idx = i + 1

            # Если все точки невалидные, пропускаем итерацию
            if best_local_val == float("-inf"):
                no_improvement_count += 1
                continue

            # Записываем в историю с полными концентрациями
            best_local_conc = [full_conc1, full_conc2, full_conc3][best_local_idx]
            iter_data = {
                "iteration": iteration + 1,
                "conc1": [x1, x2, x3][best_local_idx],
                "conc2": available - [x1, x2, x3][best_local_idx],
                "value": [f1, f2, f3][best_local_idx],
                "target": params.target_value
                if params.mode == OptimizationMode.TARGET_VALUE
                else None,
                "full_concentrations": best_local_conc,
            }
            history.append(iter_data)

            # Проверяем на лучший результат
            # Для всех режимов "больше = лучше" (после преобразования)
            # Проверяем, что результат валидный (не 0 при минимизации)
            best_value_orig = [f1, f2, f3][best_local_idx]
            is_better = best_local_val > best_value and (
                params.mode != OptimizationMode.MINIMIZE or best_value_orig > 0
            )

            if is_better:
                best_value = best_local_val
                best_result = {
                    "conc1": [x1, x2, x3][best_local_idx],
                    "conc2": available - [x1, x2, x3][best_local_idx],
                    "value": [f1, f2, f3][best_local_idx],
                    "data": [data1, data2, data3][best_local_idx],
                    "full_concentrations": best_local_conc,
                }
                no_improvement_count = 0
                oscillation_detected = False  # Сбрасываем при улучшении
            else:
                no_improvement_count += 1

            # Если долго нет улучшений - переходим к лучшей точке
            if no_improvement_count > 3:
                conc1 = max(
                    params.min_conc, min(params.max_conc, [x1, x2, x3][best_local_idx])
                )
                no_improvement_count = 0
            else:
                # Находим экстремум квадратичной функции
                x_extremum = self._find_quadratic_extremum(
                    x1, x2, x3, f1_val, f2_val, f3_val
                )

                if x_extremum is not None and params.min_conc <= x_extremum <= min(
                    available, params.max_conc
                ):
                    # Вычисляем значение в экстремуме
                    f_extremum, data_extremum = self._evaluate(
                        x_extremum,
                        available - x_extremum,
                        params.other_concentrations,
                        params.comp1_idx,
                        params.comp2_idx,
                        point_name=f"e{iteration}",
                    )

                    full_conc_ext = self._build_full_concentrations(
                        x_extremum,
                        available - x_extremum,
                        params.other_concentrations,
                        params.comp1_idx,
                        params.comp2_idx,
                    )

                    # Преобразуем для сравнения
                    if params.mode == OptimizationMode.MINIMIZE:
                        f_extremum_val = -f_extremum
                    elif (
                        params.mode == OptimizationMode.TARGET_VALUE
                        and params.target_value is not None
                    ):
                        f_extremum_val = -abs(f_extremum - params.target_value)
                    else:
                        f_extremum_val = f_extremum

                    # Проверяем валидность результата и сравниваем
                    is_extremum_better = f_extremum_val > best_value
                    if params.mode == OptimizationMode.MINIMIZE:
                        is_extremum_better = is_extremum_better and f_extremum > 0

                    if is_extremum_better:
                        best_value = f_extremum_val
                        best_result = {
                            "conc1": x_extremum,
                            "conc2": available - x_extremum,
                            "value": f_extremum,
                            "data": data_extremum,
                            "full_concentrations": full_conc_ext,
                        }
                        conc1 = max(params.min_conc, min(params.max_conc, x_extremum))
                        no_improvement_count = 0
                        oscillation_detected = False  # Сбрасываем при улучшении

            # Проверяем сходимость
            # 1. Малый диапазон точек
            small_range = abs(x3 - x1) < params.tolerance

            # 2. Малые изменения концентрации (при наличии истории)
            small_conc_change = False
            if len(conc1_history) >= 3:
                recent_conc_change = abs(conc1_history[-1] - conc1_history[-3])
                small_conc_change = recent_conc_change < 1.0

            # 3. Малые изменения целевого значения
            small_value_change = False
            if len(history) >= 3:
                recent_values = [h["value"] for h in history[-3:]]
                value_range = max(recent_values) - min(recent_values)
                small_value_change = value_range < abs(
                    best_value * 0.01
                )  # 1% от значения

            # Завершаем, если выполнено несколько условий сходимости
            if small_range and (small_conc_change or small_value_change):
                break
            if oscillation_detected and step <= 1.5:
                break

            # Добавляем текущую концентрацию в историю
            conc1_history.append(conc1)
            if len(conc1_history) > 5:
                conc1_history.pop(0)

            iteration += 1

        # Формируем результат
        if best_result:
            return OptimizationResult(
                success=True,
                best_concentrations=best_result.get("full_concentrations", []),
                best_value=best_result["value"],
                iterations=iteration + 1,
                history=history,
                message=f"Найден оптимум: {params.target_param.value} = {best_result['value']:.2f}",
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

    def _find_quadratic_extremum(
        self,
        x1: float,
        x2: float,
        x3: float,
        f1: float,
        f2: float,
        f3: float,
    ) -> Optional[float]:
        """
        Нахождение экстремума квадратичной функции по трём точкам.

        Формула для вершины параболы, проходящей через (x1,f1), (x2,f2), (x3,f3):
        x = 0.5 * ((x2²-x3²)*f1 + (x3²-x1²)*f2 + (x1²-x2²)*f3) / ((x2-x3)*f1 + (x3-x1)*f2 + (x1-x2)*f3)

        Args:
            x1, x2, x3: Три точки по оси X.
            f1, f2, f3: Значения функции в этих точках.

        Returns:
            Координата X экстремума или None если парабола вырождена.
        """
        denom = (x2 - x3) * f1 + (x3 - x1) * f2 + (x1 - x2) * f3

        if abs(denom) < 1e-10:
            return None  # Парабола вырождена

        numerator = (
            (x2 * x2 - x3 * x3) * f1
            + (x3 * x3 - x1 * x1) * f2
            + (x1 * x1 - x2 * x2) * f3
        )

        x_extremum = 0.5 * numerator / denom

        return x_extremum

    def _golden_section_search(
        self, a: float, b: float, params: OptimizationParams, n_iter: int
    ) -> float:
        """Метод золотого сечения для поиска экстремума"""
        phi = (1 + math.sqrt(5)) / 2  # Золотое сечение

        other_sum = sum(params.other_concentrations)
        available = 100.0 - other_sum

        # Ограничиваем диапазон параметрами
        a = max(params.min_conc, min(params.max_conc, a))
        b = max(params.min_conc, min(params.max_conc, b))

        x1 = b - (b - a) / phi
        x2 = a + (b - a) / phi

        f1_orig, _ = self._evaluate(
            x1,
            available - x1,
            params.other_concentrations,
            params.comp1_idx,
            params.comp2_idx,
        )
        f2_orig, _ = self._evaluate(
            x2,
            available - x2,
            params.other_concentrations,
            params.comp1_idx,
            params.comp2_idx,
        )

        # Преобразуем значения в зависимости от режима
        # Для невалидных результатов (0 при минимизации) используем -inf
        if params.mode == OptimizationMode.MINIMIZE:
            f1 = -f1_orig if f1_orig > 0 else float("-inf")
            f2 = -f2_orig if f2_orig > 0 else float("-inf")
        elif (
            params.mode == OptimizationMode.TARGET_VALUE
            and params.target_value is not None
        ):
            f1 = -abs(f1_orig - params.target_value) if f1_orig > 0 else float("-inf")
            f2 = -abs(f2_orig - params.target_value) if f2_orig > 0 else float("-inf")
        else:
            f1, f2 = f1_orig, f2_orig

        for _ in range(n_iter):
            if f1 > f2:
                a = x1
                x1 = x2
                f1 = f2
                f1_orig = f2_orig
                x2 = a + (b - a) / phi
                x2 = max(params.min_conc, min(params.max_conc, x2))
                f2_orig, _ = self._evaluate(
                    x2,
                    available - x2,
                    params.other_concentrations,
                    params.comp1_idx,
                    params.comp2_idx,
                )
                # Преобразуем новое значение
                if params.mode == OptimizationMode.MINIMIZE:
                    f2 = -f2_orig if f2_orig > 0 else float("-inf")
                elif (
                    params.mode == OptimizationMode.TARGET_VALUE
                    and params.target_value is not None
                ):
                    f2 = (
                        -abs(f2_orig - params.target_value)
                        if f2_orig > 0
                        else float("-inf")
                    )
                else:
                    f2 = f2_orig
            else:
                b = x2
                x2 = x1
                f2 = f1
                f2_orig = f1_orig
                x1 = b - (b - a) / phi
                x1 = max(params.min_conc, min(params.max_conc, x1))
                f1_orig, _ = self._evaluate(
                    x1,
                    available - x1,
                    params.other_concentrations,
                    params.comp1_idx,
                    params.comp2_idx,
                )
                # Преобразуем новое значение
                if params.mode == OptimizationMode.MINIMIZE:
                    f1 = -f1_orig if f1_orig > 0 else float("-inf")
                elif (
                    params.mode == OptimizationMode.TARGET_VALUE
                    and params.target_value is not None
                ):
                    f1 = (
                        -abs(f1_orig - params.target_value)
                        if f1_orig > 0
                        else float("-inf")
                    )
                else:
                    f1 = f1_orig

        return max(params.min_conc, min(params.max_conc, (a + b) / 2))

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диалоговое окно для настройки и запуска оптимизации.

Предоставляет интерфейс для настройки параметров оптимизации
и отображения прогресса выполнения.
"""

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional

from core.optimizers.base_model import (
    OptimizationMode,
    OptimizationParams,
    OptimizationResult,
    OptimizationTarget,
)
from core.optimizers.grad import GradientOptimizerParams

logger = logging.getLogger(__name__)


class OptimizationDialog:
    """Диалоговое окно для настройки оптимизации"""

    def __init__(
        self,
        parent,
        component_names: List[str],
        current_params: Dict,
    ):
        self.parent = parent
        self.component_names = component_names
        self.current_params = current_params
        self.result: Optional[OptimizationResult] = None
        self._optimization_running = False
        self._stop_requested = False

        # Создание окна - используем root для Toplevel
        self.dialog = tk.Toplevel(parent.root)
        self.dialog.title("⚙️ Оптимизация состава")
        self.dialog.geometry("700x700")
        self.dialog.transient(parent.root)
        self.dialog.grab_set()

        # Центрирование
        self.dialog.update_idletasks()
        x = (parent.root.winfo_width() // 2) - (700 // 2)
        y = (parent.root.winfo_height() // 2) - (700 // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()
        self._load_components()

    def _create_widgets(self):
        """Создание виджетов окна"""

        # Главный контейнер с прокруткой
        main_canvas = tk.Canvas(self.dialog)
        scrollbar = ttk.Scrollbar(
            self.dialog, orient="vertical", command=main_canvas.yview
        )
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")),
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # === Секция 1: Целевой параметр ===
        target_frame = ttk.LabelFrame(
            scrollable_frame, text="🎯 Целевой параметр", padding=10
        )
        target_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(target_frame, text="Параметр для оптимизации:").grid(
            row=0, column=0, sticky="w", pady=5
        )

        self.target_var = tk.StringVar(value="temperature")
        target_combo = ttk.Combobox(
            target_frame,
            textvariable=self.target_var,
            values=[
                ("temperature", "Температура (K)"),
                ("enthalpy", "Энтальпия (кДж/кг)"),
                ("density", "Плотность (кг/м³)"),
                ("molar_mass", "Молярная масса (г/моль)"),
                ("adiabatic_index", "Показатель адиабаты"),
                ("volume_gas", "Объём газовой фазы (м³/кг)"),
            ],
            state="readonly",
            width=35,
        )
        target_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(target_frame, text="Режим:").grid(row=1, column=0, sticky="w", pady=5)

        self.mode_var = tk.StringVar(value="maximize")
        self.mode_var.trace_add("write", self._on_mode_changed)
        mode_frame = ttk.Frame(target_frame)
        mode_frame.grid(row=1, column=1, sticky="w", pady=5)
        ttk.Radiobutton(
            mode_frame, text="Максимизация", variable=self.mode_var, value="maximize"
        ).pack(side="left", padx=5)
        ttk.Radiobutton(
            mode_frame, text="Минимизация", variable=self.mode_var, value="minimize"
        ).pack(side="left", padx=5)
        ttk.Radiobutton(
            mode_frame,
            text="Достижение значения",
            variable=self.mode_var,
            value="target",
        ).pack(side="left", padx=5)

        # Поле для ввода целевого значения (скрыто по умолчанию)
        ttk.Label(target_frame, text="Целевое значение:").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.target_value_entry = ttk.Entry(target_frame, width=15)
        self.target_value_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.target_value_entry.insert(0, "0")

        ttk.Label(target_frame, text="Допуск (%):").grid(
            row=3, column=0, sticky="w", pady=5
        )
        self.target_tolerance_entry = ttk.Entry(target_frame, width=15)
        self.target_tolerance_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.target_tolerance_entry.insert(0, "1.0")

        # Скрываем поля для целевого режима
        self._on_mode_changed()

        # === Секция 2: Компоненты для оптимизации ===
        comp_frame = ttk.LabelFrame(
            scrollable_frame, text="🧪 Компоненты для оптимизации", padding=10
        )
        comp_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(comp_frame, text="Первый компонент:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.comp1_var = tk.StringVar()
        self.comp1_combo = ttk.Combobox(
            comp_frame, textvariable=self.comp1_var, state="readonly", width=35
        )
        self.comp1_combo.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(comp_frame, text="Второй компонент:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.comp2_var = tk.StringVar()
        self.comp2_combo = ttk.Combobox(
            comp_frame, textvariable=self.comp2_var, state="readonly", width=35
        )
        self.comp2_combo.grid(row=1, column=1, padx=5, pady=5)

        # === Секция 3: Параметры оптимизации ===
        opt_frame = ttk.LabelFrame(
            scrollable_frame, text="⚙️ Параметры оптимизации", padding=10
        )
        opt_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(opt_frame, text="Мин. концентрация (%):").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.min_conc_entry = ttk.Entry(opt_frame, width=15)
        self.min_conc_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.min_conc_entry.insert(0, "0")

        ttk.Label(opt_frame, text="Макс. концентрация (%):").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.max_conc_entry = ttk.Entry(opt_frame, width=15)
        self.max_conc_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.max_conc_entry.insert(0, "100")

        ttk.Label(opt_frame, text="Точность (%):").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.tolerance_entry = ttk.Entry(opt_frame, width=15)
        self.tolerance_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.tolerance_entry.insert(0, "0.5")

        ttk.Label(opt_frame, text="Макс. итераций:").grid(
            row=3, column=0, sticky="w", pady=5
        )
        self.max_iter_entry = ttk.Entry(opt_frame, width=15)
        self.max_iter_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.max_iter_entry.insert(0, "15")

        ttk.Label(opt_frame, text="Метод:").grid(row=4, column=0, sticky="w", pady=5)
        self.method_var = tk.StringVar(value="quadratic")
        method_combo = ttk.Combobox(
            opt_frame,
            textvariable=self.method_var,
            values=[
                "Квадратичная аппроксимация",
                "Градиентный метод",
            ],
            state="readonly",
            width=35,
        )
        method_combo.current(0)
        method_combo.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        method_combo.bind("<<ComboboxSelected>>", self._on_method_changed)

        # Словарь для сопоставления названий методов с ключами
        self.method_map = {
            "Квадратичная аппроксимация": "quadratic",
            "Градиентный метод": "gradient",
        }

        # Параметры для градиентного метода (скрыты по умолчанию)
        self.grad_params_frame = ttk.LabelFrame(
            opt_frame, text="⚙️ Параметры градиентного метода", padding=10
        )

        ttk.Label(self.grad_params_frame, text="Learning rate:").grid(
            row=0, column=0, sticky="w", pady=5
        )
        self.learning_rate_entry = ttk.Entry(self.grad_params_frame, width=15)
        self.learning_rate_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.learning_rate_entry.insert(0, "5.0")

        ttk.Label(self.grad_params_frame, text="Мин. learning rate:").grid(
            row=1, column=0, sticky="w", pady=5
        )
        self.min_learning_rate_entry = ttk.Entry(self.grad_params_frame, width=15)
        self.min_learning_rate_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        self.min_learning_rate_entry.insert(0, "0.5")

        ttk.Label(self.grad_params_frame, text="Макс. learning rate:").grid(
            row=2, column=0, sticky="w", pady=5
        )
        self.max_learning_rate_entry = ttk.Entry(self.grad_params_frame, width=15)
        self.max_learning_rate_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        self.max_learning_rate_entry.insert(0, "15.0")

        ttk.Label(self.grad_params_frame, text="Моментум:").grid(
            row=3, column=0, sticky="w", pady=5
        )
        self.momentum_entry = ttk.Entry(self.grad_params_frame, width=15)
        self.momentum_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        self.momentum_entry.insert(0, "0.8")

        self.use_momentum_var = tk.BooleanVar(value=True)
        self.momentum_check = ttk.Checkbutton(
            self.grad_params_frame,
            text="Использовать моментум",
            variable=self.use_momentum_var,
        )
        self.momentum_check.grid(row=4, column=0, columnspan=2, sticky="w", pady=5)

        self.grad_params_frame.grid(
            row=5, column=0, columnspan=2, sticky="ew", padx=5, pady=5
        )
        self.grad_params_frame.grid_remove()  # Скрыть по умолчанию

        # === Секция 4: Прогресс ===
        progress_frame = ttk.LabelFrame(
            scrollable_frame, text="📊 Прогресс оптимизации", padding=10
        )
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="indeterminate",
        )
        self.progress_bar.pack(fill="x", pady=5)

        self.status_label = ttk.Label(
            progress_frame, text="Ожидание запуска...", wraplength=500
        )
        self.status_label.pack(anchor="w")

        self.iteration_label = ttk.Label(progress_frame, text="Итерация: 0 / 0")
        self.iteration_label.pack(anchor="w")

        self.current_value_label = ttk.Label(progress_frame, text="Текущее значение: -")
        self.current_value_label.pack(anchor="w")

        # === Секция 5: Кнопки ===
        btn_frame = ttk.Frame(scrollable_frame, padding=10)
        btn_frame.pack(fill="x", padx=10, pady=10)

        self.start_btn = ttk.Button(
            btn_frame,
            text="▶ Запустить оптимизацию",
            command=self._start_optimization,
            width=25,
        )
        self.start_btn.pack(side="left", padx=5)

        self.stop_btn = ttk.Button(
            btn_frame,
            text="⏹ Стоп",
            command=self._stop_optimization,
            width=15,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=5)

        self.apply_btn = ttk.Button(
            btn_frame,
            text="✅ Применить",
            command=self._on_apply,
            width=15,
            state="disabled",
        )
        self.apply_btn.pack(side="left", padx=5)

        self.close_btn = ttk.Button(
            btn_frame, text="❌ Закрыть", command=self.dialog.destroy, width=15
        )
        self.close_btn.pack(side="left", padx=5)

    def _load_components(self):
        """Загрузка списка компонентов"""
        self.comp1_combo["values"] = self.component_names
        self.comp2_combo["values"] = self.component_names

        if self.component_names:
            self.comp1_combo.current(0)
            self.comp2_combo.current(1 if len(self.component_names) > 1 else 0)

    def _on_mode_changed(self, *args):
        """Обработчик изменения режима оптимизации"""
        use_target = self.mode_var.get() == "target"
        state = "normal" if use_target else "disabled"
        self.target_value_entry.config(state=state)
        self.target_tolerance_entry.config(state=state)

    def _on_method_changed(self, *args):
        """Обработчик изменения метода оптимизации"""
        selected_name = self.method_var.get()
        use_gradient = self.method_map.get(selected_name) == "gradient"
        if use_gradient:
            self.grad_params_frame.grid()
        else:
            self.grad_params_frame.grid_remove()

    def _start_optimization(self):
        """Запуск оптимизации"""
        if self._optimization_running:
            messagebox.showwarning("Предупреждение", "Оптимизация уже запущена")
            return

        # Проверка выбора компонентов
        if self.comp1_var.get() == self.comp2_var.get():
            messagebox.showerror("Ошибка", "Выбраны одинаковые компоненты")
            return

        # Получение параметров
        try:
            min_conc = float(self.min_conc_entry.get())
            max_conc = float(self.max_conc_entry.get())
            tolerance = float(self.tolerance_entry.get())
            max_iter = int(self.max_iter_entry.get())

            if min_conc < 0 or max_conc > 100 or min_conc >= max_conc:
                raise ValueError("Некорректный диапазон концентраций")

        except ValueError as e:
            messagebox.showerror("Ошибка", f"Некорректные параметры: {e}")
            return

        # Получение индексов компонентов
        comp1_idx = self.comp1_combo.current()
        comp2_idx = self.comp2_combo.current()

        if comp1_idx < 0 or comp2_idx < 0:
            messagebox.showerror("Ошибка", "Выберите компоненты")
            return

        # Блокировка интерфейса
        self._optimization_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.apply_btn.config(state="disabled")
        self.progress_bar.config(mode="indeterminate")
        self.progress_bar.start(10)

        # Создание параметров оптимизации
        # Получаем концентрации остальных компонентов из текущих параметров
        other_concentrations = self._get_other_concentrations(comp1_idx, comp2_idx)

        # Получаем целевое значение если выбран режим TARGET_VALUE
        target_value = None
        target_tolerance = 1.0
        if self.mode_var.get() == "target":
            try:
                target_value = float(self.target_value_entry.get())
                target_tolerance = float(self.target_tolerance_entry.get())
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректное целевое значение")
                return

        # Функция обратного вызова для обновления прогресса
        def on_iter_callback(iter_num, total, value, concentrations):
            self.parent.root.after(
                0,
                lambda: self._update_progress(iter_num, total, value, concentrations),
            )

        opt_params = OptimizationParams(
            target_param=OptimizationTarget(self.target_var.get()),
            mode=OptimizationMode(self.mode_var.get()),
            comp1_idx=comp1_idx,
            comp2_idx=comp2_idx,
            other_concentrations=other_concentrations,
            min_conc=min_conc,
            max_conc=max_conc,
            tolerance=tolerance,
            max_iterations=max_iter,
            target_value=target_value,
            target_tolerance=target_tolerance,
            on_iteration=on_iter_callback,
        )

        # Запуск в отдельном потоке
        thread = threading.Thread(
            target=self._run_optimization, args=(opt_params,), daemon=True
        )
        thread.start()

    def _get_other_concentrations(self, comp1_idx: int, comp2_idx: int) -> List[float]:
        """Получение концентраций остальных компонентов"""
        if not self.current_params or "variants" not in self.current_params:
            return []

        # Берем концентрации из первой вариации
        concentrations = self.current_params["variants"][0].get("concentrations", [])

        other_conc = []
        for i, conc in enumerate(concentrations):
            if i != comp1_idx and i != comp2_idx:
                other_conc.append(conc)

        return other_conc

    def _run_optimization(self, params: OptimizationParams):
        """Выполнение оптимизации в отдельном потоке"""
        try:
            # Создаем оптимизатор
            from core.optimizers.base_model import OptimizationManager
            from core.optimizers.grad import GradientOptimizer

            # Получаем ключ метода из названия
            method_key = self.method_map.get(self.method_var.get(), "quadratic")

            # Запускаем оптимизацию
            optimizer = OptimizationManager.create_optimizer(
                method=method_key,
                runner=self.parent.runner,
                ps_generator=self.parent.generator,
                work_dir=str(self.parent.work_dir),
                base_params=self.current_params,
            )

            # Для градиентного метода передаем дополнительные параметры
            if isinstance(optimizer, GradientOptimizer):
                try:
                    grad_params = GradientOptimizerParams(
                        learning_rate=float(self.learning_rate_entry.get()),
                        min_learning_rate=float(self.min_learning_rate_entry.get()),
                        max_learning_rate=float(self.max_learning_rate_entry.get()),
                        momentum=float(self.momentum_entry.get()),
                        use_momentum=self.use_momentum_var.get(),
                    )
                    result = optimizer.optimize(params, grad_params=grad_params)
                except ValueError as e:
                    raise ValueError(f"Некорректные параметры градиентного метода: {e}")
            else:
                result = optimizer.optimize(params)

            self.result = result

            # Обновляем UI после завершения
            self.parent.root.after(0, lambda: self._on_optimization_complete(result))

        except Exception as ex:
            import traceback

            error_detail = traceback.format_exc()
            logger.error(f"Ошибка оптимизации: {error_detail}")
            self.parent.root.after(0, lambda e=ex: self._on_optimization_error(str(e)))

    def _update_progress(self, iter_num: int, total: int, value: float, concentrations):
        """Обновление прогресса оптимизации"""
        self.status_label.config(text=f"Итерация {iter_num} из {total}")
        self.iteration_label.config(text=f"Итерация: {iter_num} / {total}")
        self.current_value_label.config(text=f"Текущее значение: {value:.4f}")

        # Отображаем концентрации если это список
        if isinstance(concentrations, list) and concentrations:
            conc_str = ", ".join([f"{c:.1f}" for c in concentrations])
            # Обновляем текст статуса с концентрациями
            self.status_label.config(
                text=f"Итерация {iter_num}: {value:.2f} | [{conc_str}%]"
            )

    def _on_optimization_complete(self, result):
        """Обработчик завершения оптимизации"""
        self._optimization_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_bar.stop()
        self.progress_bar.config(mode="determinate")
        self.progress_var.set(100)

        if result.success:
            # Формируем подробное сообщение с концентрациями
            conc_str = " | ".join([f"{c:.1f}%" for c in result.best_concentrations])
            msg = f"{result.message}\n\nКонцентрации:\n{conc_str}"
            self.status_label.config(text=f"✓ {result.message}")
            self.apply_btn.config(state="normal")
            messagebox.showinfo("Оптимизация завершена", msg)
        else:
            self.status_label.config(text="✗ Оптимизация не удалась")
            messagebox.showwarning("Оптимизация", result.message)

    def _on_optimization_error(self, error_msg: str):
        """Обработчик ошибки оптимизации"""
        self._optimization_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.progress_bar.stop()

        self.status_label.config(text="✗ Ошибка")
        messagebox.showerror("Ошибка оптимизации", error_msg)

    def _stop_optimization(self):
        """Остановка оптимизации"""
        if self._optimization_running:
            self._stop_requested = True
            self.status_label.config(text="⏹ Остановка...")
            self.stop_btn.config(state="disabled")

    def _on_apply(self):
        """Применение результатов оптимизации"""
        if self.result and self.result.success:
            # Возвращаем концентрации в родительское окно
            self.dialog.apply_result = {
                "concentrations": self.result.best_concentrations,
                "best_value": self.result.best_value,
            }
            self.dialog.destroy()
        else:
            messagebox.showwarning("Предупреждение", "Нет результатов для применения")

    def get_result(self) -> Optional[OptimizationResult]:
        """Получение результата оптимизации"""
        return self.result


def show_optimization_dialog(
    parent, component_names: List[str], current_params: Dict
) -> Optional[Dict]:
    """
    Показать диалог оптимизации

    Returns:
        Словарь с результатами или None
    """
    dialog = OptimizationDialog(parent, component_names, current_params)
    parent.root.wait_window(dialog.dialog)

    if hasattr(dialog.dialog, "apply_result"):
        return dialog.dialog.apply_result

    return None

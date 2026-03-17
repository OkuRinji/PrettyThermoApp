#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль построения графиков для результатов расчёта TERMO94
с использованием matplotlib
"""

import os
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

# Настройка matplotlib для работы с tkinter
import matplotlib

matplotlib.use("TkAgg")
from matplotlib import rcParams
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

# Настройка шрифтов и стилей
rcParams["font.family"] = "DejaVu Sans" if sys.platform != "win32" else "Arial"
rcParams["font.size"] = 10
rcParams["axes.labelsize"] = 11
rcParams["axes.titlesize"] = 12


@dataclass
class PlotData:
    """Данные для построения графика"""

    name: str  # Название серии данных
    x_values: List[float]  # Значения по оси X (номера вариаций или концентрация)
    y_values: List[float]  # Значения по оси Y (параметры)
    unit: str = ""  # Единицы измерения
    color: str = "#1f77b4"  # Цвет линии


class ResultsPlotter:
    """Класс для построения графиков результатов расчёта"""

    def __init__(
        self, parent, res_data_list: List, variants: Optional[List[Dict]] = None
    ):
        """
        Инициализация окна построения графиков

        Args:
            parent: Родительское окно
            res_data_list: Список объектов ResData с результатами расчётов (содержит List[Result])
            variants: Список вариаций с концентрациями компонентов
        """
        self.parent = parent
        self.res_data_list = res_data_list
        self.variants = variants or []
        self.dialog = None
        self.figure = None
        self.canvas = None
        self.axes = None

        # Выбранные параметры для отображения
        self.selected_params = {
            "temperature": tk.BooleanVar(value=True),
            "enthalpy": tk.BooleanVar(value=False),
            "entropy": tk.BooleanVar(value=False),
            "density": tk.BooleanVar(value=False),
            "molar_mass": tk.BooleanVar(value=False),
            "adiabatic_index": tk.BooleanVar(value=False),
            "volume_gas": tk.BooleanVar(value=False),
            "condensed_fraction": tk.BooleanVar(value=False),
        }

        # Цвета для графиков
        self.colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]

        # Подписи параметров
        self.param_labels = {
            "temperature": "Температура (K)",
            "enthalpy": "Энтальпия (кДж/кг)",
            "entropy": "Энтропия",
            "density": "Плотность (кг/м³)",
            "molar_mass": "Молярная масса (г/моль)",
            "adiabatic_index": "Показатель адиабаты",
            "volume_gas": "Объём газовой фазы (м³/кг)",
            "condensed_fraction": "Доля конденсата",
        }

        # Выбранный компонент для оси X
        self.x_axis_component = tk.StringVar(value="")
        self.component_vars: Dict[int, str] = {}  # Индекс компонента -> название

    def show_plot_dialog(self):
        """Открывает диалог построения графиков"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("📈 Графики результатов расчёта")
        self.dialog.geometry("1100x750")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Центрирование
        self.dialog.update_idletasks()
        x = (self.parent.winfo_width() // 2) - (1100 // 2)
        y = (self.parent.winfo_height() // 2) - (750 // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        """Создаёт виджеты окна графиков"""

        # Главный контейнер с разделением
        paned = ttk.PanedWindow(self.dialog, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # === Левая панель: управление ===
        left_frame = ttk.Frame(paned, padding=10)
        paned.add(left_frame, weight=1)

        # Заголовок
        ttk.Label(
            left_frame,
            text="Параметры для отображения:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w")

        # Параметры (чекбоксы)
        params_frame = ttk.LabelFrame(
            left_frame, text="Термодинамические параметры", padding=10
        )
        params_frame.pack(fill="x", pady=10)

        for param, var in self.selected_params.items():
            cb = ttk.Checkbutton(
                params_frame, text=self.param_labels[param], variable=var
            )
            cb.pack(anchor="w", pady=2)

        # Настройки графика
        settings_frame = ttk.LabelFrame(left_frame, text="Настройки", padding=10)
        settings_frame.pack(fill="x", pady=10)

        # Ось X - выбор компонента для концентрации
        ttk.Label(settings_frame, text="Ось X:").pack(anchor="w")
        self.x_axis_var = tk.StringVar(value="number")
        self.x_axis_var.trace_add("write", self._on_x_axis_changed)
        x_axis_frame = ttk.Frame(settings_frame)
        x_axis_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(
            x_axis_frame, text="№ вариации", variable=self.x_axis_var, value="number"
        ).pack(anchor="w")

        # Выпадающий список для выбора компонента
        conc_frame = ttk.Frame(settings_frame)
        conc_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(
            conc_frame,
            text="Концентрация:",
            variable=self.x_axis_var,
            value="concentration",
        ).pack(side="left")

        self.component_combo = ttk.Combobox(conc_frame, state="disabled", width=25)
        self.component_combo.pack(side="left", padx=5)
        self._populate_component_combo()

        # Тип графика
        ttk.Label(settings_frame, text="Тип графика:").pack(anchor="w")
        self.plot_type = tk.StringVar(value="line")
        type_frame = ttk.Frame(settings_frame)
        type_frame.pack(fill="x")
        ttk.Radiobutton(
            type_frame, text="Линейный", variable=self.plot_type, value="line"
        ).pack(anchor="w")
        ttk.Radiobutton(
            type_frame, text="Точечный", variable=self.plot_type, value="scatter"
        ).pack(anchor="w")
        ttk.Radiobutton(
            type_frame, text="Столбчатый", variable=self.plot_type, value="bar"
        ).pack(anchor="w")

        # Сетка
        self.show_grid = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Показывать сетку", variable=self.show_grid
        ).pack(anchor="w", pady=5)

        # Легенда
        self.show_legend = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            settings_frame, text="Показывать легенду", variable=self.show_legend
        ).pack(anchor="w")

        # Кнопки управления
        btn_frame = ttk.Frame(left_frame, padding=10)
        btn_frame.pack(fill="x", pady=10)

        ttk.Button(
            btn_frame, text="📊 Построить", command=self._build_plot, width=18
        ).pack(side="left", padx=3)
        ttk.Button(
            btn_frame, text="💾 Сохранить", command=self._save_plot, width=18
        ).pack(side="left", padx=3)
        ttk.Button(
            btn_frame, text="❌ Закрыть", command=self.dialog.destroy, width=18
        ).pack(side="left", padx=3)

        # Статус
        self.status_var = tk.StringVar(value="Выберите параметры и нажмите «Построить»")
        ttk.Label(left_frame, textvariable=self.status_var, wraplength=250).pack(
            anchor="w"
        )

        # === Правая панель: график ===
        right_frame = ttk.Frame(paned, padding=10)
        paned.add(right_frame, weight=3)

        # Создаём фигуру matplotlib
        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor="white")
        self.axes = self.figure.add_subplot(111)

        # Canvas для встраивания в tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, master=right_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Панель инструментов
        toolbar_frame = ttk.Frame(right_frame)
        toolbar_frame.pack(fill="x")
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()

    def _build_plot(self):
        """Строит график выбранных параметров"""
        # Собираем выбранные параметры
        selected = [param for param, var in self.selected_params.items() if var.get()]

        if not selected:
            messagebox.showwarning("Внимание", "Выберите хотя бы один параметр")
            return

        # Проверяем данные
        if not self.res_data_list or not self.res_data_list[0].calculations:
            messagebox.showwarning("Внимание", "Нет данных для построения графика")
            return

        # Собираем данные для графика
        plot_data = self._collect_plot_data(selected)

        # Очищаем текущий график
        self.axes.clear()

        # Строим график
        self._draw_matplotlib_plot(plot_data, selected)

        # Обновляем canvas
        self.canvas.draw()

        self.status_var.set(f"Построено графиков: {len(selected)}")

    def _on_x_axis_changed(self, *args):
        """Обработчик изменения оси X"""
        use_concentration = self.x_axis_var.get() == "concentration"
        if use_concentration:
            self.component_combo.config(state="readonly")
        else:
            self.component_combo.config(state="disabled")

    def _populate_component_combo(self):
        """Заполняет выпадающий список названиями компонентов"""
        # Получаем названия компонентов из параметров (если переданы)
        component_names = []

        # Ищем компоненты в self.variants_data или используем concentrations для определения количества
        if self.variants and len(self.variants) > 0:
            # Получаем количество компонентов из первой вариации
            concentrations = self.variants[0].get("concentrations", [])

            # Пытаемся получить названия компонентов из специального ключа
            first_variant = self.variants[0]
            if "component_names" in first_variant:
                component_names = first_variant["component_names"]
            else:
                # Генерируем названия по номерам
                for i in range(len(concentrations)):
                    component_names.append(f"Компонент {i + 1}")

            self.component_combo["values"] = component_names
            if component_names:
                self.component_combo.current(0)
                self.component_combo.config(state="readonly")
        else:
            self.component_combo["values"] = []
            self.component_combo.config(state="disabled")

    def _collect_plot_data(self, params: List[str]) -> Dict[str, PlotData]:
        """Собирает данные для графиков из результатов расчёта"""
        data = {}

        # Определяем значения для X-оси
        use_concentration = self.x_axis_var.get() == "concentration"
        calc_count = len(self.res_data_list[0].calculations)

        if use_concentration and self.variants:
            # Получаем индекс выбранного компонента
            try:
                comp_idx = self.component_combo.current()
                if comp_idx < 0:
                    comp_idx = 0
            except Exception:
                comp_idx = 0

            # Извлекаем концентрации выбранного компонента
            x_values = []
            for variant in self.variants:
                concentrations = variant.get("concentrations", [])
                if comp_idx < len(concentrations):
                    x_values.append(concentrations[comp_idx])
                else:
                    x_values.append(0)

            # Если вариаций меньше чем расчётов, дополняем номерами
            if len(x_values) < calc_count:
                x_values = list(range(1, calc_count + 1))
        else:
            # X-ось: номера вариаций
            x_values = list(range(1, calc_count + 1))

        color_idx = 0
        for param in params:
            y_values = []

            for calc in self.res_data_list[0].calculations:
                value = getattr(calc, param, 0)
                y_values.append(value if value else 0)

            units = {
                "temperature": "K",
                "enthalpy": "кДж/кг",
                "entropy": "",
                "density": "кг/м³",
                "molar_mass": "г/моль",
                "adiabatic_index": "",
                "volume_gas": "м³/кг",
                "condensed_fraction": "",
            }

            data[param] = PlotData(
                name=self.param_labels[param],
                x_values=x_values,
                y_values=y_values,
                unit=units.get(param, ""),
                color=self.colors[color_idx % len(self.colors)],
            )
            color_idx += 1

        return data

    def _draw_matplotlib_plot(
        self, plot_data: Dict[str, PlotData], selected: List[str]
    ):
        """Рисует график с помощью matplotlib"""

        plot_type = self.plot_type.get()

        for param, data in plot_data.items():
            if plot_type == "line":
                self.axes.plot(
                    data.x_values,
                    data.y_values,
                    marker="o",
                    linestyle="-",
                    linewidth=2,
                    markersize=6,
                    color=data.color,
                    label=data.name,
                )
            elif plot_type == "scatter":
                self.axes.scatter(
                    data.x_values,
                    data.y_values,
                    s=100,
                    alpha=0.7,
                    color=data.color,
                    label=data.name,
                    edgecolors="black",
                    linewidth=0.5,
                )
            elif plot_type == "bar":
                bar_width = 0.8 / len(selected)
                offset = (
                    list(plot_data.keys()).index(param) - len(selected) / 2 + 0.5
                ) * bar_width
                self.axes.bar(
                    [x + offset for x in data.x_values],
                    data.y_values,
                    width=bar_width,
                    color=data.color,
                    label=data.name,
                    alpha=0.8,
                    edgecolor="black",
                )

        # Настройка осей и сетки
        use_concentration = self.x_axis_var.get() == "concentration"
        if use_concentration and self.variants:
            comp_idx = self.component_combo.current()
            if comp_idx >= 0:
                comp_name = (
                    self.component_combo["values"][comp_idx]
                    if self.component_combo["values"]
                    else f"Компонент {comp_idx + 1}"
                )
                self.axes.set_xlabel(f"Концентрация: {comp_name} (%)", fontsize=11)
            else:
                self.axes.set_xlabel("Концентрация (%)", fontsize=11)
        else:
            self.axes.set_xlabel("№ вариации", fontsize=11)

        self.axes.set_ylabel("Значение", fontsize=11)
        self.axes.set_title(
            "Зависимость параметров от состава смеси", fontsize=12, fontweight="bold"
        )

        if self.show_grid.get():
            self.axes.grid(True, linestyle="--", alpha=0.7)

        if self.show_legend.get():
            self.axes.legend(loc="best", fontsize=9)

        # Поворот подписей по X
        self.axes.tick_params(axis="x", rotation=0)

        # Автоматическое масштабирование
        self.figure.tight_layout()

    def _save_plot(self):
        """Сохраняет график в файл"""
        if not self.figure:
            messagebox.showwarning("Внимание", "Сначала постройте график")
            return

        filepath = filedialog.asksaveasfilename(
            title="Сохранить график",
            defaultextension=".png",
            filetypes=[
                ("PNG изображение", "*.png"),
                ("PDF документ", "*.pdf"),
                ("SVG вектор", "*.svg"),
                ("Все файлы", "*.*"),
            ],
        )

        if filepath:
            try:
                # Определяем формат по расширению
                fmt = os.path.splitext(filepath)[1].lower().lstrip(".")
                if fmt not in ["png", "pdf", "svg", "jpg", "jpeg"]:
                    fmt = "png"

                # Сохраняем с высоким разрешением
                self.figure.savefig(
                    filepath,
                    format=fmt,
                    dpi=300,
                    bbox_inches="tight",
                    facecolor="white",
                    edgecolor="none",
                )
                messagebox.showinfo("Успех", f"График сохранён в:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось сохранить файл:\n{e}")


def show_results_plot(
    parent, res_data_list: List, variants: Optional[List[Dict]] = None
):
    """Удобная функция для показа графика результатов"""
    plotter = ResultsPlotter(parent, res_data_list, variants)
    plotter.show_plot_dialog()


if __name__ == "__main__":
    # Тестовый запуск с демонстрационными данными

    # Создаём тестовое окно
    root = tk.Tk()
    root.title("Test Plotter")
    root.geometry("800x600")

    # Тестовые данные
    class MockCalc:
        def __init__(self, id, t, i, s):
            self.id = id
            self.temperature = t
            self.enthalpy = i
            self.entropy = s
            self.pressure = 0.1
            self.density = 1.2
            self.molar_mass = 28.9
            self.adiabatic_index = 1.4
            self.volume_gas = 0.8
            self.condensed_fraction = 0.05

    class MockData:
        def __init__(self):
            self.calculations = [
                MockCalc(1, 2500, 5000, 7.5),
                MockCalc(2, 2600, 5100, 7.6),
                MockCalc(3, 2700, 5200, 7.7),
                MockCalc(4, 2650, 5150, 7.65),
                MockCalc(5, 2750, 5250, 7.75),
            ]

    # Показываем графики
    plotter = ResultsPlotter(root, [MockData()])
    plotter.show_plot_dialog()

    root.mainloop()

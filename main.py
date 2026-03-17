#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главный модуль приложения TERMO94.

Графический интерфейс для термодинамического расчета смесей.
"""

import logging
import sys
import tkinter as tk
from io import StringIO
from pathlib import Path
from tkinter import messagebox, ttk

from config_logging import setup_logging
from core.catalog_manager import CatalogManager
from core.ps_generator import PSGenerator
from core.res_parser import ResParser
from core.runner import OTVDMMRunner
from core.calc_organizer import Calculator
from gui.params_dialog import ParamsDialog
from models.res_component import ResData
from models.params import Params

logger = logging.getLogger(__name__)


def get_base_path() -> Path:
    """
    Получить базовый путь приложения.

    Returns:
        Путь к базовой директории (для exe - папка с exe, для .py - папка проекта).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


class ThermoApp:
    """
    Главное приложение TERMO94.

    Координирует работу GUI, загрузку каталога, генерацию PS файлов,
    запуск расчетов и отображение результатов.
    """

    def __init__(self, root: tk.Tk):
        """
        Инициализация приложения.

        Args:
            root: Корневое окно tkinter.
        """
        self.root = root
        self.root.title("Термодинамический расчет TERMO94")
        self.root.geometry("1100x750")

        # Пути
        self.base_path = get_base_path()
        self.work_dir = self.base_path / "TERMO"
        self.otvdm_path = self.base_path / r"otvdm-v0.9.0\otvdmw.exe"
        self.catalog_path = self.work_dir / "components.json"
        self.comp_ps_path = self.work_dir / "COMP.PS"

        # Инициализация компонентов
        self.catalog = CatalogManager()
        self.generator = PSGenerator(str(self.work_dir))
        self.runner = OTVDMMRunner(str(self.otvdm_path), str(self.work_dir))
        self.calculator: Calculator | None = None

        self.current_params = None

        self._init_catalog()
        self._create_widgets()

    def _init_catalog(self) -> None:
        """Инициализация каталога компонентов."""
        if self.catalog_path.exists():
            success = self.catalog.load_from_json(str(self.catalog_path))
            if not success:
                logger.warning("Не удалось загрузить каталог компонентов")
        else:
            logger.warning(f"Файл каталога не найден: {self.catalog_path}")
            messagebox.showwarning(
                "Внимание", f"Файл каталога не найден:\n{self.catalog_path}"
            )

    def _create_widgets(self) -> None:
        """Создание виджетов главного окна."""
        # Верхняя панель
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill="x")

        ttk.Button(
            top_frame, text="📝 Параметры", command=self._open_params_dialog, width=15
        ).pack(side="left", padx=5)
        self.fn_entry = tk.Entry(top_frame, width=12)
        self.fn_entry.pack(side="left", padx=5)
        self.fn_entry.insert(0, "New_file")
        ttk.Button(
            top_frame, text="▶ Запуск", command=self._run_calculation, width=15
        ).pack(side="left", padx=5)
        ttk.Button(
            top_frame, text="📊 Результаты", command=self._show_results, width=15
        ).pack(side="left", padx=5)
        ttk.Button(
            top_frame, text="📈 Графики", command=self._show_plots, width=15
        ).pack(side="left", padx=5)
        ttk.Button(
            top_frame, text="🔍 Оптимизация", command=self._run_optimization, width=15
        ).pack(side="left", padx=5)

        # Статус
        self.status_var = tk.StringVar(
            value=f"Готов к работе | Каталог: {self.catalog.get_count()} компонентов"
        )
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief="sunken", padding=5
        )
        status_bar.pack(fill="x", padx=5, pady=2)

        # Текст результатов
        self.output_text = tk.Text(
            self.root, height=35, width=130, font=("Consolas", 10)
        )
        self.output_text.pack(fill="both", expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(self.output_text, command=self.output_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.output_text.configure(yscrollcommand=scrollbar.set)

    def _open_params_dialog(self) -> None:
        """Открытие диалога параметров."""
        dialog = ParamsDialog(self.root, self.catalog, self.current_params)
        params = dialog.get_params()
        if params:
            self.current_params = params
            self.status_var.set(
                f"✓ Параметры загружены | Каталог: {self.catalog.get_count()}"
            )
            self._display_params_summary(params)
            logger.info("Параметры расчета загружены")

    def _display_params_summary(self, params: dict) -> None:
        """
        Отображение сводки параметров в текстовом поле.

        Args:
            params: Словарь параметров расчета.
        """
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", "=== ПАРАМЕТРЫ РАСЧЕТА ===\n\n")
        self.output_text.insert(
            "1.0", f"Исполнитель: {params.get('author', 'Каф. ТИПиКМ')}\n"
        )
        self.output_text.insert(
            "end",
            f"Директивы: {', '.join([k for k, v in params.get('directives', {}).items() if v])}\n",
        )
        self.output_text.insert(
            "end", f"PK={params.get('PK')}, PC={params.get('PC')}\n"
        )
        self.output_text.insert("end", f"Компонентов: {params.get('NB', 0)}\n")
        self.output_text.insert(
            "end", "     Компоненты           Энтальпия    Формула\n"
        )

        for comp in params["components"]:
            enthalpy_str = f"{comp['enthalpy']:>9.2f}"
            formula_str = comp["formula"]
            name = comp["name"]
            self.output_text.insert("end", f"{name}  {enthalpy_str}  {formula_str}\n")

        self.output_text.insert("end", "\nКонцентрации\n")
        for variant in params["variants"]:
            vid = variant["id"]
            conc = variant["concentrations"]
            self.output_text.insert("end", f"{vid}   {conc}\n")

    def _generate_ps(self) -> bool:
        """
        Генерация PS файла.

        Returns:
            True если файл успешно создан, иначе False.
        """
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return False

        try:
            fn = self.fn_entry.get()
            filepath = self.generator.generate(self.current_params, fn + ".ps")
            self.output_text.insert("end", f"\n✓ Файл создан: {filepath}\n")
            self.status_var.set("✓ .PS файл создан")
            logger.info(f"PS файл создан: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Ошибка генерации PS файла: {e}")
            messagebox.showerror("Ошибка", str(e))
            return False

    def _run_calculation(self) -> None:
        """Запуск расчета через Calculator."""
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return

        # Преобразуем текущие параметры в объект Params
        try:
            params = Params(
                author=self.current_params.get("author", "Белобородов"),
                code=self.current_params.get("code", "*"),
                directives=self.current_params.get("directives", {}),
                PK=self.current_params.get("PK", 0.1),
                PC=self.current_params.get("PC", 0.1),
                AL=self.current_params.get("AL", 0),
                N=self.current_params.get("N", 2),
                NB=self.current_params.get("NB", len(self.current_params.get("variants", []))),
                AL_N=self.current_params.get("AL_N", 0),
                AL_NB=self.current_params.get("AL_NB", 0),
                variants=self.current_params.get("variants", []),
                components=self.current_params.get("components", []),
                al_variants=self.current_params.get("al_variants", []),
            )
        except ValueError as e:
            logger.error(f"Ошибка валидации параметров: {e}")
            messagebox.showerror("Ошибка", f"Некорректные параметры:\n{e}")
            return

        # Создаем калькулятор
        self.calculator = Calculator(
            runner=self.runner,
            generator=self.generator,
            params=params,
            logger=logger,
            root=self.root,
            base_path=self.base_path,
        )

        # Блокируем кнопку запуска на время расчета
        self.status_var.set("⏳ Расчет выполняется...")
        logger.info(f"Запуск серии расчетов: {len(params.variants)} вариаций")

        def on_progress(current: int, total: int) -> None:
            self.root.after(
                0,
                lambda: self.status_var.set(f"⏳ Расчет: {current}/{total}"),
            )

        def on_complete(series) -> None:
            self.root.after(0, lambda: self._on_calc_complete(series))

        # Запускаем асинхронно
        self.calculator.run_all_async(
            on_progress=on_progress,
            on_complete=on_complete,
        )

    def _on_calc_complete(self, series) -> None:
        """
        Обработчик завершения серии расчетов.

        Args:
            series: ResultSeries с результатами.
        """
        if series and len(series) > 0:
            self.output_text.insert("end", f"\n✓ Серия расчетов завершена\n")
            self.output_text.insert("end", f"✓ Получено результатов: {len(series)}\n")
            self.status_var.set(f"✓ Расчет завершен: {len(series)} результатов")
            logger.info(f"Серия расчетов завершена: {len(series)} результатов")

            # Сохраняем последнюю серию для последующего отображения
            self.last_series = series
        else:
            logger.error("Ошибка расчета: нет результатов")
            messagebox.showerror("Ошибка", "Не удалось получить результаты расчета")
            self.status_var.set("✗ Ошибка расчета")

    def _load_results(self, fn: str) -> ResData | None:
        """
        Загрузка и парсинг результатов расчета.

        Args:
            fn: Имя файла расчета (без расширения).

        Returns:
            Распарсенные данные или None при ошибке.
        """
        res_path = self.work_dir / f"{fn}.res"

        if not res_path.exists():
            logger.warning(f"Файл результатов не найден: {res_path}")
            messagebox.showwarning("Внимание", f"Файл не найден:\n{res_path}")
            return None

        try:
            parser = ResParser(str(res_path))
            data = parser.parse()
            logger.info(f"Результаты загружены: {res_path}")
            return data
        except FileNotFoundError as e:
            logger.error(f"Файл не найден: {e}")
            messagebox.showerror("Ошибка", f"Файл не найден:\n{e}")
            return None
        except PermissionError as e:
            logger.error(f"Нет доступа к файлу: {e}")
            messagebox.showerror("Ошибка", f"Нет доступа:\n{e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка чтения результатов: {e}")
            messagebox.showerror("Ошибка", f"Не удалось прочитать результаты:\n{e}")
            return None

    def _show_results(self) -> None:
        """Показ результатов расчета."""
        # Сначала пробуем показать результаты из последней серии
        if hasattr(self, "last_series") and self.last_series and len(self.last_series) > 0:
            self._show_series_results(self.last_series)
            return

        # Если нет серии, пробуем загрузить из файла
        fn = self.fn_entry.get()
        data = self._load_results(fn)

        if not data:
            return

        try:
            output = StringIO()
            self._format_results(data, output)
            result_text = output.getvalue()

            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", result_text)
            self.status_var.set("✓ Результаты загружены")

        except Exception as e:
            logger.error(f"Ошибка форматирования результатов: {e}")
            self._show_raw_results(fn)

    def _show_series_results(self, series) -> None:
        """
        Показ результатов серии расчетов.

        Args:
            series: ResultSeries с результатами.
        """
        try:
            output = StringIO()
            self._format_series_results(series, output)
            result_text = output.getvalue()

            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", result_text)
            self.status_var.set(f"✓ Показано {len(series)} результатов")

        except Exception as e:
            logger.error(f"Ошибка форматирования серии: {e}")
            messagebox.showerror("Ошибка", f"Не удалось показать результаты:\n{e}")

    def _format_series_results(self, series, output: StringIO) -> None:
        """
        Форматирование результатов серии.

        Args:
            series: ResultSeries с результатами.
            output: StringIO объект для записи.
        """
        output.write("=" * 60 + "\n")
        output.write("СЕРИЯ РАСЧЕТОВ\n")
        output.write("=" * 60 + "\n\n")

        if series.mixture_name:
            output.write(f"Смесь: {series.mixture_name}\n")
        if series.mixture_density:
            output.write(f"Плотность смеси: {series.mixture_density}\n")
        output.write(f"Количество результатов: {len(series)}\n\n")

        if series.components:
            output.write("Компоненты:\n")
            output.write("-" * 40 + "\n")
            for comp in series.components:
                output.write(f"  {comp.name}: HF298 = {comp.hf298}\n")
            output.write("\n")

        if series.element_composition:
            output.write("Элементный состав:\n")
            output.write("-" * 40 + "\n")
            for elem, value in series.element_composition.items():
                output.write(f"  [{elem}]: {value:.6e}\n")
            output.write("\n")

        output.write("=" * 60 + "\n")
        output.write(f"РЕЗУЛЬТАТЫ ({len(series)} расчётов)\n")
        output.write("=" * 60 + "\n\n")

        for result in series:
            self._format_single_result(result, output)

    def _format_single_result(self, result, output: StringIO) -> None:
        """
        Форматирование одного результата из серии.

        Args:
            result: Result из серии.
            output: StringIO объект для записи.
        """
        output.write("=" * 60 + "\n")
        output.write(f"Расчёт #{result.id}\n")
        output.write("=" * 60 + "\n")

        if result.composition_percent:
            output.write(f"Концентрации: {result.composition_percent}\n")

        output.write("\nТермодинамические параметры:\n")
        output.write("-" * 40 + "\n")

        param_labels = {
            "pressure": ("Давление (P)", "МПа"),
            "temperature": ("Температура (T)", "K"),
            "enthalpy": ("Энтальпия (I)", "кДж/кг"),
            "entropy": ("Энтропия (S)", ""),
            "heat_capacity": ("Теплоемкость (C)", ""),
            "density": ("Плотность (R)", ""),
            "molar_mass": ("Молярная масса (M)", "г/моль"),
            "adiabatic_index": ("Показатель адиабаты (K)", ""),
            "volume_gas": ("Объём газовой фазы", "м³/кг"),
            "condensed_fraction": ("Доля конденсата (Z)", ""),
        }

        for attr, (label, unit) in param_labels.items():
            value = getattr(result, attr, None)
            if value:
                if unit:
                    output.write(f"  {label:<25} {value:>12.6e} {unit}\n")
                else:
                    output.write(f"  {label:<25} {value:>12.4f}\n")

        if result.equilibrium_gas:
            output.write("\nРавновесный состав газовой фазы:\n")
            output.write("-" * 40 + "\n")
            sorted_gas = sorted(result.equilibrium_gas.items(), key=lambda x: -x[1])[:30]
            for comp, value in sorted_gas:
                output.write(f"  {comp}: {value:.6e}\n")
            if len(result.equilibrium_gas) > 30:
                output.write(
                    f"  ... и ещё {len(result.equilibrium_gas) - 30} компонентов\n"
                )

        if result.equilibrium_condensed:
            output.write("\nКонденсированные продукты:\n")
            output.write("-" * 40 + "\n")
            for comp, value in sorted(
                result.equilibrium_condensed.items(), key=lambda x: -x[1]
            ):
                output.write(f"  {comp}*: {value:.6e}\n")

        if result.calculation_date:
            output.write(
                f"\nДата расчета: {result.calculation_date} {result.calculation_time}\n"
            )

        output.write("\n")

    def _format_results(self, data: ResData, output: StringIO) -> None:
        """
        Форматирование результатов расчета.

        Args:
            data: Распарсенные данные.
            output: StringIO объект для записи.
        """
        output.write("=" * 60 + "\n")
        output.write(f"Результаты расчета: {data.filename}\n")
        output.write("=" * 60 + "\n\n")

        if data.mixture_name:
            output.write(f"Смесь: {data.mixture_name}\n")
        if data.mixture_density:
            output.write(f"Плотность смеси: {data.mixture_density}\n\n")

        if data.components:
            output.write("Компоненты:\n")
            output.write("-" * 40 + "\n")
            for comp in data.components:
                output.write(f"  {comp.name}: HF298 = {comp.hf298}\n")
            output.write("\n")

        if data.element_composition:
            output.write("Элементный состав:\n")
            output.write("-" * 40 + "\n")
            for elem, value in data.element_composition.items():
                output.write(f"  [{elem}]: {value:.6e}\n")
            output.write("\n")

        output.write(f"Количество расчётов: {len(data.calculations)}\n\n")

        if data.calculations:
            for calc in data.calculations:
                self._format_single_calculation(calc, output)

    def _format_single_calculation(self, calc, output: StringIO) -> None:
        """Форматирование одного расчета."""
        output.write("=" * 60 + "\n")
        output.write(f"Расчёт #{calc.id}\n")
        output.write("=" * 60 + "\n")

        output.write("Термодинамические параметры:\n")
        output.write("-" * 40 + "\n")

        param_labels = {
            "pressure": ("Давление (P)", "МПа"),
            "temperature": ("Температура (T)", "K"),
            "enthalpy": ("Энтальпия (I)", "кДж/кг"),
            "entropy": ("Энтропия (S)", ""),
            "heat_capacity": ("Теплоемкость (C)", ""),
            "density": ("Плотность (R)", ""),
            "molar_mass": ("Молярная масса (M)", "г/моль"),
            "adiabatic_index": ("Показатель адиабаты (K)", ""),
            "volume_gas": ("Объём газовой фазы", "м³/кг"),
            "condensed_fraction": ("Доля конденсата (Z)", ""),
        }

        for attr, (label, unit) in param_labels.items():
            value = getattr(calc, attr, None)
            if value:
                if unit:
                    output.write(f"  {label:<25} {value:>12.6e} {unit}\n")
                else:
                    output.write(f"  {label:<25} {value:>12.4f}\n")

        if calc.equilibrium_gas:
            output.write("\nРавновесный состав газовой фазы:\n")
            output.write("-" * 40 + "\n")
            sorted_gas = sorted(calc.equilibrium_gas.items(), key=lambda x: -x[1])[:30]
            for comp, value in sorted_gas:
                output.write(f"  {comp}: {value:.6e}\n")
            if len(calc.equilibrium_gas) > 30:
                output.write(
                    f"  ... и ещё {len(calc.equilibrium_gas) - 30} компонентов\n"
                )

        if calc.equilibrium_condensed:
            output.write("\nКонденсированные продукты:\n")
            output.write("-" * 40 + "\n")
            for comp, value in sorted(
                calc.equilibrium_condensed.items(), key=lambda x: -x[1]
            ):
                output.write(f"  {comp}*: {value:.6e}\n")

        if calc.calculation_date:
            output.write(
                f"\nДата расчета: {calc.calculation_date} {calc.calculation_time}\n"
            )

    def _show_raw_results(self, fn: str) -> None:
        """Показ сырого файла результатов при ошибке парсинга."""
        res_path = self.work_dir / f"{fn}.res"
        try:
            with open(res_path, "r", encoding="cp1251", errors="replace") as f:
                raw = f.read()
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", raw[:10000])
        except Exception as e:
            logger.error(f"Ошибка чтения сырого файла: {e}")

    def _show_plots(self) -> None:
        """Показ графиков результатов."""
        # Сначала пробуем показать графики из последней серии
        if hasattr(self, "last_series") and self.last_series and len(self.last_series) > 0:
            self._show_series_plots(self.last_series)
            return

        # Если нет серии, пробуем загрузить из файла
        fn = self.fn_entry.get()
        data = self._load_results(fn)

        if not data:
            return

        try:
            if not data.calculations:
                messagebox.showinfo(
                    "Информация",
                    "В файле результатов нет расчётов для построения графика",
                )
                return

            variants = []
            if self.current_params and "variants" in self.current_params:
                variants = self.current_params["variants"].copy()
                if "components" in self.current_params:
                    component_names = [
                        comp.get("name", f"Компонент {i + 1}")
                        for i, comp in enumerate(self.current_params["components"])
                    ]
                    for variant in variants:
                        variant["component_names"] = component_names

            from gui.plotter import ResultsPlotter

            plotter = ResultsPlotter(self.root, [data], variants)
            plotter.show_plot_dialog()

            self.status_var.set("✓ Графики построены")
            logger.info("Графики построены")

        except Exception as e:
            logger.error(f"Ошибка построения графиков: {e}")
            messagebox.showerror("Ошибка", f"Не удалось построить графики:\n{e}")

    def _show_series_plots(self, series) -> None:
        """
        Показ графиков для серии результатов.

        Args:
            series: ResultSeries с результатами.
        """
        try:
            if not series.results:
                messagebox.showinfo(
                    "Информация",
                    "В серии нет результатов для построения графика",
                )
                return

            # Создаем ResData из серии для совместимости с plotter
            from models.res_component import ResData

            res_data = ResData(
                filename="series_results",
                mixture_name=series.mixture_name,
                mixture_density=series.mixture_density,
                components=series.components,
                element_composition=series.element_composition,
                calculations=series.results,
            )

            variants = []
            if self.current_params and "variants" in self.current_params:
                variants = self.current_params["variants"].copy()
                if "components" in self.current_params:
                    component_names = [
                        comp.get("name", f"Компонент {i + 1}")
                        for i, comp in enumerate(self.current_params["components"])
                    ]
                    for variant in variants:
                        variant["component_names"] = component_names

            from gui.plotter import ResultsPlotter

            plotter = ResultsPlotter(self.root, [res_data], variants)
            plotter.show_plot_dialog()

            self.status_var.set("✓ Графики построены")
            logger.info("Графики построены для серии")

        except Exception as e:
            logger.error(f"Ошибка построения графиков для серии: {e}")
            messagebox.showerror("Ошибка", f"Не удалось построить графики:\n{e}")

    def _run_optimization(self) -> None:
        """Запуск оптимизации состава."""
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return

        if not self.current_params.get("components"):
            messagebox.showwarning("Внимание", "Нет компонентов для оптимизации!")
            return

        component_names = [
            comp.get("name", f"Компонент {i + 1}")
            for i, comp in enumerate(self.current_params["components"])
        ]

        if len(component_names) < 2:
            messagebox.showwarning(
                "Внимание", "Для оптимизации нужно минимум 2 компонента!"
            )
            return

        from gui.optimization_dialog import show_optimization_dialog

        result = show_optimization_dialog(self, component_names, self.current_params)

        if result:
            self._apply_optimization_result(result)

    def _apply_optimization_result(self, result: dict) -> None:
        """
        Применение результатов оптимизации.

        Args:
            result: Словарь с результатами оптимизации.
        """
        if not self.current_params:
            return

        if (
            "variants" in self.current_params
            and len(self.current_params["variants"]) > 0
        ):
            self.current_params["variants"][0]["concentrations"] = result[
                "concentrations"
            ]

        self.output_text.insert("end", "\n=== РЕЗУЛЬТАТ ОПТИМИЗАЦИИ ===\n")
        self.output_text.insert("end", f"Лучшее значение: {result['best_value']:.4f}\n")
        self.output_text.insert("end", f"Концентрации: {result['concentrations']}\n")

        self.status_var.set("✓ Результаты оптимизации применены")
        logger.info(f"Оптимизация применена: {result['best_value']:.4f}")


if __name__ == "__main__":
    setup_logging(level=logging.INFO, log_file="thermo.log")

    root = tk.Tk()
    app = ThermoApp(root)
    root.mainloop()

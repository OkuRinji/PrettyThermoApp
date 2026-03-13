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
from tkinter import ttk, messagebox

from config_logging import setup_logging
from core.catalog_manager import CatalogManager
from core.ps_generator import PSGenerator
from core.res_parser import ResParser, ResData
from core.runner import OTVDMMRunner
from gui.params_dialog import ParamsDialog

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
        ttk.Button(
            top_frame, text="📄 Создать .PS", command=self._generate_ps, width=15
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
        self.output_text.insert("1.0", f"Исполнитель: {params.get('author', 'Каф. ТИПиКМ')}\n")
        self.output_text.insert(
            "end",
            f"Директивы: {', '.join([k for k, v in params.get('directives', {}).items() if v])}\n",
        )
        self.output_text.insert("end", f"PK={params.get('PK')}, PC={params.get('PC')}\n")
        self.output_text.insert("end", f"Компонентов: {params.get('NB', 0)}\n")
        self.output_text.insert("end", "     Компоненты           Энтальпия    Формула\n")

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

    def _generate_ps(self) -> None:
        """Генерация PS файла."""
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return

        try:
            fn = self.fn_entry.get()
            filepath = self.generator.generate(self.current_params, fn + ".ps")
            self.output_text.insert("end", f"\n✓ Файл создан: {filepath}\n")
            self.status_var.set("✓ .PS файл создан")
            logger.info(f"PS файл создан: {filepath}")
        except Exception as e:
            logger.error(f"Ошибка генерации PS файла: {e}")
            messagebox.showerror("Ошибка", str(e))

    def _run_calculation(self) -> None:
        """Запуск расчета."""
        fn = self.fn_entry.get()
        input_ps = self.work_dir / f"{fn}.ps"

        if not input_ps.exists():
            messagebox.showwarning("Внимание", "Сначала создайте .PS файл!")
            return

        # Блокируем кнопку запуска на время расчета
        self.status_var.set("⏳ Расчет выполняется...")
        logger.info(f"Запуск расчета: {fn}.ps")

        def on_calc_complete(success: bool) -> None:
            self.root.after(0, lambda: self._on_calc_complete(success, fn))

        self.runner.run(
            ps_file=fn, async_mode=True, hidden=False, on_complete=on_calc_complete
        )

    def _on_calc_complete(self, success: bool, fn: str) -> None:
        """
        Обработчик завершения расчета.

        Args:
            success: True если расчет успешен.
            fn: Имя файла расчета.
        """
        if success:
            self.output_text.insert("end", "\n✓ Расчет завершен\n")
            self.status_var.set("✓ Расчет завершен")
            logger.info(f"Расчет завершен: {fn}")
        else:
            logger.error(f"Ошибка расчета: {fn}")
            messagebox.showerror("Ошибка", "Не удалось запустить расчет")
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
                output.write(f"  ... и ещё {len(calc.equilibrium_gas) - 30} компонентов\n")

        if calc.equilibrium_condensed:
            output.write("\nКонденсированные продукты:\n")
            output.write("-" * 40 + "\n")
            for comp, value in sorted(calc.equilibrium_condensed.items(), key=lambda x: -x[1]):
                output.write(f"  {comp}*: {value:.6e}\n")

        if calc.calculation_date:
            output.write(f"\nДата расчета: {calc.calculation_date} {calc.calculation_time}\n")

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
        fn = self.fn_entry.get()
        data = self._load_results(fn)

        if not data:
            return

        try:
            if not data.calculations:
                messagebox.showinfo(
                    "Информация", "В файле результатов нет расчётов для построения графика"
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

            from core.plotter import ResultsPlotter
            plotter = ResultsPlotter(self.root, [data], variants)
            plotter.show_plot_dialog()

            self.status_var.set("✓ Графики построены")
            logger.info("Графики построены")

        except Exception as e:
            logger.error(f"Ошибка построения графиков: {e}")
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

        if "variants" in self.current_params and len(self.current_params["variants"]) > 0:
            self.current_params["variants"][0]["concentrations"] = result["concentrations"]

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

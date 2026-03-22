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
        # Главный контейнер с боковой панелью
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # === Левая панель управления ===
        control_frame = ttk.Frame(main_frame, padding=10)
        control_frame.pack(side="left", fill="y")

        # Заголовок
        ttk.Label(
            control_frame,
            text="Pyro 1.2",
            font=("TkDefaultFont", 12, "bold")
        ).pack(pady=(0, 15))

        # Кнопки управления
        ttk.Button(
            control_frame, text="📝 Задать параметры", command=self._open_params_dialog, width=20
        ).pack(pady=5, fill="x")

        # Поле имени файла
        fn_label = ttk.Label(control_frame, text="Имя файла:")
        fn_label.pack(pady=(15, 5))
        self.fn_entry = tk.Entry(control_frame, width=22)
        self.fn_entry.pack(pady=5, fill="x")
        self.fn_entry.insert(0, "New_file")

        # Кнопки действий
        ttk.Button(
            control_frame, text="▶ Запуск расчета", command=self._run_calculation, width=20
        ).pack(pady=5, fill="x")
        ttk.Button(
            control_frame, text="📊 Результаты расчета", command=self._show_results, width=20
        ).pack(pady=5, fill="x")
        ttk.Button(
            control_frame, text="📈 Построить график ", command=self._show_plots, width=20
        ).pack(pady=5, fill="x")
        ttk.Button(
            control_frame, text="🔍 Оптимизация", command=self._run_optimization, width=20
        ).pack(pady=5, fill="x")
        ttk.Button(
            control_frame, text="📂 Загрузить .res", command=self._load_res_files, width=20
        ).pack(pady=5, fill="x")

        # Разделитель
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=20)

        # Статус
        self.status_var = tk.StringVar(
            value=f"Каталог:\n{self.catalog.get_count()} комп."
        )
        status_label = ttk.Label(
            control_frame, textvariable=self.status_var, relief="sunken",
            padding=5, anchor="w", wraplength=180
        )
        status_label.pack(fill="x", side="bottom", pady=(20, 0))

        # === Правая панель - параметры и результаты ===
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        # === Панель текущих параметров (верхняя часть) ===
        params_frame = ttk.LabelFrame(right_frame, text="📋 Текущие параметры расчета", padding=10)
        params_frame.pack(fill="x", padx=5, pady=5)

        # Сетка для параметров
        self.params_info = {}

        # Строка 0: Давления
        ttk.Label(params_frame, text="PK (камера), МПа:", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.params_info["pk"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["pk"].grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="PC (срез), МПа:", font=("TkDefaultFont", 9, "bold")).grid(
            row=0, column=2, sticky="w", padx=5, pady=2
        )
        self.params_info["pc"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["pc"].grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # Строка 1: Количество компонентов и вариаций
        ttk.Label(params_frame, text="Компонентов:", font=("TkDefaultFont", 9, "bold")).grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.params_info["components_count"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["components_count"].grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="Вариаций:", font=("TkDefaultFont", 9, "bold")).grid(
            row=1, column=2, sticky="w", padx=5, pady=2
        )
        self.params_info["variants_count"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["variants_count"].grid(row=1, column=3, sticky="w", padx=5, pady=2)

        # Строка 2: Директивы
        ttk.Label(params_frame, text="Директивы:", font=("TkDefaultFont", 9, "bold")).grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.params_info["directives"] = ttk.Label(params_frame, text="—", anchor="w", width=40)
        self.params_info["directives"].grid(row=2, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        # Строка 3: Список компонентов (заголовок)
        ttk.Label(params_frame, text="Компоненты:", font=("TkDefaultFont", 9, "bold")).grid(
            row=3, column=0, sticky="nw", padx=5, pady=2
        )

        # Фрейм для списка компонентов в столбик
        components_list_frame = ttk.Frame(params_frame)
        components_list_frame.grid(row=3, column=1, columnspan=3, sticky="w", padx=5, pady=2)
        self.params_info["components_list_frame"] = components_list_frame
        self.params_info["components_labels"] = []

        # Разделитель
        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", padx=5, pady=5)

        # === Правая панель - результаты (нижняя часть) ===
        results_frame = ttk.Frame(right_frame)
        results_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Текст результатов
        self.output_text = tk.Text(
            results_frame, font=("Consolas", 10), padx=10, pady=10
        )
        self.output_text.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.output_text.yview)
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
            self._update_params_display(params)
            self._display_params_summary(params)
            logger.info("Параметры расчета загружены")

    def _update_params_display(self, params: dict) -> None:
        """
        Обновление отображения текущих параметров в виджетах.

        Args:
            params: Словарь параметров расчета.
        """
        # Давления
        self.params_info["pk"].config(text=f"{params.get('PK', 0):.3f}")
        self.params_info["pc"].config(text=f"{params.get('PC', 0):.3f}")

        # Количество компонентов и вариаций
        self.params_info["components_count"].config(
            text=str(params.get("NB", 0))
        )
        self.params_info["variants_count"].config(
            text=str(len(params.get("variants", [])))
        )

        # Директивы
        active_directives = [
            k for k, v in params.get("directives", {}).items() if v
        ]
        directives_str = ", ".join(active_directives) if active_directives else "—"
        self.params_info["directives"].config(text=directives_str)

        # Список компонентов - вывод столбиком
        components = params.get("components", [])
        list_frame = self.params_info["components_list_frame"]

        # Очищаем старые виджеты
        for widget in self.params_info.get("components_labels", []):
            widget.destroy()
        self.params_info["components_labels"] = []

        # Создаем новые метки для каждого компонента
        if components:
            for i, comp in enumerate(components):
                comp_name = comp.get("name", "—")
                if comp_name:
                    lbl = ttk.Label(list_frame, text=f"• {comp_name}", anchor="w")
                    lbl.grid(row=i, column=0, sticky="w", padx=2, pady=1)
                    self.params_info["components_labels"].append(lbl)
        else:
            lbl = ttk.Label(list_frame, text="—", anchor="w")
            lbl.grid(row=0, column=0, sticky="w", padx=2, pady=1)
            self.params_info["components_labels"].append(lbl)

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
            self.status_var.set(f"✓ Расчет завершен: {len(series)} результатов")
            logger.info(f"Серия расчетов завершена: {len(series)} результатов")

            # Сохраняем последнюю серию для последующего отображения
            self.last_series = series

            # Сразу выводим результаты на главный экран
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", "=== РЕЗУЛЬТАТЫ РАСЧЕТА ===\n\n")
            self.output_text.insert("end", f"✓ Серия расчетов завершена\n")
            self.output_text.insert("end", f"✓ Получено результатов: {len(series)}\n\n")

            # Форматируем и выводим все результаты
            output = StringIO()
            self._format_series_results(series, output)
            result_text = output.getvalue()
            self.output_text.insert("end", result_text)
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

    def _load_res_files(self) -> None:
        """
        Загрузка серии результатов из готовых .res файлов.

        Открывает диалог выбора файлов и загружает результаты из выбранных .res файлов.
        """
        from tkinter import filedialog

        # Открываем диалог выбора файлов
        filepaths = filedialog.askopenfilenames(
            title="Выберите .res файлы для загрузки",
            filetypes=[("Файлы результатов", "*.res"), ("Все файлы", "*.*")],
            initialdir=str(self.work_dir),
        )

        if not filepaths:
            return

        try:
            # Импортируем Calculator для использования метода загрузки
            from core.calc_organizer import Calculator

            # Загружаем серию из выбранных файлов
            series = Calculator.load_series_from_res_files(
                res_files=list(filepaths),
                params=None,  # Параметры можно загрузить отдельно если нужно
                logger=logger,
                base_path=self.base_path,
            )

            if len(series) > 0:
                # Сохраняем серию для последующего отображения
                self.last_series = series

                self.output_text.delete("1.0", "end")
                self.output_text.insert("1.0", "=== ЗАГРУЖЕНО ИЗ .RES ФАЙЛОВ ===\n")
                self.output_text.insert("end", f"✓ Загружено результатов: {len(series)}\n")
                self.output_text.insert("end", f"✓ Файлов обработано: {len(filepaths)}\n")
                
                if series.mixture_name:
                    self.output_text.insert("end", f"Смесь: {series.mixture_name}\n")
                if series.mixture_density:
                    self.output_text.insert("end", f"Плотность смеси: {series.mixture_density}\n")
                
                self.output_text.insert("end", "\n")
                
                # Форматируем и выводим результаты последовательно
                output = StringIO()
                self._format_series_results(series, output)
                result_text = output.getvalue()
                self.output_text.insert("end", result_text)
                
                self.status_var.set(f"✓ Загружено {len(series)} результатов из {len(filepaths)} файлов")
                logger.info(f"Загружено {len(series)} результатов из {len(filepaths)} .res файлов")
            else:
                messagebox.showwarning(
                    "Внимание",
                    "Не удалось загрузить результаты из выбранных файлов",
                )
                self.status_var.set("✗ Ошибка загрузки результатов")

        except Exception as e:
            logger.error(f"Ошибка загрузки .res файлов: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить файлы:\n{e}")
            self.status_var.set("✗ Ошибка загрузки")

    def _show_results(self) -> None:
        """Показ результатов расчета."""
        # Сначала пробуем показать результаты из последней серии
        if hasattr(self, "last_series") and self.last_series and len(self.last_series) > 0:
            self._show_series_table(self.last_series)
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

    def _show_series_table(self, series) -> None:
        """
        Показ результатов серии в виде таблицы.

        Args:
            series: ResultSeries с результатами.
        """
        # Создаем новое окно для таблицы
        table_window = tk.Toplevel(self.root)
        table_window.title("Результаты серии расчетов")
        table_window.geometry("1200x700")

        # Фрейм для таблицы и скроллов
        table_frame = ttk.Frame(table_window)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Создаем Treeview
        columns = (
            "id",
            "conc",
            "temperature",
            "pressure",
            "enthalpy",
            "density",
            "molar_mass",
            "adiabatic_index",
        )

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)

        # Настраиваем заголовки
        tree.heading("id", text="#")
        tree.heading("conc", text="Концентрации")
        tree.heading("temperature", text="T, K")
        tree.heading("pressure", text="P, МПа")
        tree.heading("enthalpy", text="I, кДж/кг")
        tree.heading("density", text="R")
        tree.heading("molar_mass", text="M, г/моль")
        tree.heading("adiabatic_index", text="K")

        # Настраиваем ширину колонок
        tree.column("id", width=40, anchor="center")
        tree.column("conc", width=150, anchor="w")
        tree.column("temperature", width=100, anchor="e")
        tree.column("pressure", width=90, anchor="e")
        tree.column("enthalpy", width=110, anchor="e")
        tree.column("density", width=90, anchor="e")
        tree.column("molar_mass", width=90, anchor="e")
        tree.column("adiabatic_index", width=80, anchor="e")

        # Добавляем скроллы
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        # Заполняем таблицу данными
        for result in series:
            # Формируем строку концентраций, если они есть
            if result.composition_percent:
                conc_str = ", ".join([f"{c:.1f}" for c in result.composition_percent])
            else:
                conc_str = "—"
            
            tree.insert(
                "",
                "end",
                values=(
                    result.id,
                    conc_str,
                    f"{result.temperature:.2f}",
                    f"{result.pressure:.6f}",
                    f"{result.enthalpy:.2f}",
                    f"{result.density:.6f}",
                    f"{result.molar_mass:.2f}",
                    f"{result.adiabatic_index:.4f}",
                ),
            )

        # Фрейм для кнопок
        btn_frame = ttk.Frame(table_window)
        btn_frame.pack(fill="x", padx=10, pady=5)

        def on_show_details():
            """Показать детали выбранного расчета."""
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Информация", "Выберите расчет в таблице")
                return

            item = tree.item(selection[0])
            result_id = int(item["values"][0])

            # Находим результат в серии
            result = series.get_result_by_id(result_id)
            if result:
                self._show_result_details(result, table_window)

        def on_export_csv():
            """Экспорт результатов в CSV."""
            from tkinter import filedialog
            import csv

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV файлы", "*.csv"), ("Все файлы", "*.*")],
                title="Сохранить результаты как...",
            )

            if file_path:
                try:
                    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        writer.writerow(
                            [
                                "ID",
                                "Концентрации",
                                "T, K",
                                "P, МПа",
                                "I, кДж/кг",
                                "R",
                                "M, г/моль",
                                "K",
                            ]
                        )
                        for result in series:
                            conc_str = ", ".join(
                                [f"{c:.1f}" for c in result.composition_percent]
                            )
                            writer.writerow(
                                [
                                    result.id,
                                    conc_str,
                                    f"{result.temperature:.2f}",
                                    f"{result.pressure:.6f}",
                                    f"{result.enthalpy:.2f}",
                                    f"{result.density:.6f}",
                                    f"{result.molar_mass:.2f}",
                                    f"{result.adiabatic_index:.4f}",
                                ]
                            )
                    messagebox.showinfo(
                        "Успешно", f"Результаты экспортированы в:\n{file_path}"
                    )
                    logger.info(f"Результаты экспортированы в CSV: {file_path}")
                except Exception as e:
                    logger.error(f"Ошибка экспорта CSV: {e}")
                    messagebox.showerror("Ошибка", f"Не удалось экспортировать:\n{e}")

        def on_close():
            table_window.destroy()

        ttk.Button(btn_frame, text="📋 Детали", command=on_show_details).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="💾 Экспорт CSV", command=on_export_csv).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Закрыть", command=on_close).pack(side="right", padx=5)

        # Статус
        status_label = ttk.Label(
            table_window,
            text=f"Всего результатов: {len(series)}",
            relief="sunken",
            padding=5,
        )
        status_label.pack(fill="x", padx=10, pady=2)

        self.status_var.set(f"✓ Показано {len(series)} результатов")

    def _show_result_details(self, result, parent_window) -> None:
        """
        Показ деталей выбранного результата в диалоговом окне.

        Args:
            result: Результат расчета.
            parent_window: Родительское окно.
        """
        details_window = tk.Toplevel(parent_window)
        details_window.title(f"Расчет #{result.id}")
        details_window.geometry("700x500")

        text_widget = tk.Text(details_window, height=30, width=80, font=("Consolas", 10))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)

        # Форматируем детали
        output = StringIO()
        output.write("=" * 60 + "\n")
        output.write(f"Расчёт #{result.id}\n")
        output.write("=" * 60 + "\n\n")

        if result.composition_percent:
            conc_str = ", ".join([f"{c:.1f}" for c in result.composition_percent])
            output.write(f"Концентрации: {conc_str}\n\n")

        output.write("Термодинамические параметры:\n")
        output.write("-" * 40 + "\n")
        output.write(f"  Давление (P)           {result.pressure:>12.6e} МПа\n")
        output.write(f"  Температура (T)        {result.temperature:>12.2f} K\n")
        output.write(f"  Энтальпия (I)          {result.enthalpy:>12.2f} кДж/кг\n")
        output.write(f"  Энтропия (S)           {result.entropy:>12.4f}\n")
        output.write(f"  Теплоемкость (C)       {result.heat_capacity:>12.4f}\n")
        output.write(f"  Плотность (R)          {result.density:>12.6e}\n")
        output.write(f"  Молярная масса (M)     {result.molar_mass:>12.2f} г/моль\n")
        output.write(f"  Показатель адиабаты (K){result.adiabatic_index:>12.4f}\n")
        output.write(f"  Объём газовой фазы     {result.volume_gas:>12.6e} м³/кг\n")
        output.write(f"  Доля конденсата (Z)    {result.condensed_fraction:>12.6f}\n")

        if result.equilibrium_gas:
            output.write("\nРавновесный состав газовой фазы (топ-30):\n")
            output.write("-" * 40 + "\n")
            sorted_gas = sorted(result.equilibrium_gas.items(), key=lambda x: -x[1])[:30]
            for comp, value in sorted_gas:
                output.write(f"  {comp}: {value:.6e}\n")

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

        text_widget.insert("1.0", output.getvalue())
        text_widget.configure(state="disabled")

        ttk.Button(details_window, text="Закрыть", command=details_window.destroy).pack(
            pady=5
        )

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

    def _format_series_results(self, series, output: StringIO) -> None:
        """
        Форматирование серии результатов для вывода в текстовое поле.

        Args:
            series: ResultSeries с результатами.
            output: StringIO объект для записи.
        """
        if series.mixture_name:
            output.write(f"Смесь: {series.mixture_name}\n")
        if series.mixture_density:
            output.write(f"Плотность смеси: {series.mixture_density}\n\n")

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

        output.write(f"Количество расчётов: {len(series)}\n\n")

        # Выводим все результаты последовательно
        for calc in series:
            self._format_single_calculation(calc, output)

    def _format_value(self, value: float, use_decimal: bool = False) -> str:
        """
        Форматирование числового значения.
        
        Преобразует числа из экспоненциальной записи в обычный формат.
        
        Args:
            value: Числовое значение.
            use_decimal: Если True, использовать десятичный формат, иначе - экспоненциальный.
        
        Returns:
            Отформатированная строка.
        """
        if use_decimal:
            # Для значений в диапазоне от 0.001 до 9999999 используем обычный формат
            if 0.001 <= abs(value) < 10000000:
                # Округляем до разумного количества знаков
                if value == int(value):
                    return f"{int(value)}"
                else:
                    return f"{value:.6f}".rstrip('0').rstrip('.')
            else:
                # Для очень больших/малых чисел используем экспоненциальный формат
                return f"{value:.6e}"
        else:
            # Для параметров без единиц измерения
            return f"{value:.4f}"

    def _format_single_calculation(self, calc, output: StringIO) -> None:
        """Форматирование одного расчета."""
        output.write("=" * 60 + "\n")
        output.write(f"Расчёт #{calc.id}\n")
        output.write("=" * 60 + "\n")

        output.write("Термодинамические параметры:\n")
        output.write("-" * 40 + "\n")

        param_labels = {
            "pressure": ("Давление (P)", "МПа", True),
            "temperature": ("Температура (T)", "K", True),
            "enthalpy": ("Энтальпия (I)", "кДж/кг", True),
            "entropy": ("Энтропия (S)", "", False),
            "heat_capacity": ("Теплоемкость (C)", "", False),
            "density": ("Плотность (R)", "", True),
            "molar_mass": ("Молярная масса (M)", "г/моль", True),
            "adiabatic_index": ("Показатель адиабаты (K)", "", False),
            "volume_gas": ("Объём газовой фазы", "м³/кг", True),
            "condensed_fraction": ("Доля конденсата (Z)", "", True),
        }

        for attr, (label, unit, use_decimal) in param_labels.items():
            value = getattr(calc, attr, None)
            if value:
                formatted_value = self._format_value(value, use_decimal)
                if unit:
                    output.write(f"  {label:<25} {formatted_value:>15} {unit}\n")
                else:
                    output.write(f"  {label:<25} {formatted_value:>15}\n")

        if calc.equilibrium_gas:
            output.write("\nРавновесный состав газовой фазы (Моль / КГ смеси):\n")
            output.write("-" * 40 + "\n")
            sorted_gas = sorted(calc.equilibrium_gas.items(), key=lambda x: -x[1])[:30]
            for comp, value in sorted_gas:
                output.write(f"  {comp}: {value:.6e}\n")
            if len(calc.equilibrium_gas) > 30:
                output.write(
                    f"  ... и ещё {len(calc.equilibrium_gas) - 30} компонентов\n"
                )

        if calc.equilibrium_condensed:
            output.write("\nКонденсированные продукты (Моль / КГ смеси):\n")
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

            # Формируем вариации для отображения концентраций
            variants = []
            if series.results and series.results[0].composition_percent:
                # Создаем вариации на основе концентраций из результатов
                for i, result in enumerate(series.results):
                    variants.append({
                        "id": result.id,
                        "concentrations": result.composition_percent,
                    })
            elif self.current_params and "variants" in self.current_params:
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

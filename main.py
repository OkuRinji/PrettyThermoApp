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
from core.calc_organizer import Calculator
from core.catalog_manager import CatalogManager
from core.ps_generator import PSGenerator
from core.res_parser import ResParser
from core.runner import OTVDMMRunner
from gui.params_dialog import ParamsDialog
from models.params import Params
from models.res_component import ResData
from models.results import ResultSeries

logger = logging.getLogger(__name__)


def get_base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


class ThermoApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Термодинамический расчет TERMO94")
        self.root.geometry("1100x750")

        self.base_path = get_base_path()
        self.work_dir = self.base_path / "TERMO"
        self.otvdm_path = self.base_path / r"otvdm-v0.9.0\otvdmw.exe"
        self.catalog_path = self.work_dir / "components.json"

        self.catalog = CatalogManager()
        self.generator = PSGenerator(str(self.work_dir))
        self.runner = OTVDMMRunner(str(self.otvdm_path), str(self.work_dir))
        self.calculator: Calculator | None = None
        self.current_params = None

        self._init_catalog()
        self._create_widgets()

    def _init_catalog(self) -> None:
        if self.catalog_path.exists():
            success = self.catalog.load_from_json(str(self.catalog_path))
            if not success:
                logger.warning("Не удалось загрузить каталог компонентов")
        else:
            logger.warning(f"Файл каталога не найден: {self.catalog_path}")
            messagebox.showwarning("Внимание", f"Файл каталога не найден:\n{self.catalog_path}")

    def _create_widgets(self) -> None:
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        control_frame = ttk.Frame(main_frame, padding=10)
        control_frame.pack(side="left", fill="y")

        ttk.Label(control_frame, text="ModernTermo", font=("TkDefaultFont", 12, "bold")).pack(pady=(0, 15))

        ttk.Button(control_frame, text="📝 Задать параметры", command=self._open_params_dialog, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="▶ Запуск расчета", command=self._run_calculation, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="📈 Построить график", command=self._show_plots, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="💾 Сохранить результаты", command=self._save_results, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="Скопировать результаты", command=self._copy_results, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="📂 Загрузить результаты", command=self._load_res_json_results, width=20).pack(pady=5, fill="x")
        ttk.Button(control_frame, text="📊 Таблица результатов", command=self._show_results, width=20).pack(pady=5, fill="x")

        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Button(control_frame, text="❓ Инструкция", command=self._show_help_window, width=20).pack(pady=5, fill="x")
        ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=20)

        self.status_var = tk.StringVar(value=f"Каталог:\n{self.catalog.get_count()} комп.")
        status_label = ttk.Label(control_frame, textvariable=self.status_var, relief="sunken", padding=5, anchor="w", wraplength=180)
        status_label.pack(fill="x", side="bottom", pady=(20, 0))

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)

        params_frame = ttk.LabelFrame(right_frame, text="📋 Текущие параметры расчета", padding=10)
        params_frame.pack(fill="x", padx=5, pady=5)

        self.params_info = {}
        ttk.Label(params_frame, text="PK (камера), МПа:", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.params_info["pk"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["pk"].grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="PC (срез), МПа:", font=("TkDefaultFont", 9, "bold")).grid(row=0, column=2, sticky="w", padx=5, pady=2)
        self.params_info["pc"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["pc"].grid(row=0, column=3, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="Компонентов:", font=("TkDefaultFont", 9, "bold")).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.params_info["components_count"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["components_count"].grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="Вариаций:", font=("TkDefaultFont", 9, "bold")).grid(row=1, column=2, sticky="w", padx=5, pady=2)
        self.params_info["variants_count"] = ttk.Label(params_frame, text="—", anchor="w", width=15)
        self.params_info["variants_count"].grid(row=1, column=3, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="Директивы:", font=("TkDefaultFont", 9, "bold")).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.params_info["directives"] = ttk.Label(params_frame, text="—", anchor="w", width=40)
        self.params_info["directives"].grid(row=2, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        ttk.Label(params_frame, text="Компоненты:", font=("TkDefaultFont", 9, "bold")).grid(row=3, column=0, sticky="nw", padx=5, pady=2)
        components_list_frame = ttk.Frame(params_frame)
        components_list_frame.grid(row=3, column=1, columnspan=3, sticky="w", padx=5, pady=2)
        self.params_info["components_list_frame"] = components_list_frame
        self.params_info["components_labels"] = []

        ttk.Separator(right_frame, orient="horizontal").pack(fill="x", padx=5, pady=5)

        results_frame = ttk.Frame(right_frame)
        results_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.output_text = tk.Text(results_frame, font=("Consolas", 10), padx=10, pady=10)
        self.output_text.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=self.output_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.output_text.configure(yscrollcommand=scrollbar.set)

        self._show_startup_instructions()

    def _open_params_dialog(self) -> None:
        dialog = ParamsDialog(self.root, self.catalog, self.current_params)
        params = dialog.get_params()
        if params:
            self.current_params = params
            self.status_var.set(f"✓ Параметры загружены | Каталог: {self.catalog.get_count()}")
            self._update_params_display(params)
            self._display_params_summary(params)
            logger.info("Параметры расчета загружены")

    def _update_params_display(self, params: dict) -> None:
        self.params_info["pk"].config(text=f"{params.get('PK', 0):.3f}")
        self.params_info["pc"].config(text=f"{params.get('PC', 0):.3f}")
        self.params_info["components_count"].config(text=str(params.get("NB", 0)))
        self.params_info["variants_count"].config(text=str(len(params.get("variants", []))))

        active_directives = [k for k, v in params.get("directives", {}).items() if v]
        self.params_info["directives"].config(text=", ".join(active_directives) if active_directives else "—")

        components = params.get("components", [])
        list_frame = self.params_info["components_list_frame"]
        for widget in self.params_info.get("components_labels", []):
            widget.destroy()
        self.params_info["components_labels"] = []

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

    def _reset_params_display(self) -> None:
        self.current_params = None
        for key in ["pk", "pc", "components_count", "variants_count", "directives"]:
            self.params_info[key].config(text="—")
        
        list_frame = self.params_info["components_list_frame"]
        for widget in self.params_info.get("components_labels", []):
            widget.destroy()
        self.params_info["components_labels"] = []
        lbl = ttk.Label(list_frame, text="—", anchor="w")
        lbl.grid(row=0, column=0, sticky="w", padx=2, pady=1)
        self.params_info["components_labels"].append(lbl)

    def _show_startup_instructions(self) -> None:
        instructions = """
╔═══════════════════════════════════════════════════════════════╗
║              ДОБРО ПОЖАЛОВАТЬ В ModernTermo (TERMO94)         ║
╠═══════════════════════════════════════════════════════════════╣
║  1. 📝 Нажмите "Задать параметры" для настройки расчета       ║
║  2. ▶ Нажмите "Запуск расчета" для выполнения                 ║
║  3. 📊 Результаты отобразятся в этом окне                     ║
║  4. 💾 Сохраните результаты в JSON или загрузите ранее        ║
╚═══════════════════════════════════════════════════════════════╝
"""
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", instructions)

    def _show_help_window(self) -> None:
        help_window = tk.Toplevel(self.root)
        help_window.title("📖 Инструкция по работе с TERMO94")
        help_window.geometry("700x550")
        
        help_text_widget = tk.Text(help_window, font=("Consolas", 10), padx=15, pady=15)
        help_text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        help_text_widget.insert("1.0", "Инструкция: используйте кнопки на главной панели для управления расчетами.")
        help_text_widget.configure(state="disabled")
        ttk.Button(help_window, text="Закрыть", command=help_window.destroy).pack(pady=(0, 10))

    def _display_params_summary(self, params: dict) -> None:
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", "=== ПАРАМЕТРЫ РАСЧЕТА ===\n\n")
        self.output_text.insert("1.0", f"Исполнитель: {params.get('author', 'Каф. ТИПиКМ')}\n")
        self.output_text.insert("end", f"Директивы: {', '.join([k for k, v in params.get('directives', {}).items() if v])}\n")
        self.output_text.insert("end", f"PK={params.get('PK')}, PC={params.get('PC')}\n")
        self.output_text.insert("end", f"Компонентов: {params.get('NB', 0)}\n")
        self.output_text.insert("end", "     Компоненты           Энтальпия    Формула\n")
        for comp in params["components"]:
            self.output_text.insert("end", f"{comp['name']}  {comp['enthalpy']:>9.2f}  {comp['formula']}\n")
        self.output_text.insert("end", "\nКонцентрации\n")
        for variant in params["variants"]:
            self.output_text.insert("end", f"{variant['id']}   {variant['concentrations']}\n")

    def _run_calculation(self) -> None:
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return

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
                outer_oxy=self.current_params.get("outer_oxy", []),
            )
        except ValueError as e:
            logger.error(f"Ошибка валидации параметров: {e}")
            messagebox.showerror("Ошибка", f"Некорректные параметры:\n{e}")
            return

        self.calculator = Calculator(
            runner=self.runner, generator=self.generator, params=params,
            logger=logger, root=self.root, base_path=self.base_path,
        )

        self.status_var.set("⏳ Расчет выполняется...")
        logger.info(f"Запуск серии расчетов: {len(params.variants)} вариаций")

        def on_progress(current: int, total: int) -> None:
            self.root.after(0, lambda: self.status_var.set(f"⏳ Расчет: {current}/{total}"))

        def on_complete(series) -> None:
            self.root.after(0, lambda: self._on_calc_complete(series))

        self.calculator.run_all_async(on_progress=on_progress, on_complete=on_complete)

    def _on_calc_complete(self, series: ResultSeries) -> None:
        if series and len(series) > 0:
            self.status_var.set(f"✓ Расчет завершен: {len(series)} результатов")
            self.last_series = series

            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", "=== РЕЗУЛЬТАТЫ РАСЧЕТА ===\n\n")
            self.output_text.insert("end", f"✓ Получено результатов: {len(series)}\n\n")

            output = StringIO()
            self._format_series_results(series, output)
            self.output_text.insert("end", output.getvalue())
        else:
            messagebox.showerror("Ошибка", "Не удалось получить результаты расчета")
            self.status_var.set("✗ Ошибка расчета")

    def _load_res_json_results(self) -> None:
        from tkinter import filedialog
        from models.results import ResultSeries

        filepaths = filedialog.askopenfilenames(
            title="Выберите файлы с результатами",
            filetypes=[("JSON файлы", "*.json"), ("Res файлы", "*.res"), ("Все файлы", "*.*")],
            initialdir=str(self.work_dir),
        )
        if not filepaths:
            return

        try:
            first_file = Path(filepaths[0])
            if first_file.suffix.lower() == ".json":
                series = ResultSeries.load_from_json(filepaths[0])
                file_type = "JSON"
            else:
                series = Calculator.load_series_from_res_files(
                    res_files=list(filepaths), params=None, logger=logger, base_path=self.base_path
                )
                file_type = "RES"

            self.last_series = series
            if len(series) > 0:
                params = series.params.to_dict() if hasattr(series, 'params') and series.params else None
                if params:
                    self._update_params_display(params)
                else:
                    self._reset_params_display()

                self.output_text.delete("1.0", "end")
                self.output_text.insert("1.0", f"=== ЗАГРУЖЕНО ИЗ {file_type} ФАЙЛА ===\n")
                self.output_text.insert("end", f"✓ Загружено результатов: {len(series)}\n")
                
                output = StringIO()
                self._format_series_results(series, output)
                self.output_text.insert("end", "\n" + output.getvalue())

                self.status_var.set(f"✓ Загружено {len(series)} результатов")
            else:
                messagebox.showwarning("Внимание", "Не удалось загрузить результаты")
        except Exception as e:
            logger.error(f"Ошибка загрузки файла: {e}")
            messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{e}")

    def _copy_results(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.output_text.get("1.0", tk.END))
        self.root.update()
        
    def _save_results(self) -> None:
        if not hasattr(self, "last_series") or not self.last_series or len(self.last_series) == 0:
            messagebox.showwarning("Внимание", "Нет результатов для сохранения.")
            return

        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            title="Сохранить результаты", defaultextension=".result",
            filetypes=[("Текстовый файл", "*.result"), ("Все файлы", "*.*")],
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.output_text.get("1.0", tk.END))
            self.last_series.save_to_json(filepath.replace(".result", ".json"))
            self.status_var.set(f"✓ Результаты сохранены: {filepath}")
            messagebox.showinfo("Успех", f"Результаты успешно сохранены:\n{filepath}")
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def _show_results(self) -> None:
        if hasattr(self, "last_series") and self.last_series and len(self.last_series) > 0:
            self._show_series_table(self.last_series)
        else:
            messagebox.showwarning("Внимание", "Сначала выполните расчет или загрузите результат")

    # =========================================================================
    # НОВЫЕ МЕТОДЫ ФОРМАТИРОВАНИЯ ДЛЯ РАЗДЕЛЬНЫХ СТОЛБЦОВ
    # =========================================================================
    def _format_single_value(self, value: float | None, decimals: int = 4, use_exp: bool = False) -> str:
        """Форматирует одно числовое значение."""
        if value is None:
            return "—"
        return f"{value:.{decimals}e}" if use_exp else f"{value:.{decimals}f}"

    def _format_list_value(self, value: float | list[float] | None, decimals: int = 4, use_exp: bool = False) -> str:
        """Обратная совместимость: форматирует список или одиночное значение."""
        if value is None:
            return "—"
        if isinstance(value, list):
            if not value:
                return "—"
            return ", ".join(self._format_single_value(v, decimals, use_exp) for v in value)
        return self._format_single_value(value, decimals, use_exp)

    def _show_series_table(self, series) -> None:
        table_window = tk.Toplevel(self.root)
        table_window.title("Результаты серии расчетов")
        table_window.geometry("1200x700")

        table_frame = ttk.Frame(table_window)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Определяем максимальное количество точек в серии
        max_points = 1
        for r in series:
            val = getattr(r, "pressure", None)
            pts = len(val) if isinstance(val, list) else 1
            if pts > max_points:
                max_points = pts

        # 2. Настраиваем колонки динамически
        base_columns = ("id", "conc")
        params_to_show = [
            ("temperature", "T, K", 2, False),
            ("pressure", "P, МПа", 6, True),
            ("enthalpy", "I, кДж/кг", 2, False),
            ("density", "R", 6, True),
            ("molar_mass", "M, г/моль", 2, False),
            ("adiabatic_index", "K", 4, False),
        ]

        columns = list(base_columns)
        col_headers = {"id": "#", "conc": "Концентрации"}
        col_widths = {"id": 40, "conc": 150}

        if max_points == 1:
            for attr, label, dec, use_exp in params_to_show:
                columns.append(attr)
                col_headers[attr] = label
                col_widths[attr] = 100
        else:
            for attr, label, dec, use_exp in params_to_show:
                for i in range(1, max_points + 1):
                    col_name = f"{attr}_{i}"
                    columns.append(col_name)
                    col_headers[col_name] = f"{label.split(',')[0]} {i}"
                    col_widths[col_name] = 90

        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=25)
        for col in columns:
            tree.heading(col, text=col_headers[col])
            tree.column(col, width=col_widths.get(col, 80), anchor="e" if col not in ["id", "conc"] else "w")

        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")
        tree.pack(side="left", fill="both", expand=True)

        # 3. Заполняем таблицу
        for result in series:
            conc_str = ", ".join([f"{c:.1f}" for c in result.composition_percent]) if result.composition_percent else "—"
            row_values = [result.id, conc_str]

            if max_points == 1:
                for attr, label, dec, use_exp in params_to_show:
                    val = getattr(result, attr, None)
                    row_values.append(self._format_list_value(val, decimals=dec, use_exp=use_exp))
            else:
                for attr, label, dec, use_exp in params_to_show:
                    val = getattr(result, attr, None)
                    if isinstance(val, list):
                        for i in range(max_points):
                            row_values.append(self._format_single_value(val[i], decimals=dec, use_exp=use_exp) if i < len(val) else "—")
                    else:
                        row_values.append(self._format_single_value(val, decimals=dec, use_exp=use_exp) if val is not None else "—")
                        for _ in range(1, max_points):
                            row_values.append("—")
            tree.insert("", "end", values=row_values)

        btn_frame = ttk.Frame(table_window)
        btn_frame.pack(fill="x", padx=10, pady=5)

        def on_show_details():
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Информация", "Выберите расчет в таблице")
                return
            item = tree.item(selection[0])
            result = series.get_result_by_id(int(item["values"][0]))
            if result:
                self._show_result_details(result, table_window)

        def on_export_csv():
            import csv
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV файлы", "*.csv")], title="Сохранить как..."
            )
            if file_path:
                try:
                    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        csv_headers = ["ID", "Концентрации"]
                        if max_points == 1:
                            for attr, label, dec, use_exp in params_to_show:
                                csv_headers.append(label)
                        else:
                            for attr, label, dec, use_exp in params_to_show:
                                for i in range(1, max_points + 1):
                                    csv_headers.append(f"{label.split(',')[0]} {i}")
                        writer.writerow(csv_headers)

                        for result in series:
                            conc_str = ", ".join([f"{c:.1f}" for c in result.composition_percent]) if result.composition_percent else "—"
                            row = [result.id, conc_str]
                            if max_points == 1:
                                for attr, label, dec, use_exp in params_to_show:
                                    row.append(self._format_list_value(getattr(result, attr, None), decimals=dec, use_exp=use_exp))
                            else:
                                for attr, label, dec, use_exp in params_to_show:
                                    val = getattr(result, attr, None)
                                    if isinstance(val, list):
                                        for i in range(max_points):
                                            row.append(self._format_single_value(val[i], decimals=dec, use_exp=use_exp) if i < len(val) else "—")
                                    else:
                                        row.append(self._format_single_value(val, decimals=dec, use_exp=use_exp) if val is not None else "—")
                                        for _ in range(1, max_points):
                                            row.append("—")
                            writer.writerow(row)
                    messagebox.showinfo("Успешно", f"Экспортировано в:\n{file_path}")
                except Exception as e:
                    logger.error(f"Ошибка экспорта CSV: {e}")
                    messagebox.showerror("Ошибка", f"Не удалось экспортировать:\n{e}")

        ttk.Button(btn_frame, text="📋 Детали", command=on_show_details).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="💾 Экспорт CSV", command=on_export_csv).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Закрыть", command=table_window.destroy).pack(side="right", padx=5)

        ttk.Label(table_window, text=f"Всего результатов: {len(series)}", relief="sunken", padding=5).pack(fill="x", padx=10, pady=2)
        self.status_var.set(f"✓ Показано {len(series)} результатов")

    def _show_result_details(self, result, parent_window) -> None:
        details_window = tk.Toplevel(parent_window)
        details_window.title(f"Расчет #{result.id}")
        details_window.geometry("800x600")

        text_widget = tk.Text(details_window, height=30, width=90, font=("Consolas", 10))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)

        output = StringIO()
        self._format_single_calculation(result, output)
        text_widget.insert("1.0", output.getvalue())
        text_widget.configure(state="disabled")

        ttk.Button(details_window, text="Закрыть", command=details_window.destroy).pack(pady=5)

    def _format_series_results(self, series: ResultSeries, output: StringIO) -> None:
        if series.mixture_name:
            output.write(f"Смесь: {series.mixture_name}\n")
        if series.mixture_density:
            output.write(f"Плотность смеси: {series.mixture_density}\n\n")

        output.write(f"Количество расчётов: {len(series)}\n\n")
        for calc in series:
            self._format_single_calculation(calc, output)

    def _format_single_calculation(self, calc, output: StringIO) -> None:
        """Форматирование одного расчета с таблицей по точкам."""
        output.write("=" * 70 + "\n")
        output.write(f"Расчёт #{calc.id}\n")
        output.write("=" * 70 + "\n")

        if calc.composition_percent:
            conc_str = ", ".join([f"{c:.1f}" for c in calc.composition_percent])
            output.write(f"Концентрации: {conc_str}\n\n")

        # Определяем количество точек
        max_points = 1
        for attr in ["pressure", "temperature", "enthalpy"]:
            val = getattr(calc, attr, None)
            if isinstance(val, list) and len(val) > max_points:
                max_points = len(val)

        param_labels = {
            "pressure": ("Давление (P), МПа", 6, True),
            "temperature": ("Температура (T), K", 2, False),
            "enthalpy": ("Энтальпия (I), кДж/кг", 2, False),
            "entropy": ("Энтропия (S)", 4, False),
            "heat_capacity": ("Теплоемкость (C)", 4, False),
            "density": ("Плотность (R)", 6, True),
            "molar_mass": ("Молярная масса (M), г/моль", 2, False),
            "adiabatic_index": ("Показатель адиабаты (K)", 4, False),
            "volume_gas": ("Объём газовой фазы, м³/кг", 6, True),
            "condensed_fraction": ("Доля конденсата (Z)", 6, False),
        }

        if max_points == 1:
            output.write("Термодинамические параметры:\n")
            output.write("-" * 40 + "\n")
            for attr, (label, dec, use_exp) in param_labels.items():
                value = getattr(calc, attr, None)
                if value is not None:
                    val = value[0] if isinstance(value, list) else value
                    formatted = self._format_single_value(val, decimals=dec, use_exp=use_exp)
                    output.write(f"  {label:<28} {formatted:>15}\n")
        else:
            output.write("Термодинамические параметры:\n")
            header = f"{'Параметр':<28}"
            for i in range(1, max_points + 1):
                header += f" | Точка {i:<10}"
            output.write(header + "\n")
            output.write("-" * (28 + 14 * max_points) + "\n")
            
            for attr, (label, dec, use_exp) in param_labels.items():
                value = getattr(calc, attr, None)
                row = f"{label:<28}"
                if isinstance(value, list):
                    for i in range(max_points):
                        val_str = self._format_single_value(value[i], decimals=dec, use_exp=use_exp) if i < len(value) else "—"
                        row += f" | {val_str:<10}"
                else:
                    val_str = self._format_single_value(value, decimals=dec, use_exp=use_exp) if value is not None else "—"
                    row += f" | {val_str:<10}"
                    for _ in range(1, max_points):
                        row += f" | {'—':<10}"
                output.write(row + "\n")
        output.write("\n")

        # Равновесный состав
        if calc.equilibrium_gas:
            output.write("Равновесный состав газовой фазы (Моль / КГ смеси):\n")
            if max_points == 1:
                output.write("-" * 40 + "\n")
                sorted_gas = sorted(calc.equilibrium_gas.items(), key=lambda x: -x[1][0] if isinstance(x[1], list) else -x[1])[:30]
                for comp, values in sorted_gas:
                    val = values[0] if isinstance(values, list) else values
                    output.write(f"  {comp}: {self._format_single_value(val, decimals=6, use_exp=True)}\n")
            else:
                header = f"{'Компонент':<12}"
                for i in range(1, max_points + 1):
                    header += f" | Точка {i:<10}"
                output.write(header + "\n")
                output.write("-" * (12 + 14 * max_points) + "\n")
                
                sorted_gas = sorted(calc.equilibrium_gas.items(), key=lambda x: -x[1][0] if isinstance(x[1], list) and x[1] else 0)[:30]
                for comp, values in sorted_gas:
                    row = f"{comp:<12}"
                    if isinstance(values, list):
                        for i in range(max_points):
                            val_str = self._format_single_value(values[i], decimals=6, use_exp=True) if i < len(values) else "—"
                            row += f" | {val_str:<10}"
                    else:
                        val_str = self._format_single_value(values, decimals=6, use_exp=True)
                        row += f" | {val_str:<10}"
                        for _ in range(1, max_points):
                            row += f" | {'—':<10}"
                    output.write(row + "\n")
                if len(calc.equilibrium_gas) > 30:
                    output.write(f"  ... и ещё {len(calc.equilibrium_gas) - 30} компонентов\n")
            output.write("\n")

        if calc.equilibrium_condensed:
            output.write("Конденсированные продукты (Моль / КГ смеси):\n")
            if max_points == 1:
                output.write("-" * 40 + "\n")
                sorted_cond = sorted(calc.equilibrium_condensed.items(), key=lambda x: -x[1][0] if isinstance(x[1], list) else -x[1])
                for comp, values in sorted_cond:
                    val = values[0] if isinstance(values, list) else values
                    output.write(f"  {comp}*: {self._format_single_value(val, decimals=6, use_exp=True)}\n")
            else:
                header = f"{'Компонент':<12}"
                for i in range(1, max_points + 1):
                    header += f" | Точка {i:<10}"
                output.write(header + "\n")
                output.write("-" * (12 + 14 * max_points) + "\n")
                
                sorted_cond = sorted(calc.equilibrium_condensed.items(), key=lambda x: -x[1][0] if isinstance(x[1], list) and x[1] else 0)
                for comp, values in sorted_cond:
                    row = f"{comp}*: {'':<8}" # Выравнивание имени
                    if isinstance(values, list):
                        for i in range(max_points):
                            val_str = self._format_single_value(values[i], decimals=6, use_exp=True) if i < len(values) else "—"
                            row += f" | {val_str:<10}"
                    else:
                        val_str = self._format_single_value(values, decimals=6, use_exp=True)
                        row += f" | {val_str:<10}"
                        for _ in range(1, max_points):
                            row += f" | {'—':<10}"
                    output.write(row + "\n")
            output.write("\n")

        if calc.calculation_date:
            output.write(f"Дата расчета: {calc.calculation_date} {calc.calculation_time}\n")

    def _show_plots(self) -> None:
        if hasattr(self, "last_series") and self.last_series and len(self.last_series) > 0:
            try:
                from models.res_component import ResData
                from gui.plotter import ResultsPlotter

                res_data = ResData(
                    filename="series_results", mixture_name=self.last_series.mixture_name,
                    mixture_density=self.last_series.mixture_density,
                    components=self.last_series.components,
                    element_composition=self.last_series.element_composition,
                    calculations=self.last_series.results,
                )
                variants = [{"id": r.id, "concentrations": r.composition_percent} for r in self.last_series.results if r.composition_percent]
                
                plotter = ResultsPlotter(self.root, [res_data], variants)
                plotter.show_plot_dialog()
                self.status_var.set("✓ Графики построены")
            except Exception as e:
                logger.error(f"Ошибка построения графиков: {e}")
                messagebox.showerror("Ошибка", f"Не удалось построить графики:\n{e}")
        else:
            messagebox.showwarning("Внимание", "Сначала выполните расчет или загрузите результат")


if __name__ == "__main__":
    setup_logging(level=logging.INFO, log_file="thermo.log")
    root = tk.Tk()
    app = ThermoApp(root)
    root.mainloop()
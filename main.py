## main.py
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from core.catalog_manager import CatalogManager
from core.ps_generator import PSGenerator
from core.res_parser import ResParser
from core.runner import DOSBoxRunner
from core.plotter import ResultsPlotter
from gui.params_dialog import ParamsDialog
import sys
from io import StringIO


def get_base_path():
    """Получить базовый путь: для exe - папка с exe, для .py - папка проекта"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent


class ThermoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Термодинамический расчет TERMO94")
        self.root.geometry("1100x750")

        # Пути - рабочая директория TERMO в проекте
        self.base_path = get_base_path()
        self.work_dir = self.base_path / "TERMO"
        self.dosbox_path = r"C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"
        self.catalog_path = self.work_dir / "components.json"
        self.comp_ps_path = self.work_dir / "COMP.PS"

        # Инициализация
        self.catalog = CatalogManager()
        self.generator = PSGenerator(str(self.work_dir))
        self.parser = None  # Создаётся при парсинге
        self.runner = DOSBoxRunner(self.dosbox_path, str(self.work_dir))

        self.current_params = None

        self._init_catalog()
        self._create_widgets()

    def _init_catalog(self):
        if self.catalog_path.exists():
            self.catalog.load_fromJson(str(self.catalog_path))
        else:
            messagebox.showwarning(
                "Внимание", f"Файл каталога не найден:\n{self.catalog_path}"
            )

    def _create_widgets(self):
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

    def _open_params_dialog(self):
        dialog = ParamsDialog(self.root, self.catalog, self.current_params)
        params = dialog.get_params()
        if params:
            self.current_params = params
            self.status_var.set(
                f"✓ Параметры загружены | Каталог: {self.catalog.get_count()}"
            )
            self._display_params_summary(params)

    def _display_params_summary(self, params):
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", "=== ПАРАМЕТРЫ РАСЧЕТА ===\n\n")
        self.output_text.insert("end", f"Исполнитель: {params.get('author', 'N/A')}\n")
        self.output_text.insert(
            "end",
            f"Директивы: {', '.join([k for k, v in params.get('directives', {}).items() if v])}\n",
        )
        self.output_text.insert(
            "end", f"PK={params.get('PK')}, PC={params.get('PC')}\n"
        )
        self.output_text.insert("end", f"Компонентов: {params.get('NB', 0)}\n")

    def _generate_ps(self):
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return
        try:
            fn = self.fn_entry.get()
            filepath = self.generator.generate(self.current_params, fn + ".ps")
            self.output_text.insert("end", f"\n✓ Файл создан: {filepath}\n")
            self.status_var.set("✓ .PS файл создан")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _run_calculation(self):
        fn = self.fn_entry.get()
        input_ps = self.work_dir / str(fn + ".ps")
        if not input_ps.exists():
            messagebox.showwarning("Внимание", "Сначала создайте .PS файл!")
            return
        self.status_var.set("⏳ Запуск расчета...")
        if self.runner.run():
            self.output_text.insert("end", "\n✓ Расчет завершен\n")
            self.status_var.set("✓ Расчет завершен")
        else:
            messagebox.showerror("Ошибка", "Не удалось запустить расчет")

    def _show_results(self):
        """Показывает результаты расчета"""
        fn = self.fn_entry.get()
        res_path = self.work_dir / f"{fn}.res"

        if not res_path.exists():
            messagebox.showwarning(
                "Внимание", f"Файл результатов не найден:\n{res_path}"
            )
            return
        try:
            # Парсим файл
            parser = ResParser(res_path)
            data = parser.parse()

            # Форматируем вывод
            output = StringIO()

            # Заголовок
            output.write("=" * 60 + "\n")
            output.write(f"Результаты расчета: {data.filename}\n")
            output.write("=" * 60 + "\n\n")

            if data.mixture_name:
                output.write(f"Смесь: {data.mixture_name}\n")
            if data.mixture_density:
                output.write(f"Плотность смеси: {data.mixture_density}\n\n")

            # Компоненты
            if data.components:
                output.write("Компоненты:\n")
                output.write("-" * 40 + "\n")
                for comp in data.components:
                    output.write(f"  {comp.name}: HF298 = {comp.hf298}\n")
                output.write("\n")

            # Элементный состав
            if data.element_composition:
                output.write("Элементный состав:\n")
                output.write("-" * 40 + "\n")
                for elem, value in data.element_composition.items():
                    output.write(f"  [{elem}]: {value:.6e}\n")
                output.write("\n")

            # Количество расчётов
            output.write(f"Количество расчётов: {len(data.calculations)}\n\n")

            # Показываем первый расчёт
            if data.calculations:
                for calc in data.calculations:
                    output.write("=" * 60 + "\n")
                    output.write(f"Расчёт #{calc.id}\n")
                    output.write("=" * 60 + "\n")

                    # Термодинамические параметры
                    output.write("Термодинамические параметры:\n")
                    output.write("-" * 40 + "\n")
                    if calc.pressure:
                        output.write(
                            f"  Давление (P):        {calc.pressure:.6e} МПа\n"
                        )
                    if calc.temperature:
                        output.write(
                            f"  Температура (T):     {calc.temperature:.2f} K\n"
                        )
                    if calc.enthalpy:
                        output.write(
                            f"  Энтальпия (I):       {calc.enthalpy:.2f} кДж/кг\n"
                        )
                    if calc.entropy:
                        output.write(f"  Энтропия (S):        {calc.entropy:.4f}\n")
                    if calc.heat_capacity:
                        output.write(
                            f"  Теплоемкость (C):    {calc.heat_capacity:.4f}\n"
                        )
                    if calc.density:
                        output.write(f"  Плотность (R):       {calc.density:.4f}\n")
                    if calc.molar_mass:
                        output.write(f"  Молярная масса (M):  {calc.molar_mass:.2f}\n")
                    if calc.adiabatic_index:
                        output.write(
                            f"  Показатель адиабаты (K): {calc.adiabatic_index:.4f}\n"
                        )
                    if calc.volume_gas:
                        output.write(f"  Объём газовой фазы:  {calc.volume_gas:.4f}\n")
                    if calc.condensed_fraction:
                        output.write(
                            f"  Доля конденсата (Z): {calc.condensed_fraction:.4f}\n"
                        )

                    # Равновесный состав газовой фазы
                    if calc.equilibrium_gas:
                        output.write("\nРавновесный состав газовой фазы:\n")
                        output.write("-" * 40 + "\n")
                        sorted_gas = sorted(
                            calc.equilibrium_gas.items(), key=lambda x: -x[1]
                        )[:30]
                        for comp, value in sorted_gas:
                            output.write(f"  {comp}: {value:.6e}\n")
                        if len(calc.equilibrium_gas) > 30:
                            output.write(
                                f"  ... и ещё {len(calc.equilibrium_gas) - 30} компонентов\n"
                            )

                    # Конденсированные продукты
                    if calc.equilibrium_condensed:
                        output.write("\nКонденсированные продукты:\n")
                        output.write("-" * 40 + "\n")
                        for comp, value in sorted(
                            calc.equilibrium_condensed.items(), key=lambda x: -x[1]
                        ):
                            output.write(f"  {comp}*: {value:.6e}\n")

                    # Дата/время
                    if calc.calculation_date:
                        output.write(
                            f"\nДата расчета: {calc.calculation_date} {calc.calculation_time}\n"
                        )

            # Выводим результат
            result_text = output.getvalue()
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", result_text)
            self.status_var.set("✓ Результаты загружены")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать результаты:\n{e}")
            # Пробуем показать сырой файл

            with open(res_path, "r", encoding="cp1251", errors="replace") as f:
                raw = f.read()
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", raw[:10000])

    def _show_plots(self):
        """Показывает графики результатов расчёта"""
        fn = self.fn_entry.get()
        res_path = self.work_dir / f"{fn}.res"

        if not res_path.exists():
            messagebox.showwarning(
                "Внимание", f"Файл результатов не найден:\n{res_path}"
            )
            return

        try:
            # Парсим файл
            parser = ResParser(res_path)
            data = parser.parse()

            if not data.calculations:
                messagebox.showinfo(
                    "Информация",
                    "В файле результатов нет расчётов для построения графика",
                )
                return

            # Показываем окно графиков
            plotter = ResultsPlotter(self.root, [data])
            plotter.show_plot_dialog()

            self.status_var.set("✓ Графики построены")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось построить графики:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ThermoApp(root)
    root.mainloop()

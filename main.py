## main.py
import tkinter as tk
from tkinter import ttk, messagebox
from core.catalog_manager import CatalogManager
from core.ps_generator import PSGenerator
from core.res_parser import RESParser
from core.runner import DOSBoxRunner
from gui.params_dialog import ParamsDialog
import os

class ThermoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Термодинамический расчет TERMO94")
        self.root.geometry("1100x750")
        
        # Пути
        self.work_dir = r"C:\THERMO"
        self.dosbox_path = r"C:\Program Files (x86)\DOSBox-0.74-3\DOSBox.exe"
        self.catalog_path = r"components.json"
        
        # Инициализация
        self.catalog = CatalogManager()
        self.generator = PSGenerator(self.work_dir)
        self.parser = RESParser(self.work_dir)
        self.runner = DOSBoxRunner(self.dosbox_path, self.work_dir)
        
        self.current_params = None
        
        self._init_catalog()
        self._create_widgets()
    
    def _init_catalog(self):
        if os.path.exists(self.catalog_path):
            self.catalog.load_fromJson(self.catalog_path)
        else:
            messagebox.showwarning("Внимание", f"Файл каталога не найден:\n{self.catalog_path}")
    
    def _create_widgets(self):
        # Верхняя панель
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill='x')
        
        ttk.Button(top_frame, text="📝 Параметры", command=self._open_params_dialog, width=15).pack(side='left', padx=5)
        ttk.Button(top_frame, text="📄 Создать .PS", command=self._generate_ps, width=15).pack(side='left', padx=5)
        ttk.Button(top_frame, text="▶ Запуск", command=self._run_calculation, width=15).pack(side='left', padx=5)
        ttk.Button(top_frame, text="📊 Результаты", command=self._show_results, width=15).pack(side='left', padx=5)
        
        # Статус
        self.status_var = tk.StringVar(value=f"Готов к работе | Каталог: {self.catalog.get_count()} компонентов")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken', padding=5)
        status_bar.pack(fill='x', padx=5, pady=2)
        
        # Текст результатов
        self.output_text = tk.Text(self.root, height=35, width=130, font=('Consolas', 10))
        self.output_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(self.output_text, command=self.output_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.output_text.configure(yscrollcommand=scrollbar.set)
    
    def _open_params_dialog(self):
        dialog = ParamsDialog(self.root, self.catalog, self.current_params)
        params = dialog.get_params()
        if params:
            self.current_params = params
            self.status_var.set(f"✓ Параметры загружены | Каталог: {self.catalog.get_count()}")
            self._display_params_summary(params)
    
    def _display_params_summary(self, params):
        self.output_text.delete('1.0', 'end')
        self.output_text.insert('1.0', "=== ПАРАМЕТРЫ РАСЧЕТА ===\n\n")
        self.output_text.insert('end', f"Исполнитель: {params.get('author', 'N/A')}\n")
        self.output_text.insert('end', f"Директивы: {', '.join([k for k, v in params.get('directives', {}).items() if v])}\n")
        self.output_text.insert('end', f"PK={params.get('PK')}, PC={params.get('PC')}\n")
        self.output_text.insert('end', f"Компонентов: {params.get('NB', 0)}\n")
    
    def _generate_ps(self):
        if not self.current_params:
            messagebox.showwarning("Внимание", "Сначала задайте параметры!")
            return
        try:
            filepath = self.generator.generate(self.current_params, 'input.ps')
            self.output_text.insert('end', f"\n✓ Файл создан: {filepath}\n")
            self.status_var.set("✓ .PS файл создан")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))
    
    def _run_calculation(self):
        if not os.path.exists(os.path.join(self.work_dir, 'input.ps')):
            messagebox.showwarning("Внимание", "Сначала создайте .PS файл!")
            return
        self.status_var.set("⏳ Запуск расчета...")
        if self.runner.run():
            self.output_text.insert('end', "\n✓ Расчет завершен\n")
            self.status_var.set("✓ Расчет завершен")
        else:
            messagebox.showerror("Ошибка", "Не удалось запустить расчет")
    
    def _show_results(self):
        results = self.parser.parse('input.res')
        if results:
            self.output_text.delete('1.0', 'end')
            self.output_text.insert('1.0', results['raw'][:10000])
            self.status_var.set("✓ Результаты загружены")
        else:
            messagebox.showwarning("Внимание", "Файл результатов не найден")

if __name__ == "__main__":
    root = tk.Tk()
    app = ThermoApp(root)
    root.mainloop()


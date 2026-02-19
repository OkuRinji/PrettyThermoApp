# gui/params_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, List
from core.catalog_manager import CatalogManager
from gui.component_search import ComponentSearchDialog

class ParamsDialog:
    """
    Диалоговое окно для ввода параметров расчета TERMO94
    """
    
    def __init__(self, parent, catalog: CatalogManager = None, initial_params: Optional[Dict] = None):
        self.parent = parent
        self.catalog = catalog or CatalogManager()
        self.initial_params = initial_params or self._get_default_params()
        self.result = None
        
        # Создание окна
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Параметры расчета TERMO94")
        self.dialog.geometry("950x750")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Центрирование
        self.dialog.update_idletasks()
        x = (parent.winfo_width() // 2) - (950 // 2)
        y = (parent.winfo_height() // 2) - (750 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        self._load_params(self.initial_params)
    
    def _get_default_params(self) -> Dict:
        """Возвращает параметры по умолчанию"""
        return {
            'author': '',
            'code': '*',
            'directives': {
                'LDY': False, 'LNN': True, 'TABL': True, 'WPS': True,
                'LVM': True, 'RMIN': '1.E-6'
            },
            'PK': 0.1,
            'PC': 0.1,
            'N': 1,
            'NB': 2,
            'variants': [{'id': 1, 'concentrations': [50.0, 50.0]}],
            'components': [
                {'id': 0, 'enthalpy': 0.0, 'formula': ''},
                {'id': 0, 'enthalpy': 0.0, 'formula': ''}
            ]
        }
    
    def _create_widgets(self):
        """Создает все виджеты окна"""
        
        # Главный контейнер с прокруткой
        main_canvas = tk.Canvas(self.dialog)
        scrollbar = ttk.Scrollbar(self.dialog, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # === Секция 1: Метаданные ===
        meta_frame = ttk.LabelFrame(scrollable_frame, text="📋 Метаданные", padding=10)
        meta_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(meta_frame, text="Исполнитель:").grid(row=0, column=0, sticky='w', pady=2)
        self.author_entry = ttk.Entry(meta_frame, width=40)
        self.author_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(meta_frame, text="Шифр:").grid(row=0, column=2, sticky='w', pady=2)
        self.code_entry = ttk.Entry(meta_frame, width=20)
        self.code_entry.grid(row=0, column=3, padx=5, pady=2)
        
        # === Секция 2: Директивы ===
        dir_frame = ttk.LabelFrame(scrollable_frame, text="⚙️ Директивы (NAMELIST RRP)", padding=10)
        dir_frame.pack(fill='x', padx=10, pady=5)
        
        self.directive_vars = {}
        directives_list = [
            ('LDY', 'Расчет параметров ДУ/генератора'),
            ('LNN', 'Концентрации в молях на 1 кг'),
            ('TABL', 'Оформление в виде таблицы'),
            ('WPS', 'Выдача состава продуктов'),
            ('LVM', 'Концентрации: газ-объем%, конд-масса%'),
            ('LMM', 'Концентрации в массовых долях'),
            ('LTF', 'Расчет теплопроводности и вязкости'),
        ]
        
        for i, (code, desc) in enumerate(directives_list):
            var = tk.BooleanVar(value=False)
            self.directive_vars[code] = var
            cb = ttk.Checkbutton(dir_frame, text=f"{code} - {desc}", variable=var)
            cb.grid(row=i//2, column=i%2, sticky='w', pady=1)
        
        # RMIN
        rmin_frame = ttk.Frame(dir_frame)
        rmin_frame.grid(row=len(directives_list)//2 + 1, column=0, columnspan=2, sticky='w', pady=5)
        ttk.Label(rmin_frame, text="RMIN (мин. концентрация):").pack(side='left')
        self.rmin_entry = ttk.Entry(rmin_frame, width=15)
        self.rmin_entry.pack(side='left', padx=5)
        self.rmin_entry.insert(0, '1.E-6')
        
        # === Секция 3: Параметры процесса ===
        proc_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Параметры процесса", padding=10)
        proc_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(proc_frame, text="PK - Давление в камере (МПа):").grid(row=0, column=0, sticky='w', pady=2)
        self.pk_entry = ttk.Entry(proc_frame, width=15)
        self.pk_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(proc_frame, text="PC - Давление на срезе (МПа):").grid(row=0, column=2, sticky='w', pady=2)
        self.pc_entry = ttk.Entry(proc_frame, width=15)
        self.pc_entry.grid(row=0, column=3, padx=5, pady=2)
        
        # === Секция 4: Рецептура ===
        recipe_frame = ttk.LabelFrame(scrollable_frame, text="🧪 Рецептура состава", padding=10)
        recipe_frame.pack(fill='x', padx=10, pady=5)
        
        # Количество компонентов
        count_frame = ttk.Frame(recipe_frame)
        count_frame.pack(fill='x', pady=5)
        
        ttk.Label(count_frame, text="Компонентов (NB):").pack(side='left', padx=5)
        self.nb_entry = ttk.Entry(count_frame, width=5)
        self.nb_entry.pack(side='left', padx=5)
        self.nb_entry.insert(0, "2")
        
        ttk.Button(count_frame, text="Применить", command=self._update_components_grid).pack(side='left', padx=20)
        
        # Сетка компонентов
        self.components_frame = ttk.Frame(recipe_frame)
        self.components_frame.pack(fill='x', pady=5)
        
        self.conc_entries = []
        self.id_entries = []
        self.formula_entries = []
        self.enthalpy_entries = []
        self.search_buttons = []
        
        self._create_components_grid()
        
        # === Секция 5: Кнопки ===
        btn_frame = ttk.Frame(scrollable_frame, padding=10)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="✅ ОК", command=self._on_ok, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="💾 Сохранить шаблон", command=self._save_template, width=18).pack(side='left', padx=5)
    
    def _create_components_grid(self):
        """Создает сетку для ввода компонентов"""
        for widget in self.components_frame.winfo_children():
            widget.destroy()
        
        try:
            nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
        except ValueError:
            nb = 2
        
        # Заголовки
        ttk.Label(self.components_frame, text="Компонент", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.components_frame, text="Конц. (%)", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(self.components_frame, text="ID", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=2, padx=5, pady=2)
        ttk.Label(self.components_frame, text="Формула", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(self.components_frame, text="Энтальпия", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=4, padx=5, pady=2)
        
        self.conc_entries = []
        self.id_entries = []
        self.formula_entries = []
        self.enthalpy_entries = []
        self.search_buttons = []
        
        for comp_idx in range(nb):
            # Кнопка поиска
            search_btn = ttk.Button(self.components_frame, text="🔍", width=3,
                                  command=lambda idx=comp_idx: self._open_component_search(idx))
            search_btn.grid(row=comp_idx+1, column=0, padx=3, pady=2)
            self.search_buttons.append(search_btn)
            
            # Концентрация
            conc_entry = ttk.Entry(self.components_frame, width=10)
            conc_entry.grid(row=comp_idx+1, column=1, padx=3, pady=2)
            conc_entry.insert(0, f"{100/nb:.1f}")
            self.conc_entries.append(conc_entry)
            
            # ID
            id_entry = ttk.Entry(self.components_frame, width=8)
            id_entry.grid(row=comp_idx+1, column=2, padx=3, pady=2)
            self.id_entries.append(id_entry)
            
            # Формула
            form_entry = ttk.Entry(self.components_frame, width=25)
            form_entry.grid(row=comp_idx+1, column=3, padx=3, pady=2)
            self.formula_entries.append(form_entry)
            
            # Энтальпия
            ent_entry = ttk.Entry(self.components_frame, width=12)
            ent_entry.grid(row=comp_idx+1, column=4, padx=3, pady=2)
            self.enthalpy_entries.append(ent_entry)
    
    def _update_components_grid(self):
        """Обновляет сетку компонентов"""
        self._create_components_grid()
    
    def _load_params(self, params: Dict):
        """Загружает параметры в виджеты"""
        self.author_entry.insert(0, params.get('author', ''))
        self.code_entry.insert(0, params.get('code', '*'))
        
        # Директивы
        for code, var in self.directive_vars.items():
            var.set(params.get('directives', {}).get(code, False))
        
        # RMIN
        self.rmin_entry.insert(0, params.get('directives', {}).get('RMIN', '1.E-6'))
        
        # Параметры процесса
        self.pk_entry.insert(0, str(params.get('PK', 0.1)))
        self.pc_entry.insert(0, str(params.get('PC', 0.1)))
        
        # Рецептура
        self.nb_entry.insert(0, str(params.get('NB', 2)))
        self._create_components_grid()
        
        # Компоненты
        components = params.get('components', [])
        variants = params.get('variants', [])
        
        for i, comp in enumerate(components):
            if i < len(self.formula_entries):
                self.id_entries[i].insert(0, str(comp.get('id', 0)))
                self.formula_entries[i].insert(0, comp.get('formula', ''))
                if comp.get('enthalpy') is not None:
                    self.enthalpy_entries[i].insert(0, f"{comp['enthalpy']:.2f}")
        
        if variants and len(variants) > 0:
            concs = variants[0].get('concentrations', [])
            for i, conc in enumerate(concs):
                if i < len(self.conc_entries):
                    self.conc_entries[i].delete(0, 'end')
                    self.conc_entries[i].insert(0, str(conc))
    
    def _open_component_search(self, comp_index: int):
        """Открывает диалог поиска компонента"""
        dialog = ComponentSearchDialog(self.dialog, self.catalog)
        component = dialog.get_component()
        
        if component:
            self.id_entries[comp_index].delete(0, 'end')
            self.id_entries[comp_index].insert(0, str(component.id))
            
            self.formula_entries[comp_index].delete(0, 'end')
            self.formula_entries[comp_index].insert(0, component.formula)
            
            if component.enthalpy is not None:
                self.enthalpy_entries[comp_index].delete(0, 'end')
                self.enthalpy_entries[comp_index].insert(0, f"{component.enthalpy:.2f}")
    
    def _on_ok(self):
        """Собирает данные и закрывает окно"""
        try:
            # Директивы
            directives = {}
            for code, var in self.directive_vars.items():
                directives[code] = var.get()
            directives['RMIN'] = self.rmin_entry.get().strip()
            
            # Параметры процесса
            params = {
                'author': self.author_entry.get().strip(),
                'code': self.code_entry.get().strip(),
                'directives': directives,
                'PK': float(self.pk_entry.get()),
                'PC': float(self.pc_entry.get()),
            }
            
            # Рецептура
            nb = int(self.nb_entry.get())
            params['NB'] = nb
            params['N'] = 1
            
            # Концентрации
            concentrations = []
            for entry in self.conc_entries:
                val = entry.get().strip()
                concentrations.append(float(val) if val else 0.0)
            params['variants'] = [{'id': 1, 'concentrations': concentrations}]
            
            # Компоненты
            components = []
            for i in range(nb):
                comp_id = int(self.id_entries[i].get().strip() or 0)
                formula = self.formula_entries[i].get().strip()
                enthalpy_str = self.enthalpy_entries[i].get().strip()
                enthalpy = float(enthalpy_str) if enthalpy_str else None
                
                components.append({
                    'id': comp_id,
                    'formula': formula,
                    'enthalpy': enthalpy
                })
            params['components'] = components
            
            self.result = params
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Ошибка ввода", f"Проверьте числовые значения:\n{e}")
    
    def _save_template(self):
        """Сохранение шаблона"""
        from tkinter import filedialog
        import json
        
        filepath = filedialog.asksaveasfilename(
            title="Сохранить шаблон",
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")]
        )
        if filepath:
            try:
                self._on_ok()
                if self.result:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(self.result, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("Успех", f"Шаблон сохранен:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
    
    def get_params(self) -> Optional[Dict]:
        """Возвращает результат после закрытия окна"""
        self.parent.wait_window(self.dialog)
        return self.result
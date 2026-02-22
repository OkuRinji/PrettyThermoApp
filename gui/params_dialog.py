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
                'LDY': False, 'LNN': True, 'TABL': True, 'WPS': False,
                'LVM': False, 'RMIN': '1.E-6'
            },
            'PK': 0.1,
            'PC': 0.1,
            'AL':0,
            'N': 1,
            'NB': 2,
            'AL_N': 1,
            'AL_NB': 1,
            'variants': [{'id': 1, 'concentrations': [50.0, 50.0]}],
            'components': [
                {'id': 0, 'name': '', 'enthalpy': 0.0, 'formula': ''},
                {'id': 0, 'name': '', 'enthalpy': 0.0, 'formula': ''}
            ],
            'AL_variants': [{'id': 1, 'concentrations': [100.]}],
        }
    
    def _create_widgets(self):
        """Создает все виджеты окна"""

        # Флаг изменения количества компонентов
        self.nb_changed = False

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

        # Прокрутка колесиком
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
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
        
        # === Секция 3: Параметры процесса ===
        proc_frame = ttk.LabelFrame(scrollable_frame, text="🔧 Параметры процесса", padding=10)
        proc_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(proc_frame, text="PK - Давление в камере (МПа):").grid(row=0, column=0, sticky='w', pady=2)
        self.pk_entry = ttk.Entry(proc_frame, width=15)
        self.pk_entry.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(proc_frame, text="PC - Давление на срезе (МПа):").grid(row=0, column=2, sticky='w', pady=2)
        self.pc_entry = ttk.Entry(proc_frame, width=15)
        self.pc_entry.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(proc_frame, text="AL - Участие внешнего окислителя").grid(row=1, column=0, sticky='w', pady=2)
        self.al_entry = ttk.Entry(proc_frame, width=15)
        self.al_entry.grid(row=1, column=1, padx=5, pady=2)
        self.al_entry.insert(0,"0")
        
        # === Секция 4: Рецептура ===
        recipe_frame = ttk.LabelFrame(scrollable_frame, text="🧪 Рецептура состава", padding=10)
        recipe_frame.pack(fill='x', padx=10, pady=5)
        
        # Количество компонентов
        count_frame = ttk.Frame(recipe_frame)
        count_frame.pack(fill='x', pady=5)
        
        ttk.Label(count_frame, text="Компонентов (NB):").pack(side='left', padx=5)
        self.nb_entry = ttk.Entry(count_frame, width=5)
        self.nb_entry.pack(side='left', padx=5)
        self.nb_entry.bind('<KeyRelease>', lambda e: self._on_nb_changed())

        ttk.Label(count_frame, text="Количество вариаций (Vars):").pack(side='left', padx=5)
        self.var_entry = ttk.Entry(count_frame, width=5)
        self.var_entry.pack(side='left', padx=5)
        
        
        ttk.Button(count_frame, text="Применить", command=self._update_components_grid).pack(side='left', padx=20)
        
        # Сетка компонентов
        self.components_frame = ttk.Frame(recipe_frame)
        self.components_frame.pack(fill='x', pady=5)
        self.variants_frame = ttk.Frame(recipe_frame)
        self.variants_frame.pack(fill='x', pady=5)

        self.conc_entries = []
        self.id_entries = []
        self.formula_entries = []
        self.enthalpy_entries = []
        self.search_buttons = []
        self.oxy_id_entries = []
        self.oxy_formula_entries = []
        self.oxy_enthalpy_entries = []
        self.oxy_search_buttons = []

        self._create_components_grid()
        
        # === Секция 5: Кнопки ===
        btn_frame = ttk.Frame(scrollable_frame, padding=10)
        btn_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Button(btn_frame, text="✅ ОК", command=self._on_ok, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="❌ Отмена", command=self.dialog.destroy, width=15).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="💾 Сохранить шаблон", command=self._save_template, width=18).pack(side='left', padx=5)


    def create_signle_comp_line(self, comp_idx, nb, start, is_oxy=False):
        """Создает одну строку компонента или окислителя"""
        # Кнопка поиска
        search_btn = ttk.Button(self.components_frame, text="Выберите компонент...", width=35,
                                command=lambda idx=comp_idx: self._open_component_search(idx, is_oxy=is_oxy))
        search_btn.grid(row=comp_idx+start, column=0, padx=3, pady=2)

        # ID - используем Label вместо Entry с визуальным оформлением
        id_label = ttk.Label(self.components_frame, text="", anchor='w', width=8, relief='sunken', padding=2)
        id_label.grid(row=comp_idx+start, column=2, padx=3, pady=2, sticky='ew')
        
        # Формула - Label
        form_label = ttk.Label(self.components_frame, text="", anchor='w', width=25, relief='sunken', padding=2)
        form_label.grid(row=comp_idx+start, column=3, padx=3, pady=2, sticky='ew')

        # Энтальпия - Label
        ent_label = ttk.Label(self.components_frame, text="", anchor='w', width=12, relief='sunken', padding=2)
        ent_label.grid(row=comp_idx+start, column=4, padx=3, pady=2, sticky='ew')
        
        # Добавляем в соответствующий список
        if is_oxy:

            self.oxy_id_entries.append(id_label)
            self.oxy_formula_entries.append(form_label)
            self.oxy_enthalpy_entries.append(ent_label)
            self.oxy_search_buttons.append(search_btn)
        else:
            self.id_entries.append(id_label)
            self.formula_entries.append(form_label)
            self.enthalpy_entries.append(ent_label)
            self.search_buttons.append(search_btn)

        
    def _create_components_grid(self):
        """Создает сетку для ввода компонентов"""
        for widget in self.components_frame.winfo_children():
            widget.destroy()
        for widget in self.variants_frame.winfo_children():
            widget.destroy()

        try:
            nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
        except ValueError:
            nb = 2

        try:
            var_cnt=int(self.var_entry.get()) if self.var_entry.get() else 1
        except ValueError:
            var_cnt=1

        # Заголовки
        ttk.Label(self.components_frame, text="Компонент", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.components_frame, text="ID", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=2, padx=5, pady=2)
        ttk.Label(self.components_frame, text="Формула", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(self.components_frame, text="Энтальпия", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=4, padx=5, pady=2)

        # Инициализируем списки для компонентов и окислителей
        self.conc_entries = []
        self.id_entries = []  # Основные компоненты
        self.formula_entries = []
        self.enthalpy_entries = []
        self.search_buttons = []
        self.oxy_id_entries = []  # Внешние окислители
        self.oxy_formula_entries = []
        self.oxy_enthalpy_entries = []
        self.oxy_search_buttons = []

        # Сначала основные компоненты смеси
        ttk.Label(self.components_frame, text="Компоненты смеси", font=('TkDefaultFont', 9, 'bold')).grid(row=1, column=0, padx=5, pady=2)
        start = 2
        for comp_idx in range(nb):
            self.create_signle_comp_line(comp_idx, nb, start, is_oxy=False)

        # Затем внешний окислитель (если есть)
        if self.al_entry.get() != "0":
            ttk.Label(self.components_frame, text="Внешний окислитель", font=('TkDefaultFont', 9, 'bold')).grid(row=start+nb, column=0, padx=5, pady=2)
            self.create_signle_comp_line(0, 1, start+nb+1, is_oxy=True)

        # Сетка вариаций
        ttk.Label(self.variants_frame, text="№ Вариации", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(self.variants_frame, text="Компонент", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(self.variants_frame, text="Конц. (%)", font=('TkDefaultFont', 9, 'bold')).grid(row=0, column=2, padx=5, pady=2)
        
        for var_num in range(var_cnt):
            self.conc_entries.append([])
            # Разделитель между вариациями (перед вариацией, кроме первой)
            if var_num > 0:
                ttk.Separator(self.variants_frame, orient='horizontal').grid(
                    row=var_num*(nb+1), column=0, columnspan=3, sticky='ew', pady=(15, 5))

            # Номер вариации с рамкой (смещаем строку на количество сепараторов)
            var_row = var_num * (nb + 1) + 1
            var_label = ttk.Label(
                self.variants_frame,
                text=str(var_num+1),
                font=('TkDefaultFont', 9, 'bold'),
                relief='ridge',
                padding=5,
                borderwidth=2
            )
            var_label.grid(row=var_row, column=0, rowspan=nb, padx=3, pady=3, sticky='ns')
            
            for comp in range(nb):
                # Получаем название компонента из кнопки
                comp_name = "Комп. " + str(comp+1)
                if comp < len(self.search_buttons):
                    btn_text = self.search_buttons[comp].cget('text')
                    if btn_text and btn_text != "Выберите компонент...":
                        comp_name = btn_text

                comp_row = var_row + comp
                comp_label = ttk.Label(self.variants_frame, text=comp_name, anchor='w', width=30)
                comp_label.grid(row=comp_row, column=1, padx=3, pady=2, sticky='w')

                conc_entry = ttk.Entry(self.variants_frame, width=10)
                conc_entry.grid(row=comp_row, column=2, padx=3, pady=2)
                conc_entry.insert(0, f"{100/nb:.1f}")
                self.conc_entries[-1].append(conc_entry)

    
    def _update_components_grid(self):
        """Обновляет сетку компонентов, сохраняя введенные данные"""
        # Определяем, есть ли внешний окислитель
        al_value = self.al_entry.get().strip() if hasattr(self, 'al_entry') else "0"
        has_outer_oxy = al_value != "0"
        
        # Получаем текущее количество вариаций и компонентов
        old_var_cnt = len(self.conc_entries)
        old_nb = len(self.id_entries)
        new_nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
        new_var_cnt = int(self.var_entry.get()) if self.var_entry.get() else 1

        # Сохраняем текущие значения основных компонентов
        saved_components = []
        for i in range(len(self.id_entries)):
            comp_data = {
                'id': self.id_entries[i].cget('text'),
                'formula': self.formula_entries[i].cget('text'),
                'enthalpy': self.enthalpy_entries[i].cget('text'),
                'button_text': self.search_buttons[i].cget('text'),
            }
            saved_components.append(comp_data)

        # Сохраняем данные внешнего окислителя (если был)
        oxy_data = None
        if len(self.oxy_id_entries) > 0:
            oxy_data = {
                'id': self.oxy_id_entries[0].cget('text'),
                'formula': self.oxy_formula_entries[0].cget('text'),
                'enthalpy': self.oxy_enthalpy_entries[0].cget('text'),
                'button_text': self.oxy_search_buttons[0].cget('text'),
            }

        # Сохраняем текущие концентрации (с учетом изменения количества вариаций)
        saved_concentrations = []
        for var_idx, var_entries in enumerate(self.conc_entries):
            var_conc = [entry.get() for entry in var_entries]
            saved_concentrations.append(var_conc)

        # Пересоздаем сетку (теперь она будет нужной длины: new_nb + окислитель)
        self._create_components_grid()

        # Восстанавливаем основные компоненты
        for i, comp_data in enumerate(saved_components):
            if i < len(self.id_entries):
                self.id_entries[i].config(text=comp_data['id'])
                self.formula_entries[i].config(text=comp_data['formula'])
                self.enthalpy_entries[i].config(text=comp_data['enthalpy'])
                self.search_buttons[i].config(text=comp_data['button_text'])

        # Восстанавливаем внешний окислитель
        if has_outer_oxy and oxy_data and len(self.oxy_id_entries) > 0:
            self.oxy_id_entries[0].config(text=oxy_data['id'])
            self.oxy_formula_entries[0].config(text=oxy_data['formula'])
            self.oxy_enthalpy_entries[0].config(text=oxy_data['enthalpy'])
            self.oxy_search_buttons[0].config(text=oxy_data['button_text'])

        # Восстанавливаем концентрации (с учетом изменения количества вариаций и компонентов)
        for var_idx, var_conc in enumerate(saved_concentrations):
            if var_idx < len(self.conc_entries):
                for comp_idx, value in enumerate(var_conc):
                    if comp_idx < len(self.conc_entries[var_idx]) and value:
                        self.conc_entries[var_idx][comp_idx].delete(0, 'end')
                        self.conc_entries[var_idx][comp_idx].insert(0, value)

        # Пересчитываем концентрации на равные доли (100/NB) только если NB изменилось
        if self.nb_changed:
            self._recalculate_concentrations()
            self.nb_changed = False  # Сбрасываем флаг после пересчета

        # Обновляем названия компонентов в вариациях
        self._update_variants_labels()
    
    def _update_variants_labels(self):
        """Обновляет названия компонентов в сетке вариаций"""
        nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
        var_cnt = int(self.var_entry.get()) if self.var_entry.get() else 1

        # Обновляем названия компонентов для каждой вариации
        for var_num in range(var_cnt):
            var_row = var_num * (nb + 1) + 1
            for comp in range(nb):
                # Получаем название компонента из кнопки
                comp_name = "Комп. " + str(comp+1)
                if comp < len(self.search_buttons):
                    btn_text = self.search_buttons[comp].cget('text')
                    if btn_text and btn_text != "Выберите компонент...":
                        comp_name = btn_text

                # Находим и обновляем label в сетке
                row = var_row + comp
                for widget in self.variants_frame.grid_slaves(row=row, column=1):
                    if isinstance(widget, ttk.Label):
                        widget.config(text=comp_name, anchor='w', width=30)

    def _recalculate_concentrations(self):
        """Пересчитывает концентрации при изменении количества компонентов"""
        try:
            nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
            if nb <= 0:
                return
            
            # Новая концентрация для каждого компонента
            new_conc = 100.0 / nb
            
            # Обновляем все поля концентраций
            for var_entries in self.conc_entries:
                for i, entry in enumerate(var_entries):
                    if i < nb:
                        entry.delete(0, 'end')
                        entry.insert(0, f"{new_conc:.1f}")
        except (ValueError, TypeError):
            pass

    def _on_nb_changed(self):
        """Отслеживает изменение количества компонентов"""
        self.nb_changed = True
    
    def _load_params(self, params: Dict):
        """Загружает параметры в виджеты"""
        # Сбрасываем флаг при загрузке
        self.nb_changed = False
        
        self.author_entry.insert(0, params.get('author', ''))
        self.code_entry.insert(0, params.get('code', '*'))

        # Директивы
        for code, var in self.directive_vars.items():
            var.set(params.get('directives', {}).get(code, False))


        # Параметры процесса
        self.pk_entry.insert(0, str(params.get('PK', 0.1)))
        self.pc_entry.insert(0, str(params.get('PC', 0.1)))

        # Рецептура
        self.nb_entry.insert(0, str(params.get('NB', 2)))
        self.var_entry.insert(0, str(params.get("N", 1)))
        self._create_components_grid()

        # Компоненты
        components = params.get('components', [])
        variants = params.get('variants', [])
        outer_oxy = params.get('outer_oxy', [])

        # Сначала загружаем основные компоненты
        for i, comp in enumerate(components):
            if i < len(self.formula_entries):
                self.id_entries[i].config(text=str(comp.get('id', 0)))
                self.formula_entries[i].config(text=comp.get('formula', ''))
                # Обновляем текст кнопки с названием компонента
                if comp.get('name'):
                    self.search_buttons[i].config(text=comp['name'])
                else:
                    self.search_buttons[i].config(text="Выберите компонент...")
                if comp.get('enthalpy') is not None:
                    self.enthalpy_entries[i].config(text=f"{comp['enthalpy']:.2f}")
                else:
                    self.enthalpy_entries[i].config(text="")

        # Затем загружаем внешний окислитель (если есть)
        if outer_oxy and len(outer_oxy) > 0 and len(self.oxy_id_entries) > 0:
            oxy = outer_oxy[0]
            self.oxy_id_entries[0].config(text=str(oxy.get('id', 0)))
            self.oxy_formula_entries[0].config(text=oxy.get('formula', ''))
            # Обновляем текст кнопки с названием компонента
            if oxy.get('name'):
                self.oxy_search_buttons[0].config(text=oxy['name'])
            else:
                self.oxy_search_buttons[0].config(text="Выберите компонент...")
            if oxy.get('enthalpy') is not None:
                self.oxy_enthalpy_entries[0].config(text=f"{oxy['enthalpy']:.2f}")
            else:
                self.oxy_enthalpy_entries[0].config(text="")
        
        # Обновляем названия компонентов в вариациях
        self._update_variants_labels()
    
    def _open_component_search(self, comp_index: int, is_oxy=False):
        """Открывает диалог поиска компонента"""
        dialog = ComponentSearchDialog(self.dialog, self.catalog)
        component = dialog.get_component()

        if component:
            if is_oxy:
                self.oxy_id_entries[comp_index].config(text=str(component.id))
                self.oxy_formula_entries[comp_index].config(text=component.formula)
                self.oxy_search_buttons[comp_index].config(text=component.name)
                if component.enthalpy is not None:
                    self.oxy_enthalpy_entries[comp_index].config(text=f"{component.enthalpy:.2f}")
                else:
                    self.oxy_enthalpy_entries[comp_index].config(text="")
            else:
                self.id_entries[comp_index].config(text=str(component.id))
                self.formula_entries[comp_index].config(text=component.formula)
                self.search_buttons[comp_index].config(text=component.name)
                if component.enthalpy is not None:
                    self.enthalpy_entries[comp_index].config(text=f"{component.enthalpy:.2f}")
                else:
                    self.enthalpy_entries[comp_index].config(text="")
            
            # Обновляем названия компонентов в вариациях
            self._update_variants_labels()
    
    def _on_ok(self):
        """Собирает данные и закрывает окно"""
        try:
            # Директивы
            directives = {}
            for code, var in self.directive_vars.items():
                if var.get():
                    directives[code] = var.get()
                
            
            # Параметры процесса
            params = {
                'author': self.author_entry.get().strip(),
                'code': self.code_entry.get().strip(),
                'directives': directives,
                'PK': float(self.pk_entry.get()),
                'PC': float(self.pc_entry.get()),
                'AL': float(self.al_entry.get())
            }
            
            if params['AL'] and params['AL']!=0:
                params['AL_N']=1
                params['AL_NB']=1
                params['AL_variants'] = [{'id': 1, 'concentrations': [100.]}]
                # Внешний окислитель - читаем из отдельного списка
                if len(self.oxy_id_entries) > 0:
                    comp_id = int(self.oxy_id_entries[0].cget('text').strip() or 0)
                    formula = self.oxy_formula_entries[0].cget('text').strip()
                    enthalpy_str = self.oxy_enthalpy_entries[0].cget('text').strip()
                    enthalpy = float(enthalpy_str) if enthalpy_str else None
                    # Получаем название компонента из текста кнопки
                    button_text = self.oxy_search_buttons[0].cget('text')
                    name = button_text if button_text != "Выберите компонент..." else ''
                    params["outer_oxy"]=[{
                        'id': comp_id,
                        'name': name,
                        'formula': formula,
                        'enthalpy': enthalpy
                    }]
            
            # Рецептура
            nb = int(self.nb_entry.get())
            n=int(self.var_entry.get())
            al_nb = 1 if (params['AL'] and params['AL']!=0) else 0

            params['NB'] = nb
            params['N'] = n
            params['AL_NB'] = al_nb

            # Концентрации
            variants=[]
            for idx in range(len(self.conc_entries)):
                concentrations=[]
                for entry in self.conc_entries[idx]:
                    val = entry.get().strip()
                    concentrations.append(float(val) if val else 0.0)
                variants.append({"id":idx+1,'concentrations':concentrations })
            params['variants'] = variants

            # Компоненты - основные компоненты (индексы 0..nb-1)
            components = []
            for i in range(nb):
                comp_id = int(self.id_entries[i].cget('text').strip() or 0)
                formula = self.formula_entries[i].cget('text').strip()
                enthalpy_str = self.enthalpy_entries[i].cget('text').strip()
                enthalpy = float(enthalpy_str) if enthalpy_str else None
                # Получаем название компонента из текста кнопки
                button_text = self.search_buttons[i].cget('text')
                name = button_text if button_text != "Выберите компонент..." else ''

                components.append({
                    'id': comp_id,
                    'name': name,
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
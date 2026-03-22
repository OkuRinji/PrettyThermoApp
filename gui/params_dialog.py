# gui/params_dialog.py
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

from core.catalog_manager import CatalogManager
from gui.component_search import ComponentSearchDialog
from models.params import Params


class ParamsDialog:
    """
    Диалоговое окно для ввода параметров расчета TERMO94
    """

    def __init__(
        self,
        parent,
        catalog: CatalogManager = None,
        initial_params: Optional[Dict] = None,
    ):
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
        params = Params()
        return params.to_dict()

    def _create_widgets(self):
        """Создает все виджеты окна"""

        # Главный контейнер с прокруткой
        self.main_canvas = tk.Canvas(self.dialog)
        scrollbar = ttk.Scrollbar(
            self.dialog, orient="vertical", command=self.main_canvas.yview
        )
        scrollable_frame = ttk.Frame(self.main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(
                scrollregion=self.main_canvas.bbox("all")
            ),
        )

        self.main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=scrollbar.set)

        self.main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Прокрутка колесиком
        def _on_mousewheel(event):
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Отписка обработчика прокрутки при закрытии окна
        def _on_closing():
            self.main_canvas.unbind_all("<MouseWheel>")
            self.dialog.destroy()

        self.dialog.protocol("WM_DELETE_WINDOW", _on_closing)

        # === Секция 1: Директивы ===
        self.directives_expanded = tk.BooleanVar(value=False)  # По умолчанию свернуто

        dir_header_frame = ttk.Frame(scrollable_frame)
        dir_header_frame.pack(fill="x", padx=10, pady=(10, 0))

        ttk.Label(
            dir_header_frame,
            text="⚙️ Директивы",
            font=("TkDefaultFont", 10, "bold")
        ).pack(side="left")

        self.toggle_btn = ttk.Button(
            dir_header_frame,
            text="▶ Развернуть",
            command=self._toggle_directives,
            width=12
        )
        self.toggle_btn.pack(side="left", padx=10)

        # Контейнер для директив (сворачиваемый)
        self.directives_frame = ttk.Frame(scrollable_frame)
        # Не pack'им сразу - покажем при разворачивании
        self._directives_packed = False  # Флаг для отслеживания pack

        self.directive_vars = {}
        directives_list = [
            ("LDY", "Плотность"),
            ("LNN", "Концентрации в молях на 1 кг"),
            ("TABL", "Оформление в виде таблицы"),
            ("LVM", "Концентрации: газ-объем%, конд-масса%"),
            ("WPS", "Генерация PS-файла"),
            ("LMM", "Концентрации в массовых долях"),
        ]

        # Создаем виджеты директив внутри сворачиваемого контейнера
        for i, (code, desc) in enumerate(directives_list):
            var = tk.BooleanVar(value=False)
            self.directive_vars[code] = var
            cb = ttk.Checkbutton(self.directives_frame, text=f"{code} - {desc}", variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky="w", pady=1)

        # === Секция 2: Параметры процесса ===
        proc_frame = ttk.LabelFrame(
            scrollable_frame, text="🔧 Параметры процесса", padding=10
        )
        proc_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(proc_frame, text="PK - Давление в камере (МПа):").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.pk_entry = ttk.Entry(proc_frame, width=15)
        self.pk_entry.grid(row=0, column=1, padx=5, pady=2)
        self.pk_entry.bind("<FocusIn>", self._on_focus_in)

        ttk.Label(proc_frame, text="PC - Давление на срезе (МПа):").grid(
            row=0, column=2, sticky="w", pady=2
        )
        self.pc_entry = ttk.Entry(proc_frame, width=15)
        self.pc_entry.grid(row=0, column=3, padx=5, pady=2)
        self.pc_entry.bind("<FocusIn>", self._on_focus_in)

        ttk.Label(proc_frame, text="AL - Участие внешнего окислителя").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.al_entry = ttk.Entry(proc_frame, width=15)
        self.al_entry.grid(row=1, column=1, padx=5, pady=2)
        self.al_entry.insert(0, "0")
        self.al_entry.bind("<FocusIn>", self._on_focus_in)
        self.al_entry.bind("<KeyRelease>", lambda e: self._on_al_changed())

        # === Секция 4: Рецептура ===
        recipe_frame = ttk.LabelFrame(
            scrollable_frame, text="🧪 Рецептура состава", padding=10
        )
        recipe_frame.pack(fill="x", padx=10, pady=5)

        # Количество компонентов
        count_frame = ttk.Frame(recipe_frame)
        count_frame.pack(fill="x", pady=5)

        ttk.Label(count_frame, text="Компонентов (NB):").pack(side="left", padx=5)
        self.nb_entry = ttk.Entry(count_frame, width=5)
        self.nb_entry.pack(side="left", padx=5)
        self.nb_entry.bind("<KeyRelease>", lambda e: self._on_nb_changed())
        self.nb_entry.bind("<FocusIn>", self._on_focus_in)

        ttk.Label(count_frame, text="Количество вариаций (Vars):").pack(
            side="left", padx=5
        )
        self.var_entry = ttk.Entry(count_frame, width=5)
        self.var_entry.pack(side="left", padx=5)
        self.var_entry.bind("<KeyRelease>", lambda e: self._on_var_changed())
        self.var_entry.bind("<FocusIn>", self._on_focus_in)

        ttk.Button(
            count_frame, text="Построить серию", command=self._make_series_dialog
        ).pack(side="left", padx=20)

        # Сетка компонентов (верхняя часть)
        self.components_frame = ttk.Frame(recipe_frame)
        self.components_frame.pack(fill="x", pady=5)

        # Сетка вариаций (нижняя часть с прокруткой и рамкой)
        variants_label_frame = ttk.LabelFrame(recipe_frame, text="📊 Вариации концентраций", padding=5)
        variants_label_frame.pack(fill="both", expand=True, pady=5)

        # Создаём Canvas с прокруткой для вариаций внутри LabelFrame
        self.variants_canvas = tk.Canvas(variants_label_frame, highlightthickness=0)
        self.variants_scrollbar = ttk.Scrollbar(
            variants_label_frame, orient="vertical", command=self.variants_canvas.yview
        )
        self.variants_frame = ttk.Frame(self.variants_canvas)

        self.variants_frame.bind(
            "<Configure>",
            lambda e: self.variants_canvas.configure(
                scrollregion=self.variants_canvas.bbox("all")
            ),
        )

        self.variants_canvas_window = self.variants_canvas.create_window(
            (0, 0), window=self.variants_frame, anchor="nw"
        )
        self.variants_canvas.configure(yscrollcommand=self.variants_scrollbar.set)

        self.variants_canvas.pack(side="left", fill="both", expand=True)
        self.variants_scrollbar.pack(side="right", fill="y")

        # Прокрутка колесиком для вариаций
        def _on_variants_mousewheel(event):
            self.variants_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.variants_canvas.bind_all("<MouseWheel>", _on_variants_mousewheel)

        # Отписка при закрытии
        def _on_closing_dialog():
            self.variants_canvas.unbind_all("<MouseWheel>")
            self.dialog.destroy()

        self.dialog.protocol("WM_DELETE_WINDOW", _on_closing_dialog)

        self._create_components_grid()

        # === Секция 5: Кнопки ===
        btn_frame = ttk.Frame(scrollable_frame, padding=10)
        btn_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(btn_frame, text="✅ ОК", command=self._on_ok, width=15).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="❌ Отмена", command=_on_closing, width=15).pack(
            side="left", padx=5
        )
        ttk.Button(
            btn_frame, text="💾 Сохранить шаблон", command=self._save_template, width=18
        ).pack(side="left", padx=5)

    def create_signle_comp_line(self, comp_idx, nb, start, is_oxy=False):
        """Создает одну строку компонента или окислителя"""
        # Кнопка поиска
        search_btn = ttk.Button(
            self.components_frame,
            text="Выберите компонент...",
            width=35,
            command=lambda idx=comp_idx: self._open_component_search(
                idx, is_oxy=is_oxy
            ),
        )
        search_btn.grid(row=comp_idx + start, column=0, padx=3, pady=2)

        # ID - используем Label вместо Entry с визуальным оформлением
        id_label = ttk.Label(
            self.components_frame,
            text="",
            anchor="w",
            width=8,
            relief="sunken",
            padding=2,
        )
        id_label.grid(row=comp_idx + start, column=2, padx=3, pady=2, sticky="ew")

        # Формула - Label
        form_label = ttk.Label(
            self.components_frame,
            text="",
            anchor="w",
            width=25,
            relief="sunken",
            padding=2,
        )
        form_label.grid(row=comp_idx + start, column=3, padx=3, pady=2, sticky="ew")

        # Энтальпия - Label
        ent_label = ttk.Label(
            self.components_frame,
            text="",
            anchor="w",
            width=12,
            relief="sunken",
            padding=2,
        )
        ent_label.grid(row=comp_idx + start, column=4, padx=3, pady=2, sticky="ew")

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
            var_cnt = int(self.var_entry.get()) if self.var_entry.get() else 1
        except ValueError:
            var_cnt = 1

        # Заголовки компонентов
        ttk.Label(
            self.components_frame, text="Компонент", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(
            self.components_frame, text="ID", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=2, padx=5, pady=2)
        ttk.Label(
            self.components_frame, text="Формула", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=3, padx=5, pady=2)
        ttk.Label(
            self.components_frame, text="Энтальпия", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=4, padx=5, pady=2)

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
        ttk.Label(
            self.components_frame,
            text="Компоненты смеси",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=1, column=0, padx=5, pady=2)
        start = 2
        for comp_idx in range(nb):
            self.create_signle_comp_line(comp_idx, nb, start, is_oxy=False)

        # Затем внешний окислитель (если есть)
        if self.al_entry.get() != "0":
            ttk.Label(
                self.components_frame,
                text="Внешний окислитель",
                font=("TkDefaultFont", 9, "bold"),
            ).grid(row=start + nb, column=0, padx=5, pady=2)
            self.create_signle_comp_line(0, 1, start + nb + 1, is_oxy=True)

        # Сетка вариаций
        ttk.Label(
            self.variants_frame, text="№", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=0, padx=5, pady=2)
        ttk.Label(
            self.variants_frame, text="Компонент", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(
            self.variants_frame, text="Конц. (%)", font=("TkDefaultFont", 9, "bold")
        ).grid(row=0, column=2, padx=5, pady=2)

        for var_num in range(var_cnt):
            self.conc_entries.append([])
            # Разделитель между вариациями (перед вариацией, кроме первой)
            if var_num > 0:
                ttk.Separator(self.variants_frame, orient="horizontal").grid(
                    row=var_num * (nb + 1),
                    column=0,
                    columnspan=3,
                    sticky="ew",
                    pady=(15, 5),
                )

            # Номер вариации с рамкой
            var_row = var_num * (nb + 1) + 1
            var_label = ttk.Label(
                self.variants_frame,
                text=str(var_num + 1),
                font=("TkDefaultFont", 9, "bold"),
                relief="ridge",
                padding=5,
                borderwidth=2,
            )
            var_label.grid(
                row=var_row, column=0, rowspan=nb, padx=3, pady=3, sticky="ns"
            )

            for comp in range(nb):
                # Получаем название компонента из кнопки
                comp_name = "Комп. " + str(comp + 1)
                if comp < len(self.search_buttons):
                    btn_text = self.search_buttons[comp].cget("text")
                    if btn_text and btn_text != "Выберите компонент...":
                        comp_name = btn_text

                comp_row = var_row + comp
                comp_label = ttk.Label(
                    self.variants_frame, text=comp_name, anchor="w", width=30
                )
                comp_label.grid(row=comp_row, column=1, padx=3, pady=2, sticky="w")

                conc_entry = ttk.Entry(self.variants_frame, width=10)
                conc_entry.grid(row=comp_row, column=2, padx=3, pady=2)
                conc_entry.bind("<FocusIn>", self._on_focus_in)
                self.conc_entries[-1].append(conc_entry)

        # Обновляем область прокрутки главного canvas после создания всех элементов
        self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")
        )

    def _make_series_dialog(self):
        """Создаёт диалоговое окно для построения серии расчётов"""
        self.series_dialog = tk.Toplevel(self.dialog)
        self.series_dialog.title("Построение серии расчётов")
        self.series_dialog.geometry("600x500")
        self.series_dialog.transient(self.dialog)
        self.series_dialog.grab_set()

        self.start_conc_entries = {}  # Словарь: индекс компонента -> Entry
        self.series_frame = ttk.LabelFrame(self.series_dialog, padding=10)
        self.series_frame.pack(fill="both", expand=True)

        ttk.Label(
            self.series_frame,
            text="Введите данные для построения серии",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, columnspan=4, padx=3, pady=5)

        # Получаем названия компонентов из основного окна
        comp_names = []
        for btn in self.search_buttons:
            btn_text = btn.cget("text")
            if btn_text and btn_text != "Выберите компонент...":
                comp_names.append(btn_text)
            else:
                comp_names.append(f"Комп. {len(comp_names) + 1}")

        n = int(self.nb_entry.get())
        comp_options = [f"{i + 1}. {comp_names[i]}" for i in range(n)]

        # Выбор двух компонентов для изменения через Combobox
        ttk.Label(self.series_frame, text="Первый изменяемый компонент:").grid(
            row=1, column=0, padx=3, pady=3, sticky="e"
        )
        self.fst_comp_combo = ttk.Combobox(
            self.series_frame, values=comp_options, width=30, state="readonly"
        )
        self.fst_comp_combo.grid(
            row=1, column=1, columnspan=2, padx=3, pady=3, sticky="w"
        )
        self.fst_comp_combo.current(0)

        ttk.Label(self.series_frame, text="Второй изменяемый компонент:").grid(
            row=2, column=0, padx=3, pady=3, sticky="e"
        )
        self.scnd_comp_combo = ttk.Combobox(
            self.series_frame, values=comp_options, width=30, state="readonly"
        )
        self.scnd_comp_combo.grid(
            row=2, column=1, columnspan=2, padx=3, pady=3, sticky="w"
        )
        self.scnd_comp_combo.current(1 if n > 1 else 0)

        # Кнопка подтверждения выбора компонентов
        self.confirm_btn = ttk.Button(
            self.series_frame,
            text="Подтвердить выбор компонентов",
            command=self._on_confirm_components,
        )
        self.confirm_btn.grid(row=3, column=0, columnspan=4, padx=3, pady=10)

        # Флаг подтверждения выбора
        self.components_confirmed = False

        # Контейнер для полей концентраций (изначально скрыт)
        self.conc_container = ttk.Frame(self.series_frame)

        # Шаг изменения концентрации
        ttk.Label(self.conc_container, text="Шаг изменения концентрации (%):").grid(
            row=0, column=0, padx=3, pady=3, sticky="e"
        )
        self.step_entry = ttk.Entry(self.conc_container, width=10)
        self.step_entry.grid(row=0, column=1, padx=3, pady=3, sticky="w")
        self.step_entry.insert(0, "5")

        # Начальная и конечная концентрация первого компонента
        ttk.Label(self.conc_container, text="Начальная концентрация (%):").grid(
            row=1, column=0, padx=3, pady=3, sticky="e"
        )
        self.start_conc_1_entry = ttk.Entry(self.conc_container, width=10)
        self.start_conc_1_entry.grid(row=1, column=1, padx=3, pady=3, sticky="w")
        self.start_conc_1_entry.insert(0, "0")

        ttk.Label(self.conc_container, text="Конечная концентрация (%):").grid(
            row=2, column=0, padx=3, pady=3, sticky="e"
        )
        self.end_conc_1_entry = ttk.Entry(self.conc_container, width=10)
        self.end_conc_1_entry.grid(row=2, column=1, padx=3, pady=3, sticky="w")
        self.end_conc_1_entry.insert(0, "100")

        # Начальные концентрации для остальных компонентов
        ttk.Separator(self.conc_container, orient="horizontal").grid(
            row=3, column=0, columnspan=4, sticky="ew", pady=10
        )
        ttk.Label(
            self.conc_container,
            text="Начальные концентрации компонентов (%)",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=4, column=0, columnspan=4, padx=3, pady=5)

        # Кнопки будут созданы после подтверждения выбора в _create_conc_entries

    def _on_confirm_components(self):
        """Обработчик кнопки подтверждения выбора компонентов"""
        comp_1 = self.fst_comp_combo.current()
        comp_2 = self.scnd_comp_combo.current()

        # Проверка: компоненты не должны совпадать
        if comp_1 == comp_2:
            messagebox.showerror("Ошибка", "Выбраны одинаковые компоненты")
            return

        # Получаем названия компонентов
        comp_names = []
        for btn in self.search_buttons:
            btn_text = btn.cget("text")
            if btn_text and btn_text != "Выберите компонент...":
                comp_names.append(btn_text)
            else:
                comp_names.append(f"Комп. {len(comp_names) + 1}")

        n = int(self.nb_entry.get())

        # Блокируем выбор компонентов
        self.fst_comp_combo.config(state="disabled")
        self.scnd_comp_combo.config(state="disabled")
        self.confirm_btn.config(text="Выбор подтверждён", state="disabled")

        # Создаём поля для ввода концентраций
        self._create_conc_entries(n, comp_names, comp_1, comp_2)

        self.components_confirmed = True

    def _create_conc_entries(self, n, comp_names, comp_1, comp_2):
        """Создаёт поля для ввода начальных концентраций"""
        # Очищаем старые виджеты
        for widget in self.conc_container.grid_slaves():
            if int(widget.grid_info()["row"]) >= 3:
                widget.destroy()

        self.start_conc_entries.clear()

        # Создаём поля только для неизменяемых компонентов
        row = 5

        for i in range(n):
            if i == comp_1 or i == comp_2:
                continue  # Пропускаем изменяемые компоненты

            ttk.Label(self.conc_container, text=f"{i + 1}. {comp_names[i]}:").grid(
                row=row, column=0, padx=3, pady=3, sticky="e"
            )
            start_conc_entry = ttk.Entry(self.conc_container, width=10)
            start_conc_entry.grid(row=row, column=1, padx=3, pady=3, sticky="w")
            self.start_conc_entries[i] = start_conc_entry
            row += 1

        # Добавляем информационные метки для изменяемых компонентов
        info_row = row
        ttk.Separator(self.conc_container, orient="horizontal").grid(
            row=info_row, column=0, columnspan=4, sticky="ew", pady=10
        )

        ttk.Label(
            self.conc_container,
            text=f"✦ {comp_names[comp_1]} — изменяется от 0% до 100%",
            foreground="blue",
        ).grid(row=info_row + 1, column=0, columnspan=4, padx=3, pady=3, sticky="w")
        ttk.Label(
            self.conc_container,
            text=f"✦ {comp_names[comp_2]} — изменяется компенсаторно (сумма с 1-м = const)",
            foreground="blue",
        ).grid(row=info_row + 2, column=0, columnspan=4, padx=3, pady=3, sticky="w")

        # Сумма концентраций остальных компонентов
        other_sum_label = ttk.Label(
            self.conc_container,
            text="Сумма остальных концентраций:",
            font=("TkDefaultFont", 9, "bold"),
        )
        other_sum_label.grid(row=info_row + 3, column=0, padx=3, pady=5, sticky="e")
        self.other_sum_value = ttk.Label(
            self.conc_container,
            text="0.0%",
            font=("TkDefaultFont", 9, "bold"),
            foreground="green",
        )
        self.other_sum_value.grid(
            row=info_row + 3, column=1, padx=3, pady=5, sticky="w"
        )

        # Доступный диапазон для изменяемых компонентов
        avail_label = ttk.Label(
            self.conc_container,
            text="Доступно для изменяемых:",
            font=("TkDefaultFont", 9, "bold"),
        )
        avail_label.grid(row=info_row + 4, column=0, padx=3, pady=5, sticky="e")
        self.avail_value = ttk.Label(
            self.conc_container,
            text="100.0%",
            font=("TkDefaultFont", 9, "bold"),
            foreground="green",
        )
        self.avail_value.grid(row=info_row + 4, column=1, padx=3, pady=5, sticky="w")

        # Привязываем обновление суммы к полям ввода
        for entry in self.start_conc_entries.values():
            entry.bind("<KeyRelease>", self._update_other_sum)
            entry.bind("<FocusOut>", self._update_other_sum)

        # Создаём кнопки (после всех полей)
        btn_row = info_row + 5
        btn_frame = ttk.Frame(self.conc_container)
        btn_frame.grid(row=btn_row, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="Построить серию", command=self._build_series).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Отмена", command=self.series_dialog.destroy).pack(
            side="left", padx=5
        )

        # Показываем контейнер
        self.conc_container.grid(
            row=4, column=0, columnspan=4, padx=3, pady=5, sticky="ns"
        )

        # Инициализируем сумму
        self._update_other_sum()

    def _update_other_sum(self, event=None):
        """Обновляет отображение суммы концентраций остальных компонентов"""
        try:
            other_sum = sum(
                float(entry.get()) for entry in self.start_conc_entries.values()
            )
            self.other_sum_value.config(text=f"{other_sum:.1f}%")

            # Доступно для изменяемых компонентов
            start_1 = (
                float(self.start_conc_1_entry.get())
                if hasattr(self, "start_conc_1_entry")
                else 0
            )
            available = 100.0 - other_sum
            self.avail_value.config(text=f"{available:.1f}%")

            # Подсветка если сумма слишком большая
            if other_sum >= 100:
                self.other_sum_value.config(foreground="red")
                self.avail_value.config(foreground="red")
            elif start_1 > available:
                self.other_sum_value.config(foreground="green")
                self.avail_value.config(foreground="red")
            else:
                self.other_sum_value.config(foreground="green")
                self.avail_value.config(foreground="green")
        except ValueError, TypeError:
            pass

    def _build_series(self):
        """Построение серии расчётов с изменением концентраций двух компонентов.

        Концентрация 1-го компонента изменяется от start до end с заданным шагом.
        Концентрация 2-го компонента изменяется компенсаторно (сумма 1+2 = const).
        """
        try:
            # Проверка: подтверждён ли выбор компонентов
            if not self.components_confirmed:
                messagebox.showwarning(
                    "Предупреждение", "Сначала подтвердите выбор компонентов"
                )
                return

            # Получаем номера компонентов (индексация с 0)
            comp_1 = self.fst_comp_combo.current()
            comp_2 = self.scnd_comp_combo.current()

            # Параметры изменения концентраций
            step = float(self.step_entry.get())
            if step <= 0:
                messagebox.showerror("Ошибка", "Шаг должен быть положительным числом")
                return

            start_1 = float(self.start_conc_1_entry.get())
            end_1 = float(self.end_conc_1_entry.get())

            # Проверка диапазона концентраций
            if start_1 < 0 or end_1 < 0 or start_1 > 100 or end_1 > 100:
                messagebox.showerror("Ошибка", "Концентрация должна быть от 0 до 100%")
                return

            # Собираем концентрации остальных (неизменяемых) компонентов
            other_conc = {}
            other_sum = 0.0
            for i, entry in self.start_conc_entries.items():
                conc = float(entry.get())
                other_conc[i] = conc
                other_sum += conc

            # Проверка: сумма остальных концентраций
            if other_sum >= 100:
                messagebox.showerror(
                    "Ошибка",
                    f"Сумма концентраций остальных компонентов ({other_sum:.1f}%) "
                    f"должна быть меньше 100%",
                )
                return

            # Начальная концентрация 2-го компонента
            start_2 = 100.0 - start_1 - other_sum

            if start_2 < 0:
                messagebox.showerror(
                    "Ошибка",
                    f"Отрицательная начальная концентрация 2-го компонента ({start_2:.1f}%)\n"
                    f"Уменьшите сумму остальных концентраций или начальную концентрацию 1-го",
                )
                return

            # Конечная концентрация 2-го компонента
            end_2 = 100.0 - end_1 - other_sum
            if end_2 < 0:
                messagebox.showerror(
                    "Ошибка",
                    f"Отрицательная конечная концентрация 2-го компонента ({end_2:.1f}%)\n"
                    f"Уменьшите конечную концентрацию 1-го компонента",
                )
                return

            # Сумма концентраций двух изменяемых компонентов (константа)
            sum_1_2 = start_1 + start_2

            # Определяем направление изменения
            direction = 1 if start_1 <= end_1 else -1

            # Рассчитываем количество вариаций
            steps = int(abs(end_1 - start_1) / step) + 1

            # Устанавливаем количество вариаций
            self.var_entry.delete(0, "end")
            self.var_entry.insert(0, str(steps))

            # Обновляем сетку компонентов
            self._update_components_grid()

            # Заполняем концентрации для каждой вариации
            for var_idx, entry_list in enumerate(self.conc_entries):
                if not entry_list:
                    continue

                curr_1 = start_1 + var_idx * step * direction
                curr_2 = sum_1_2 - curr_1  # Компенсаторное изменение

                for comp_idx, entry in enumerate(entry_list):
                    entry.delete(0, "end")
                    if comp_idx == comp_1:
                        entry.insert(0, f"{curr_1:.2f}")
                    elif comp_idx == comp_2:
                        entry.insert(0, f"{curr_2:.2f}")
                    else:
                        # Остальные компоненты остаются неизменными
                        entry.insert(0, f"{other_conc.get(comp_idx, 0):.2f}")

            self.series_dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Ошибка", f"Некорректный ввод данных: {e}")

    ######### Нужно реализовать непосредвенно построение серии в GUI #####################

    def _update_components_grid(self):
        """Обновляет сетку компонентов и вариаций, сохраняя введенные данные"""
        # Определяем, есть ли внешний окислитель
        al_value = self.al_entry.get().strip() if hasattr(self, "al_entry") else "0"
        has_outer_oxy = al_value != "0"
        
        # Сохраняем текущие значения основных компонентов
        saved_components = []
        for i in range(len(self.id_entries)):
            comp_data = {
                "id": self.id_entries[i].cget("text"),
                "formula": self.formula_entries[i].cget("text"),
                "enthalpy": self.enthalpy_entries[i].cget("text"),
                "button_text": self.search_buttons[i].cget("text"),
            }
            saved_components.append(comp_data)

        # Сохраняем данные внешнего окислителя (если был)
        oxy_data = None
        if len(self.oxy_id_entries) > 0:
            oxy_data = {
                "id": self.oxy_id_entries[0].cget("text"),
                "formula": self.oxy_formula_entries[0].cget("text"),
                "enthalpy": self.oxy_enthalpy_entries[0].cget("text"),
                "button_text": self.oxy_search_buttons[0].cget("text"),
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
                self.id_entries[i].config(text=comp_data["id"])
                self.formula_entries[i].config(text=comp_data["formula"])
                self.enthalpy_entries[i].config(text=comp_data["enthalpy"])
                self.search_buttons[i].config(text=comp_data["button_text"])

        # Восстанавливаем внешний окислитель
        if has_outer_oxy and oxy_data and len(self.oxy_id_entries) > 0:
            self.oxy_id_entries[0].config(text=oxy_data["id"])
            self.oxy_formula_entries[0].config(text=oxy_data["formula"])
            self.oxy_enthalpy_entries[0].config(text=oxy_data["enthalpy"])
            self.oxy_search_buttons[0].config(text=oxy_data["button_text"])

        # Восстанавливаем концентрации (с учетом изменения количества вариаций и компонентов)
        for var_idx, var_conc in enumerate(saved_concentrations):
            if var_idx < len(self.conc_entries):
                for comp_idx, value in enumerate(var_conc):
                    if comp_idx < len(self.conc_entries[var_idx]) and value:
                        self.conc_entries[var_idx][comp_idx].delete(0, "end")
                        self.conc_entries[var_idx][comp_idx].insert(0, value)

        # Обновляем названия компонентов в вариациях
        self._update_variants_labels()

        # Обновляем область прокрутки главного canvas
        self.main_canvas.configure(
            scrollregion=self.main_canvas.bbox("all")
        )

    def _update_variants_labels(self):
        """Обновляет названия компонентов в сетке вариаций"""
        nb = int(self.nb_entry.get()) if self.nb_entry.get() else 2
        var_cnt = int(self.var_entry.get()) if self.var_entry.get() else 1

        # Обновляем названия компонентов для каждой вариации
        for var_num in range(var_cnt):
            var_row = var_num * (nb + 1) + 1
            for comp in range(nb):
                # Получаем название компонента из кнопки
                comp_name = "Комп. " + str(comp + 1)
                if comp < len(self.search_buttons):
                    btn_text = self.search_buttons[comp].cget("text")
                    if btn_text and btn_text != "Выберите компонент...":
                        comp_name = btn_text

                # Находим и обновляем label в сетке
                row = var_row + comp
                for widget in self.variants_frame.grid_slaves(row=row, column=1):
                    if isinstance(widget, ttk.Label):
                        widget.config(text=comp_name, anchor="w", width=30)

    def _on_nb_changed(self):
        """Отслеживает изменения количества компонентов и обновляет сетку"""
        self._update_components_grid()

    def _on_var_changed(self):
        """Отслеживает изменение количества вариаций и обновляет сетку"""
        self._update_components_grid()

    def _on_al_changed(self):
        """Отслеживает изменение участия внешнего окислителя и обновляет сетку"""
        self._update_components_grid()

    def _load_params(self, params: Dict):
        """Загружает параметры в виджеты"""

        # Директивы
        for code, var in self.directive_vars.items():
            var.set(params.get("directives", {}).get(code, False))

        # Параметры процесса
        self.pk_entry.insert(0, str(params.get("PK", 0.1)))
        self.pc_entry.insert(0, str(params.get("PC", 0.1)))

        # Рецептура
        self.nb_entry.insert(0, str(params.get("NB", 2)))
        self.var_entry.insert(0, str(params.get("N", 1)))
        self._create_components_grid()

        # Компоненты
        components = params.get("components", [])
        outer_oxy = params.get("outer_oxy", [])

        # Сначала загружаем основные компоненты
        for i, comp in enumerate(components):
            if i < len(self.formula_entries):
                self.id_entries[i].config(text=str(comp.get("id", 0)))
                self.formula_entries[i].config(text=comp.get("formula", ""))
                # Обновляем текст кнопки с названием компонента
                if comp.get("name"):
                    self.search_buttons[i].config(text=comp["name"])
                else:
                    self.search_buttons[i].config(text="Выберите компонент...")
                if comp.get("enthalpy") is not None:
                    self.enthalpy_entries[i].config(text=f"{comp['enthalpy']:.2f}")
                else:
                    self.enthalpy_entries[i].config(text="")

        # Затем загружаем внешний окислитель (если есть)
        if outer_oxy and len(outer_oxy) > 0 and len(self.oxy_id_entries) > 0:
            oxy = outer_oxy[0]
            self.oxy_id_entries[0].config(text=str(oxy.get("id", 0)))
            self.oxy_formula_entries[0].config(text=oxy.get("formula", ""))
            # Обновляем текст кнопки с названием компонента
            if oxy.get("name"):
                self.oxy_search_buttons[0].config(text=oxy["name"])
            else:
                self.oxy_search_buttons[0].config(text="Выберите компонент...")
            if oxy.get("enthalpy") is not None:
                self.oxy_enthalpy_entries[0].config(text=f"{oxy['enthalpy']:.2f}")
            else:
                self.oxy_enthalpy_entries[0].config(text="")

        # Загружаем концентрации из вариаций
        variants = params.get("variants", [])
        for var_idx, variant in enumerate(variants):
            if var_idx < len(self.conc_entries):
                concentrations = variant.get("concentrations", [])
                for comp_idx, conc in enumerate(concentrations):
                    if comp_idx < len(self.conc_entries[var_idx]):
                        entry = self.conc_entries[var_idx][comp_idx]
                        entry.delete(0, "end")
                        entry.insert(0, f"{conc:.2f}")

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
                    self.oxy_enthalpy_entries[comp_index].config(
                        text=f"{component.enthalpy:.2f}"
                    )
                else:
                    self.oxy_enthalpy_entries[comp_index].config(text="")
            else:
                self.id_entries[comp_index].config(text=str(component.id))
                self.formula_entries[comp_index].config(text=component.formula)
                self.search_buttons[comp_index].config(text=component.name)
                if component.enthalpy is not None:
                    self.enthalpy_entries[comp_index].config(
                        text=f"{component.enthalpy:.2f}"
                    )
                else:
                    self.enthalpy_entries[comp_index].config(text="")

            # Обновляем названия компонентов в вариациях
            self._update_variants_labels()

    def _on_focus_in(self, event):
        """Восстанавливает цвет текста при получении фокуса"""
        widget = event.widget
        # Просто возвращаем стандартный стиль (чёрный текст)
        widget.configure(style="TEntry")

    def _toggle_directives(self):
        """Переключение сворачивания/разворачивания панели директив"""
        if self.directives_expanded.get():
            # Сворачиваем - скрываем панель
            self.directives_frame.pack_forget()
            self.toggle_btn.config(text="▶ Развернуть")
            self.directives_expanded.set(False)
            self._directives_packed = False
        else:
            # Разворачиваем - показываем панель ПЕРЕД секцией параметров процесса
            # Находим proc_frame среди дочерних виджетов scrollable_frame
            proc_frame = None
            for widget in self.directives_frame.master.winfo_children():
                if isinstance(widget, ttk.LabelFrame) and "Параметры процесса" in widget.cget("text"):
                    proc_frame = widget
                    break
            
            if proc_frame:
                self.directives_frame.pack(fill="x", padx=10, pady=5, before=proc_frame)
            else:
                self.directives_frame.pack(fill="x", padx=10, pady=5)
            
            self.toggle_btn.config(text="▼ Свернуть")
            self.directives_expanded.set(True)
            self._directives_packed = True

    def _clear_validation_errors(self):
        """Сбрасывает все подсветки ошибок"""

        # Сброс для полей ввода
        widgets_to_check: List[Any] = [
            self.pk_entry,
            self.pc_entry,
            self.al_entry,
            self.nb_entry,
            self.var_entry,
        ]
        for widget in widgets_to_check:
            widget.configure(style="TEntry")

        # Сброс для кнопок поиска компонентов
        for btn in self.search_buttons:
            btn.configure(style="TButton")
        for btn in self.oxy_search_buttons:
            btn.configure(style="TButton")

        # Сброс для полей концентраций
        for var_entries in self.conc_entries:
            for entry in var_entries:
                entry.configure(style="TEntry")

    def _highlight_error(self, widget, message: str):
        """Делает текст поля красным"""
        style = ttk.Style()

        # Для Entry виджетов - красный текст
        if isinstance(widget, ttk.Entry):
            widget_id = str(widget)
            style_name = f"Error.{widget_id}.TEntry"
            style.configure(style_name, foreground="red")
            widget.configure(style=style_name)

        # Для кнопок - меняем стиль
        elif isinstance(widget, ttk.Button):
            widget_id = str(widget)
            style_name = f"Error.{widget_id}.TButton"
            style.configure(style_name, foreground="red")
            widget.configure(style=style_name)

    def _is_float(self, value: str) -> bool:
        """Проверяет, можно ли строку преобразовать в float"""
        try:
            float(value)
            return True
        except ValueError, TypeError:
            return False

    def _validate_params(self) -> tuple[bool, str, List[tuple]]:
        """
        Валидирует все введённые параметры.
        Возвращает кортеж (успех, сообщение_об_ошибке, список_виджетов_с_ошибками).
        """
        errors = []
        error_widgets: List[tuple] = []  # (виджет, сообщение)

        # === Проверка числовых полей процесса ===
        pk_str = self.pk_entry.get().strip()
        if not pk_str:
            errors.append("PK не указано")
            error_widgets.append((self.pk_entry, "PK не указано"))
        else:
            try:
                pk = float(pk_str)
                if pk <= 0:
                    errors.append("PK (давление в камере) должно быть > 0")
                    error_widgets.append((self.pk_entry, "PK должно быть > 0"))
            except ValueError:
                errors.append("PK должно быть числовым значением")
                error_widgets.append((self.pk_entry, "PK должно быть числом"))

        pc_str = self.pc_entry.get().strip()
        if not pc_str:
            errors.append("PC не указано")
            error_widgets.append((self.pc_entry, "PC не указано"))
        else:
            try:
                pc = float(pc_str)
                if pc <= 0:
                    errors.append("PC (давление на срезе) должно быть > 0")
                    error_widgets.append((self.pc_entry, "PC должно быть > 0"))
            except ValueError:
                errors.append("PC должно быть числовым значением")
                error_widgets.append((self.pc_entry, "PC должно быть числом"))

        al_str = self.al_entry.get().strip()
        if not al_str:
            errors.append("AL не указано")
            error_widgets.append((self.al_entry, "AL не указано"))
        else:
            try:
                al = float(al_str)
                if al < 0:
                    errors.append("AL (участие окислителя) должно быть ≥ 0")
                    error_widgets.append((self.al_entry, "AL должно быть ≥ 0"))
            except ValueError:
                errors.append("AL должно быть числовым значением")
                error_widgets.append((self.al_entry, "AL должно быть числом"))

        # === Проверка количества компонентов и вариаций ===
        nb_str = self.nb_entry.get().strip()
        if not nb_str:
            errors.append("Количество компонентов не указано")
            error_widgets.append((self.nb_entry, "Не указано"))
        else:
            try:
                nb = int(nb_str)
                if nb < 2:
                    errors.append("Количество компонентов должно быть ≥ 2")
                    error_widgets.append((self.nb_entry, "Должно быть ≥ 2"))
            except ValueError:
                errors.append("Количество компонентов должно быть целым числом")
                error_widgets.append((self.nb_entry, "Должно быть целым числом"))

        n_str = self.var_entry.get().strip()
        if not n_str:
            errors.append("Количество вариаций не указано")
            error_widgets.append((self.var_entry, "Не указано"))
        else:
            try:
                n = int(n_str)
                if n < 1:
                    errors.append("Количество вариаций должно быть ≥ 1")
                    error_widgets.append((self.var_entry, "Должно быть ≥ 1"))
            except ValueError:
                errors.append("Количество вариаций должно быть целым числом")
                error_widgets.append((self.var_entry, "Должно быть целым числом"))

        # === Проверка выбора компонентов ===
        nb = int(nb_str) if nb_str.isdigit() else 0
        for i in range(nb):
            button_text = self.search_buttons[i].cget("text")
            if button_text == "Выберите компонент...":
                errors.append(f"Не выбран компонент № {i + 1}")
                error_widgets.append((self.search_buttons[i], f"Компонент № {i + 1}"))

            comp_id_str = self.id_entries[i].cget("text").strip()
            if not comp_id_str or comp_id_str == "0":
                errors.append(f"Компонент № {i + 1}: не выбран из каталога")
                error_widgets.append((self.search_buttons[i], f"Компонент № {i + 1}"))

        # === Проверка внешнего окислителя ===
        al = float(al_str) if self._is_float(al_str) else 0
        if al != 0:
            if len(self.oxy_id_entries) > 0:
                button_text = self.oxy_search_buttons[0].cget("text")
                if button_text == "Выберите компонент...":
                    errors.append("Не выбран внешний окислитель")
                    error_widgets.append(
                        (self.oxy_search_buttons[0], "Внешний окислитель")
                    )

                oxy_id_str = self.oxy_id_entries[0].cget("text").strip()
                if not oxy_id_str or oxy_id_str == "0":
                    errors.append("Внешний окислитель: не выбран из каталога")
                    error_widgets.append(
                        (self.oxy_search_buttons[0], "Внешний окислитель")
                    )

        # === Проверка концентраций ===
        for var_idx, var_entries in enumerate(self.conc_entries):
            concentrations = []
            for entry in var_entries:
                val_str = entry.get().strip()
                if val_str:
                    try:
                        val = float(val_str)
                        if val < 0:
                            errors.append(
                                f"В вариации № {var_idx + 1}: отрицательная концентрация"
                            )
                            error_widgets.append((entry, "Отрицательная"))
                        concentrations.append(val)
                    except ValueError:
                        errors.append("Концентрация должна быть числом")
                        error_widgets.append((entry, "Не число"))
                else:
                    concentrations.append(0.0)

            # Проверка суммы с допуском на погрешность float
            if concentrations:
                conc_sum = sum(concentrations)
                if abs(conc_sum - 100.0) > 0.01:
                    errors.append(
                        f"В вариации № {var_idx + 1}: сумма = {conc_sum:.2f} (должна быть 100.00)"
                    )
                    # Подсвечиваем все поля в этой вариации
                    for entry in var_entries:
                        if entry not in [ew[0] for ew in error_widgets]:
                            error_widgets.append((entry, "Сумма ≠ 100"))

        if errors:
            return False, "\n".join(errors), error_widgets
        return True, "", []

    def _on_ok(self):
        """Собирает данные, валидирует через Params и закрывает окно"""
        # Сначала валидация
        is_valid, error_msg, error_widgets = self._validate_params()
        if not is_valid:
            # Сбрасываем старую подсветку и подсвечиваем новые ошибки
            self._clear_validation_errors()
            for widget, _ in error_widgets:
                self._highlight_error(widget, "")
            messagebox.showerror("Ошибка ввода", error_msg)
            return

        try:
            # Директивы - добавляем все, включая False значения
            directives = {}
            for code, var in self.directive_vars.items():
                directives[code] = bool(var.get())

            # Рецептура
            nb = int(self.nb_entry.get())
            n = int(self.var_entry.get())
            al_value = float(self.al_entry.get())
            al_nb = 1 if al_value != 0 else 0

            # Концентрации
            variants = []
            for idx in range(len(self.conc_entries)):
                concentrations = []
                for entry in self.conc_entries[idx]:
                    val_str = entry.get().strip()
                    val = float(val_str) if val_str else 0.0
                    concentrations.append(val)
                variants.append({"id": idx + 1, "concentrations": concentrations})

            # Компоненты - основные компоненты (индексы 0..nb-1)
            components = []
            for i in range(nb):
                comp_id = int(self.id_entries[i].cget("text").strip() or 0)
                formula = self.formula_entries[i].cget("text").strip()
                enthalpy_str = self.enthalpy_entries[i].cget("text").strip()
                enthalpy = float(enthalpy_str) if enthalpy_str else None
                button_text = self.search_buttons[i].cget("text")
                name = button_text

                components.append(
                    {
                        "id": comp_id,
                        "name": name,
                        "formula": formula,
                        "enthalpy": enthalpy,
                    }
                )

            # AL_variants
            al_variants = [{"id": 1, "concentrations": [100.0]}]

            # Создаём и валидируем через класс Params
            params_obj = Params(
                author="Белобородов",
                code="*",
                directives=directives,
                PK=float(self.pk_entry.get()),
                PC=float(self.pc_entry.get()),
                AL=al_value,
                N=n,
                NB=nb,
                AL_N=1 if al_value != 0 else 0,
                AL_NB=al_nb,
                variants=variants,
                components=components,
                al_variants=al_variants,
            )

            self.result = params_obj.to_dict()

            # Добавляем outer_oxy если есть внешний окислитель
            if al_value != 0 and len(self.oxy_id_entries) > 0:
                comp_id = int(self.oxy_id_entries[0].cget("text").strip() or 0)
                formula = self.oxy_formula_entries[0].cget("text").strip()
                enthalpy_str = self.oxy_enthalpy_entries[0].cget("text").strip()
                enthalpy = float(enthalpy_str) if enthalpy_str else None
                button_text = self.oxy_search_buttons[0].cget("text")
                name = button_text
                if button_text == "Выберите компонент...":
                    raise ValueError("Не выбран внешний окислитель")

                self.result["outer_oxy"] = [
                    {
                        "id": comp_id,
                        "name": name,
                        "formula": formula,
                        "enthalpy": enthalpy,
                    }
                ]

            # Отписка обработчика прокрутки перед закрытием
            self.main_canvas.unbind_all("<MouseWheel>")
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Ошибка ввода", str(e))

    def _save_template(self):
        """Сохранение шаблона"""
        import json
        from tkinter import filedialog

        filepath = filedialog.asksaveasfilename(
            title="Сохранить шаблон",
            defaultextension=".json",
            filetypes=[("JSON файлы", "*.json"), ("Все файлы", "*.*")],
        )
        if filepath:
            try:
                self._on_ok()
                if self.result:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(self.result, f, ensure_ascii=False, indent=2)
                    messagebox.showinfo("Успех", f"Шаблон сохранен:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    def get_params(self) -> Optional[Dict]:
        """Возвращает результат после закрытия окна"""
        self.parent.wait_window(self.dialog)
        return self.result

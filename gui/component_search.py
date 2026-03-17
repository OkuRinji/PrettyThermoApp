import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from models.component import Component

from core.catalog_manager import CatalogManager


class ComponentSearchDialog:
    """Диалог поиска и выбора компонента из каталога"""

    def __init__(self, parent, catalog: CatalogManager = None):
        self.parent = parent
        self.catalog = catalog or CatalogManager()
        self.result: Optional[Component] = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Выбор компоннета из катлога")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = (parent.winfo_width() // 2) - (800 // 2)
        y = (parent.winfo_height() // 2) - (600 // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self._create_widgets()
        self._load_all_components()

    def _create_widgets(self):
        # Поиск
        search_frame = ttk.Frame(self.dialog, padding=10)
        search_frame.pack(fill="x")

        ttk.Label(search_frame, text="🔍 Поиск:").pack(side="left")
        self.search_entry = ttk.Entry(search_frame, width=50)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self._search())
        self.search_entry.focus_set()

        ttk.Button(search_frame, text="Найти", command=self._search).pack(
            side="left", padx=5
        )

        # Статистика
        self.status_var = tk.StringVar(value=f"Всего: {len(self.catalog.components)}")
        ttk.Label(search_frame, textvariable=self.status_var).pack(side="right")

        # Таблица результатов
        tree_frame = ttk.Frame(self.dialog, padding=10)
        tree_frame.pack(fill="both", expand=True)

        columns = ("id", "name", "formula", "enthalpy")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=20
        )

        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Название")
        self.tree.heading("formula", text="Формула")
        self.tree.heading("enthalpy", text="Энтальпия (кДж/кг)")

        self.tree.column("id", width=50, anchor="center")
        self.tree.column("name", width=400)
        self.tree.column("formula", width=200)
        self.tree.column("enthalpy", width=100, anchor="e")

        # Скроллбары
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        # Двойной клик для выбора
        self.tree.bind("<Double-1>", lambda e: self._on_select())
        self.tree.bind("<Return>", lambda e: self._on_select())

        # Кнопки
        btn_frame = ttk.Frame(self.dialog, padding=10)
        btn_frame.pack(fill="x")

        ttk.Button(
            btn_frame, text="✅ Выбрать", command=self._on_select, width=15
        ).pack(side="left", padx=5)
        ttk.Button(
            btn_frame, text="❌ Отмена", command=self.dialog.destroy, width=15
        ).pack(side="left", padx=5)

        # Инфо о выбранном
        info_frame = ttk.LabelFrame(
            self.dialog, text="Информация о компоненте", padding=10
        )
        info_frame.pack(fill="x", padx=10, pady=5)

        self.info_var = tk.StringVar(value="Выберите компонент из списка")
        ttk.Label(info_frame, textvariable=self.info_var, wraplength=700).pack(
            anchor="w"
        )

        # Обновление инфо при выделении
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_info())

    def _load_all_components(self):
        """Загружает все компоненты в таблицу"""

        for item in self.tree.get_children():
            self.tree.delete(item)

        for comp in self.catalog.get_all():
            self.tree.insert(
                "",
                "end",
                values=(
                    comp.id,
                    comp.name,
                    comp.formula,
                    f"{comp.enthalpy:.2f}" if comp.enthalpy is not None else "N/A",
                ),
                tags=("comps",),
            )

    def _search(self):
        """Выполняет поиск"""

        query = self.search_entry.get().strip()

        # Очистка таблицы
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not query:
            self._load_all_components()
            self.status_var.set(f"Всего: {len(self.catalog.components)}")
            return

        results = self.catalog.search(query)
        for comp in results:
            self.tree.insert(
                "",
                "end",
                values=(
                    comp.id,
                    comp.name,
                    comp.formula,
                    f"{comp.enthalpy:.2f}" if comp.enthalpy is not None else "N/A",
                ),
            )

        self.status_var.set(f"Найдено: {len(results)}")

    def _update_info(self):
        """Обновляет информацию о выбранном компоненте"""
        selection = self.tree.selection()
        if not selection:
            self.info_var.set("Выберите компонент из списка")
            return

        item = self.tree.item(selection[0])
        comp_id = int(item["values"][0])
        comp = self.catalog.get_by_id(comp_id)

        if comp:
            info = f"ID: {comp.id} | {comp.name}\n"
            info += f"Формула: {comp.formula}\n"
            info += (
                f"Энтальпия: {comp.enthalpy:.2f} кДж/кг"
                if comp.enthalpy
                else "Энтальпия: N/A"
            )
            self.info_var.set(info)

    def _on_select(self):
        """Выбор компонента"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Внимание", "Выберите компонент из списка")
            return

        item = self.tree.item(selection[0])
        comp_id = int(item["values"][0])

        self.result = self.catalog.get_by_id(comp_id)
        self.dialog.destroy()

    def get_component(self) -> Optional[Component]:
        """Возвращает выбранный компонент"""
        self.parent.wait_window(self.dialog)
        return self.result

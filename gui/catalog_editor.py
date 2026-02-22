# gui/catalog_editor.py
"""
Редактор каталога компонентов - обёртка для запуска CatalogEditorApp
"""
import tkinter as tk
import sys
from pathlib import Path

# Добавляем директорию CatalogEditor в path для импорта
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir / 'CatalogEditor'))

from CatalogEditor.catalog_app import CatalogEditorApp


class CatalogEditor:
    """Редактор каталога компонентов (обёртка для запуска отдельного приложения)"""

    def __init__(self, parent=None):
        # Создаём новое окно для отдельного приложения
        self.app_window = tk.Toplevel(parent) if parent else tk.Tk()
        self.app = CatalogEditorApp(self.app_window)

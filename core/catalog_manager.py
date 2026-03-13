#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер каталога компонентов для термодинамического расчета.

Предоставляет функционал загрузки, поиска и управления компонентами.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

from core.component import Component
from core.res_parser import ResParser

logger = logging.getLogger(__name__)


class CatalogManager:
    """
    Менеджер каталога компонентов (потокобезопасный синглтон).
    
    Предназначен для загрузки компонентов из JSON и RES файлов,
    поиска по названию/формуле/ID, и управления каталогом.
    
    Example:
        >>> catalog = CatalogManager()
        >>> catalog.load_from_json("components.json")
        >>> results = catalog.search("H2O")
    """

    _instance: Optional["CatalogManager"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "CatalogManager":
        """Создание экземпляра синглтона (потокобезопасное)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Инициализация менеджера каталога."""
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        self.components: Dict[int, Component] = {}
        self.name_index: Dict[str, int] = {}

        logger.debug("CatalogManager инициализирован")

    def load_from_json(self, filepath: str) -> bool:
        """
        Загрузка каталога компонентов из JSON файла.

        Args:
            filepath: Путь к JSON файлу с компонентами.
                     Формат: [{"id": 1, "name": "...", "formula": "...", "enthalpy": 0.0}, ...]

        Returns:
            True если загрузка успешна, иначе False.

        Raises:
            json.JSONDecodeError: При некорректном формате JSON.
            KeyError: При отсутствии обязательных полей в данных.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Файл каталога не найден: {filepath}")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            loaded_count = 0
            for item in data:
                comp = Component(
                    id=item["id"],
                    name=item["name"],
                    formula=item["formula"],
                    enthalpy=item["enthalpy"],
                )
                self.components[comp.id] = comp
                self.name_index[comp.name.lower()] = comp.id
                loaded_count += 1

            logger.info(f"Загружено {loaded_count} компонентов из {filepath}")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка формата JSON в файле {filepath}: {e}")
            return False
        except KeyError as e:
            logger.error(f"Отсутствует обязательное поле в данных: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при загрузке каталога: {e}")
            return False

    def load_from_res(self, filepath: str) -> bool:
        """
        Загрузка компонентов из .res файла (результаты расчета).

        Args:
            filepath: Путь к .res файлу.

        Returns:
            True если загрузка успешна, иначе False.
        """
        path = Path(filepath)
        if not path.exists():
            logger.warning(f"Файл .res не найден: {filepath}")
            return False

        try:
            parser = ResParser(str(path))
            data = parser.parse()

            # Получаем существующие ID для маппинга
            existing_ids = set(self.components.keys())
            max_id = max(existing_ids) if existing_ids else 0

            loaded_count = 0
            for idx, res_comp in enumerate(data.components):
                comp_id = max_id + idx + 1
                comp = Component(
                    id=comp_id,
                    name=res_comp.name,
                    formula=res_comp.name,  # Используем name как формулу
                    enthalpy=res_comp.hf298,
                )
                self.components[comp.id] = comp
                self.name_index[comp.name.lower()] = comp.id
                loaded_count += 1

            logger.info(f"Загружено {loaded_count} компонентов из {filepath}")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки из .res файла {filepath}: {e}")
            return False

    def search(self, query: str) -> List[Component]:
        """
        Поиск компонентов по названию, формуле или ID.

        Args:
            query: Строка поиска (часть названия, формулы или ID).

        Returns:
            Отсортированный по ID список найденных компонентов.
        """
        query_lower = query.lower()
        results: List[Component] = []

        for comp in self.components.values():
            if (
                query_lower in comp.name.lower()
                or query_lower in comp.formula.lower()
                or str(comp.id) == query
            ):
                results.append(comp)

        return sorted(results, key=lambda x: x.id)

    def get_by_id(self, comp_id: int) -> Optional[Component]:
        """
        Получение компонента по ID.

        Args:
            comp_id: ID искомого компонента.

        Returns:
            Компонент если найден, иначе None.
        """
        return self.components.get(comp_id)

    def get_by_ids(self, ids: List[int]) -> List[Component]:
        """
        Получение нескольких компонентов по списку ID.

        Args:
            ids: Список ID компонентов.

        Returns:
            Список найденных компонентов (пропускает несуществующие ID).
        """
        return [self.components[comp_id] for comp_id in ids if comp_id in self.components]

    def get_all(self) -> List[Component]:
        """
        Получение всех компонентов каталога.

        Returns:
            Отсортированный по ID список всех компонентов.
        """
        return sorted(self.components.values(), key=lambda x: x.id)

    def get_categories(self) -> List[str]:
        """
        Получение списка категорий (по первым буквам названий).

        Returns:
            Отсортированный список уникальных категорий.
        """
        categories: set[str] = set()
        for comp in self.components.values():
            # Первая буква или первые 2-3 символа
            cat = comp.name.split()[0][:3] if comp.name else "???"
            categories.add(cat)
        return sorted(categories)

    def get_count(self) -> int:
        """
        Получение количества компонентов в каталоге.

        Returns:
            Количество загруженных компонентов.
        """
        return len(self.components)

    def clear(self) -> None:
        """
        Очистка каталога (удаление всех компонентов).
        """
        self.components.clear()
        self.name_index.clear()
        logger.debug("Каталог очищен")

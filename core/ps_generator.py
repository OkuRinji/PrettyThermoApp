#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Генератор PS файлов для программы TERMO94.

Создаёт входные файлы в формате, требуемом программой TERMO94,
на основе параметров расчета.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Union

logger = logging.getLogger(__name__)

# Константы
DEFAULT_AUTHOR = "Каф. ТИПиКМ"
DEFAULT_CODE = "*"
LINE_ENCODING = "cp866"
LINE_ENDING = "\r\n"


class PSGenerator:
    """
    Генератор PS файлов для TERMO94.

    Создаёт файлы в формате, совместимом с программой TERMO94,
    включая метаданные, директивы, параметры процесса и рецептуру.

    Example:
        >>> generator = PSGenerator("TERMO/")
        >>> filepath = generator.generate(params, "calc.ps")
    """

    def __init__(self, work_dir: str):
        """
        Инициализация генератора.

        Args:
            work_dir: Рабочая директория для сохранения PS файлов.
        """
        self.work_dir = Path(work_dir)
        logger.debug(f"PSGenerator инициализирован: work_dir={work_dir}")

    def generate(
        self,
        params: Dict[str, Any],
        filename: str = "input.ps",
    ) -> str:
        """
        Генерация PS файла для TERMO94.

        Args:
            params: Словарь параметров расчета.
            filename: Имя выходного файла.

        Returns:
            Полный путь к созданному файлу.

        Raises:
            IOError: При ошибке записи файла.
            KeyError: При отсутствии обязательных параметров.
        """
        filepath = self.work_dir / filename

        try:
            with open(filepath, "w", encoding=LINE_ENCODING, newline=LINE_ENDING) as f:
                # 1. Метаданные
                self._write_metadata(f, params)

                # 2. Блок директив NAMELIST RRP
                self._write_directives(f, params.get("directives", {}))

                # 3. Параметры процесса
                self._write_process_params(f, params)

                # 4. Рецептура (основные компоненты)
                self._write_recipe(f, params)

                # 5. Внешний окислитель (если есть)
                if params.get("AL") and params["AL"] != 0:
                    self._write_outer_oxy(f, params)

            logger.info(f"PS файл создан: {filepath}")
            return str(filepath)

        except IOError as e:
            logger.error(f"Ошибка записи PS файла {filepath}: {e}")
            raise
        except KeyError as e:
            logger.error(f"Отсутствует обязательный параметр: {e}")
            raise

    def _write_metadata(self, f, params: Dict[str, Any]) -> None:
        """Запись метаданных (исполнитель, шифр)."""
        author = params.get("author", DEFAULT_AUTHOR)
        code = params.get("code", DEFAULT_CODE)
        meta = f"Исполнитель : * {author:<10} *   Шифр {code:<10}   *\n"
        f.write(meta)

    def _write_directives(self, f, directives: Dict[str, Any]) -> None:
        """
        Запись блока директив NAMELIST RRP.

        Args:
            f: Файловый объект.
            directives: Словарь директив.
        """
        parts = []
        for key, value in directives.items():
            if isinstance(value, bool):
                parts.append(f"{key}={'T' if value else 'F'}")
            else:
                parts.append(f"{key}={value}")

        directive_line = " &RRP " + ",".join(parts) + " /&END\n"
        f.write(directive_line)

    def _write_process_params(self, f, params: Dict[str, Any]) -> None:
        """Запись параметров процесса (PK, PC, AL и др.)."""
        process_params = ["PK", "PC", "AL", "VK", "PH", "OP", "OF", "TP"]
        for param in process_params:
            if param in params and params[param] is not None:
                f.write(f"{param}={params[param]}\n")

    def _write_recipe(self, f, params: Dict[str, Any]) -> None:
        """Запись рецептуры состава."""
        # N=... NB=...
        f.write(f"N={params['N']}  NB={params['NB']}\n")

        # Варианты и концентрации
        for variant in params["variants"]:
            concentrations = ",".join(
                [self._format_conc(x) for x in variant["concentrations"]]
            )
            f.write(f"{variant['id']},{concentrations}\n")

        # Компоненты
        for comp in params["components"]:
            enthalpy_str = f"{comp['enthalpy']:>9.2f}"
            formula_str = comp["formula"]
            f.write(f"{enthalpy_str}{formula_str}\n")

    def _write_outer_oxy(self, f, params: Dict[str, Any]) -> None:
        """Запись параметров внешнего окислителя."""
        f.write(f"N={params['AL_N']}  NB={params['AL_NB']}\n")

        for variant in params["AL_variants"]:
            concentrations = ",".join(
                [self._format_conc(x) for x in variant["concentrations"]]
            )
            f.write(f"{variant['id']},{concentrations}\n")

        for comp in params["outer_oxy"]:
            enthalpy_str = f"{comp['enthalpy']:>9.2f}"
            formula_str = comp["formula"]
            f.write(f"{enthalpy_str}{formula_str}\n")

    @staticmethod
    def _format_conc(value: Union[int, float]) -> str:
        """
        Форматирование концентрации (50., 66.7, 10.4).

        Args:
            value: Значение концентрации.

        Returns:
            Отформатированная строка концентрации.
        """
        if value == int(value):
            return f"{int(value)}."
        else:
            # Убираем лишние нули после запятой
            formatted = f"{value:.1f}".rstrip("0").rstrip(".")
            return formatted + "." if "." in formatted else formatted + "."

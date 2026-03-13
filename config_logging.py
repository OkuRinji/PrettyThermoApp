#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация логирования для проекта PrettyThermo.

Использование:
    from config_logging import setup_logging
    setup_logging()
"""

import logging
import sys
from pathlib import Path


def setup_logging(
    level: int = logging.INFO,
    log_file: str = "thermo.log",
    log_format: str | None = None,
) -> None:
    """
    Настройка системы логирования для приложения.

    Args:
        level: Уровень логирования (по умолчанию INFO).
        log_file: Имя файла для записи логов.
        log_format: Формат сообщений (по умолчанию стандартный).
    """
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Создаём обработчики
    handlers = [
        logging.StreamHandler(sys.stdout),
    ]

    # Добавляем файловый обработчик если указана директория для логов
    log_path = Path(log_file)
    try:
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        handlers.append(file_handler)
    except (PermissionError, OSError) as e:
        print(f"Предупреждение: не удалось создать файл лога {log_path}: {e}")

    # Настраиваем логирование
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=handlers,
    )

    # Устанавливаем уровень для сторонних библиотек
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Получение логгера по имени.

    Args:
        name: Имя логгера (обычно __name__ модуля).

    Returns:
        Настроенный логгер.
    """
    return logging.getLogger(name)

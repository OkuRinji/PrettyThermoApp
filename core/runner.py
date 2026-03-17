#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль запуска программы TERM94 через OTVDM (winevdm).

Предоставляет класс OTVDMMRunner для синхронного и асинхронного запуска
термодинамических расчетов.
"""

import logging
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Константы
DEFAULT_TIMEOUT_MS = 300000  # 5 минут по умолчанию
DEFAULT_EXE_NAME = "TERM94.EXE"


class OTVDMMRunner:
    """
    Раннер для запуска программы TERM94 через OTVDM.

    Поддерживает синхронный и асинхронный запуск, скрытие окна,
    таймауты и обратные вызовы.

    Example:
        >>> runner = OTVDMMRunner("otvdm/otvdmw.exe", "TERMO/")
        >>> runner.run(ps_file="calc.ps", hidden=True)
    """

    def __init__(
        self,
        otvdm_path: str,
        work_dir: str,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ):
        """
        Инициализация раннера.

        Args:
            otvdm_path: Путь к исполняемому файлу otvdm (winevdm).
            work_dir: Рабочая директория для запуска программы.
            timeout_ms: Таймаут выполнения расчета в миллисекундах.
        """
        self.otvdm_path = Path(otvdm_path)
        self.work_dir = Path(work_dir)
        self.timeout_ms = timeout_ms
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False

        logger.debug(
            f"OTVDMMRunner инициализирован: otvdm={otvdm_path}, work_dir={work_dir}"
        )

    def run(
        self,
        exe_name: str = DEFAULT_EXE_NAME,
        ps_file: Optional[str] = None,
        hidden: bool = True,
        async_mode: bool = False,
        on_complete: Optional[Callable[[bool], None]] = None,
    ) -> bool:
        """
        Запуск расчета через otvdm (winevdm).

        Args:
            exe_name: Имя исполняемого файла (по умолчанию TERM94.EXE).
            ps_file: Имя .ps файла для запуска (только имя, без пути).
            hidden: Скрыть окно программы (по умолчанию True).
            async_mode: Запустить в отдельном потоке (по умолчанию False).
            on_complete: Функция обратного вызова после завершения.
                        Вызывается с аргументом True/False (успех/ошибка).

        Returns:
            True если запуск успешен (для sync) или поток запущен (для async),
            иначе False.
        """

        def _run_process(ps_path: Optional[str]) -> bool:
            exe_path = self.work_dir / exe_name

            commands = [str(self.otvdm_path), str(exe_path)]

            # Если указано имя .ps файла, добавляем его как аргумент
            if ps_path:
                # Добавляем .ps если нет расширения
                if not ps_path.lower().endswith(".ps"):
                    ps_path += ".ps"
                commands.append(ps_path)

            try:
                self.is_running = True
                logger.info(f"Запуск расчета: {' '.join(commands)}")

                if hidden and sys.platform == "win32":
                    # Запуск без видимого окна (только для Windows)
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = subprocess.SW_HIDE
                    self.process = subprocess.Popen(
                        commands, cwd=str(self.work_dir), startupinfo=startupinfo
                    )
                else:
                    self.process = subprocess.Popen(commands, cwd=str(self.work_dir))

                # Ждем завершения процесса с таймаутом
                timeout_sec = self.timeout_ms / 1000.0
                try:
                    self.process.wait(timeout=timeout_sec)
                    logger.info("Расчет завершен успешно")
                except subprocess.TimeoutExpired:
                    logger.error(f"Расчет превысил таймаут ({timeout_sec}с)")
                    self.process.terminate()
                    self.is_running = False
                    if on_complete:
                        on_complete(False)
                    return False

                self.is_running = False

                # Вызываем функцию обратного вызова если указана
                if on_complete:
                    on_complete(True)

                return True

            except FileNotFoundError as e:
                logger.error(f"Файл не найден: {e}")
                self.is_running = False
                if on_complete:
                    on_complete(False)
                return False
            except PermissionError as e:
                logger.error(f"Нет доступа к файлу: {e}")
                self.is_running = False
                if on_complete:
                    on_complete(False)
                return False
            except Exception as e:
                logger.error(f"Ошибка запуска otvdm: {e}")
                self.is_running = False
                if on_complete:
                    on_complete(False)
                return False

        if async_mode:
            # Запуск в отдельном потоке
            logger.debug("Запуск расчета в асинхронном режиме")
            thread = threading.Thread(target=_run_process, args=(ps_file,), daemon=True)
            thread.start()
            return True
        else:
            # Синхронный запуск
            return _run_process(ps_file)

    def stop(self) -> None:
        """
        Остановка запущенного процесса.

        Если процесс не запущен, метод ничего не делает.
        """
        if self.process and self.is_running:
            logger.info("Остановка процесса расчета")
            self.process.terminate()
            self.is_running = False

    def is_process_running(self) -> bool:
        """
        Проверка статуса выполнения процесса.

        Returns:
            True если процесс выполняется, иначе False.
        """
        return self.is_running and self.process is not None

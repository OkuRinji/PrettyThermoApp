"""
Модуль организации серийных расчетов.

Разбивает параметры на чанки в соответствии с правилами сплиттера,
выполняет расчеты последовательно и собирает результаты в ResultSeries.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

from tkinter import messagebox

from core.runner import OTVDMMRunner
from core.ps_generator import PSGenerator
from core.res_parser import ResParser
from models.results import ResultSeries, Result
from models.res_component import ResComponent
from models.params import Params


class ChunkSplitter:
    """
    Сплиттер для разбиения вариаций на чанки.

    Определяет максимальный размер чанка в зависимости от количества
    компонентов (NB) для предотвращения переполнения памяти TERM94.
    """

    # Правила разбиения в зависимости от NB (количества компонентов)
    CHUNK_RULES = {
        2: 66,
        3: 50,
        4: 40,
        5: 33,
        6: 28,
    }

    @classmethod
    def get_chunk_size(cls, nb: int) -> int:
        """
        Получить размер чанка для заданного NB (количество компонентов).

        Args:
            nb: Количество компонентов в смеси.

        Returns:
            Максимальный размер чанка (количество вариаций).

        Raises:
            ValueError: Если NB не поддерживается.
        """
        if nb not in cls.CHUNK_RULES:
            raise ValueError(
                f"Неподдерживаемое значение NB={nb}. "
                f"Допустимые значения: {list(cls.CHUNK_RULES.keys())}"
            )
        return cls.CHUNK_RULES[nb]

    @classmethod
    def split(cls, params: Params) -> list[list[dict]]:
        """
        Разбить вариации на чанки.

        Args:
            params: Параметры расчета.

        Returns:
            Список чанков, где каждый чанк - список вариаций.
        """
        # Используем NB (количество компонентов) для определения размера чанка
        chunk_size = cls.get_chunk_size(int(params.NB))
        variants = params.variants

        chunks = []
        for i in range(0, len(variants), chunk_size):
            chunk = variants[i : i + chunk_size]
            chunks.append(chunk)

        return chunks


class Calculator:
    """
    Организатор серийных термодинамических расчетов.

    Разбивает большую серию вариаций на чанки, последовательно
    выполняет расчеты и собирает результаты в ResultSeries.

    Example:
        >>> calculator = Calculator(runner, generator, params, logger, root, base_path)
        >>> series = calculator.run_all(on_progress=callback)
    """

    def __init__(
        self,
        runner: OTVDMMRunner,
        generator: PSGenerator,
        params: Params,
        logger: logging.Logger,
        root,
        base_path: Path,
    ):
        """
        Инициализация калькулятора.

        Args:
            runner: Раннер для запуска TERM94.
            generator: Генератор PS файлов.
            params: Параметры расчета.
            logger: Логгер для вывода сообщений.
            root: Корневое окно tkinter.
            base_path: Базовый путь приложения.
        """
        self.root = root
        self.runner = runner
        self.generator = generator
        self.params = params
        self.logger = logger
        self.base_path = base_path
        self.work_dir = base_path / "TERMO"

        # Результат серии
        self.series = ResultSeries(params=params)

        # Состояние
        self._current_chunk_index = 0
        self._current_file_index = 0
        self._result_counter = 0
        self._chunks: list[list[dict]] = []
        self._ps_file_list: list[str] = []

    def _chunk_split(self) -> list[list[dict]]:
        """
        Разбить вариации на чанки для последовательного расчета.

        Returns:
            Список чанков с вариациями.
        """
        return ChunkSplitter.split(self.params)

    def _generate_ps(self, fn: str, variants: list[dict]) -> bool:
        """
        Сгенерировать PS файл с указанными вариациями.

        Args:
            fn: Имя файла (без расширения).
            variants: Список вариаций для записи.

        Returns:
            True если файл успешно создан, иначе False.
        """
        # Сохраняем оригинальные значения
        original_variants = self.params.variants.copy()
        original_n = self.params.N

        # Устанавливаем вариации и их количество для текущего батча
        self.params.variants = variants
        self.params.N = len(variants)

        try:
            # Конвертируем Params в словарь для генератора
            params_dict = self.params.to_dict()
            filepath = self.generator.generate(params_dict, f"{fn}.ps")
            self.logger.info(f"PS файл создан: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка генерации PS файла: {e}")
            messagebox.showerror("Ошибка", str(e))
            return False
        finally:
            # Восстанавливаем оригинальные значения
            self.params.variants = original_variants
            self.params.N = original_n

    def _load_results_from_file(self, fn: str) -> list[Result]:
        """
        Загрузить результаты из .res файла.

        Args:
            fn: Имя файла расчета (без расширения).

        Returns:
            Список результатов расчета.
        """
        res_path = self.work_dir / f"{fn}.res"

        if not res_path.exists():
            self.logger.warning(f"Файл результатов не найден: {res_path}")
            return []

        try:
            parser = ResParser(str(res_path))
            data = parser.parse()

            # Сохраняем метаданные серии из первого файла
            if not self.series.mixture_name:
                self.series.mixture_name = data.mixture_name
                self.series.mixture_density = data.mixture_density
                self.series.element_composition = data.element_composition
                self.series.components = data.components

            self.logger.info(f"Результаты загружены: {res_path}")
            return data.calculations

        except FileNotFoundError as e:
            self.logger.error(f"Файл не найден: {e}")
            return []
        except PermissionError as e:
            self.logger.error(f"Нет доступа к файлу: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Ошибка чтения результатов: {e}")
            return []

    def _convert_to_result(self, calc: Result, variant: dict) -> Result:
        """
        Конвертировать расчет в Result с добавлением концентрации.

        Args:
            calc: Результат расчета из парсера.
            variant: Вариация с концентрациями.

        Returns:
            Результат с добавлением composition_percent.
        """
        calc.composition_percent = variant["concentrations"]
        return calc

    def run_all(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_complete: Optional[Callable[[ResultSeries], None]] = None,
    ) -> ResultSeries:
        """
        Выполнить все расчеты в серии.

        Метод блокирующий - выполняет все расчеты последовательно.

        Args:
            on_progress: Callback для уведомления о прогрессе (current, total).
            on_complete: Callback для уведомления о завершении.

        Returns:
            ResultSeries с результатами всех расчетов.
        """
        # Разбиваем на чанки
        self._chunks = self._chunk_split()
        total_chunks = len(self._chunks)

        self.logger.info(
            f"Начало серии расчетов: {total_chunks} чанков, "
            f"всего вариаций: {len(self.params.variants)}"
        )

        # Генерируем все PS файлы
        self._ps_file_list = []
        for i, chunk in enumerate(self._chunks):
            fn = f"batch_{i}"
            if self._generate_ps(fn, chunk):
                self._ps_file_list.append(fn)
            else:
                self.logger.error(f"Не удалось создать PS файл для чанка {i}")
                continue

        # Выполняем расчеты последовательно
        for i, fn in enumerate(self._ps_file_list):
            if on_progress:
                on_progress(i + 1, len(self._ps_file_list))

            self.logger.info(f"Запуск расчета {i + 1}/{len(self._ps_file_list)}: {fn}")

            # Запускаем расчет синхронно
            success = self.runner.run(ps_file=fn, async_mode=False, hidden=True)

            if success:
                # Загружаем результаты
                calculations = self._load_results_from_file(fn)

                # Находим соответствующие вариации для этого чанка
                chunk = self._chunks[i]
                for j, calc in enumerate(calculations):
                    variant = chunk[j] if j < len(chunk) else chunk[-1]
                    result = self._convert_to_result(calc, variant)
                    self.series.add_result(result)

                self.logger.info(
                    f"Чанк {i} завершен: загружено {len(calculations)} результатов"
                )
            else:
                self.logger.error(f"Ошибка расчета для чанка {i}: {fn}")

        self.logger.info(
            f"Серия расчетов завершена. Всего результатов: {len(self.series)}"
        )

        if on_complete:
            on_complete(self.series)

        return self.series

    def run_all_async(
        self,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_complete: Optional[Callable[[ResultSeries], None]] = None,
        on_chunk_complete: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        """
        Выполнить все расчеты в асинхронном режиме.

        Args:
            on_progress: Callback для уведомления о прогрессе (current, total).
            on_complete: Callback для уведомления о завершении всей серии.
            on_chunk_complete: Callback для уведомления о завершении чанка.
        """
        self._chunks = self._chunk_split()
        self._ps_file_list = []

        # Генерируем все PS файлы заранее
        for i, chunk in enumerate(self._chunks):
            fn = f"batch_{i}"
            if self._generate_ps(fn, chunk):
                self._ps_file_list.append(fn)

        self._current_chunk_index = 0
        self._total_chunks = len(self._ps_file_list)

        # Запускаем первый чанк
        if self._ps_file_list:
            self._run_next_chunk(on_progress, on_complete, on_chunk_complete)

    def _run_next_chunk(
        self,
        on_progress: Optional[Callable[[int, int], None]],
        on_complete: Optional[Callable[[ResultSeries], None]],
        on_chunk_complete: Optional[Callable[[int, int], None]],
    ) -> None:
        """
        Запустить следующий чанк в очереди.

        Args:
            on_progress: Callback прогресса.
            on_complete: Callback завершения серии.
            on_chunk_complete: Callback завершения чанка.
        """
        if self._current_chunk_index >= len(self._ps_file_list):
            # Все чанки обработаны
            self.logger.info(f"Асинхронная серия завершена. Результатов: {len(self.series)}")
            if on_complete:
                on_complete(self.series)
            return

        fn = self._ps_file_list[self._current_chunk_index]
        current = self._current_chunk_index + 1

        if on_progress:
            on_progress(current, self._total_chunks)

        def on_calc_complete(success: bool):
            self.root.after(
                0,
                lambda: self._on_chunk_complete(
                    success, fn, on_progress, on_complete, on_chunk_complete
                ),
            )

        self.runner.run(
            ps_file=fn,
            async_mode=True,
            hidden=True,
            on_complete=on_calc_complete,
        )

    def _on_chunk_complete(
        self,
        success: bool,
        fn: str,
        on_progress: Optional[Callable[[int, int], None]],
        on_complete: Optional[Callable[[ResultSeries], None]],
        on_chunk_complete: Optional[Callable[[int, int], None]],
    ) -> None:
        """
        Обработчик завершения чанка.

        Args:
            success: True если расчет успешен.
            fn: Имя файла расчета.
            on_progress: Callback прогресса.
            on_complete: Callback завершения серии.
            on_chunk_complete: Callback завершения чанка.
        """
        if success:
            # Загружаем результаты
            calculations = self._load_results_from_file(fn)
            chunk = self._chunks[self._current_chunk_index]

            for j, calc in enumerate(calculations):
                variant = chunk[j] if j < len(chunk) else chunk[-1]
                result = self._convert_to_result(calc, variant)
                self.series.add_result(result)

            if on_chunk_complete:
                on_chunk_complete(self._current_chunk_index + 1, len(calculations))

            self.logger.info(
                f"Чанк {self._current_chunk_index} завершен: "
                f"{len(calculations)} результатов"
            )
        else:
            self.logger.error(f"Ошибка расчета чанка {self._current_chunk_index}: {fn}")

        # Переходим к следующему чанку
        self._current_chunk_index += 1
        self._run_next_chunk(on_progress, on_complete, on_chunk_complete)

    def get_series(self) -> ResultSeries:
        """
        Получить текущую серию результатов.

        Returns:
            ResultSeries с накопленными результатами.
        """
        return self.series

    @classmethod
    def load_series_from_res_files(
        cls,
        res_files: list[str],
        params: Params | None = None,
        logger: logging.Logger | None = None,
        base_path: Path | None = None,
    ) -> ResultSeries:
        """
        Загрузить серию результатов из готовых .res файлов.

        Метод позволяет загрузить результаты из предварительно рассчитанных
        .res файлов, предоставленных пользователем.

        Args:
            res_files: Список путей к .res файлам.
            params: Параметры расчета (опционально).
            logger: Логгер для вывода сообщений.
            base_path: Базовый путь для определения work_dir.

        Returns:
            ResultSeries с загруженными результатами.
        """
        if logger is None:
            logger = logging.getLogger(__name__)

        series = ResultSeries(params=params)
        work_dir = base_path / "TERMO" if base_path else Path("TERMO")

        for res_path in res_files:
            try:
                # Если путь относительный, добавляем work_dir
                path = Path(res_path)
                if not path.is_absolute():
                    path = work_dir / res_path

                if not path.exists():
                    logger.warning(f"Файл не найден: {path}")
                    continue

                parser = ResParser(str(path))
                data = parser.parse()

                # Сохраняем метаданные серии из первого файла
                if not series.mixture_name and data.mixture_name:
                    series.mixture_name = data.mixture_name
                    series.mixture_density = data.mixture_density
                    series.element_composition = data.element_composition
                    series.components = data.components

                # Добавляем все расчеты из файла в серию
                for calc in data.calculations:
                    series.add_result(calc)

                logger.info(f"Загружено {len(data.calculations)} результатов из {path.name}")

            except Exception as e:
                logger.error(f"Ошибка загрузки из {res_path}: {e}")
                continue

        logger.info(f"Загружено всего результатов в серию: {len(series)}")
        return series

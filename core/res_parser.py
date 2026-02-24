#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер файлов .res (выходные файлы термохимической программы TERMPS)
Извлекает ВСЕ расчёты с полным равновесным составом
"""

import re
import os
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResComponent:
    """Компонент смеси из .res файла"""

    name: str
    hf298: float


@dataclass
class CalculationResult:
    """Результаты одного расчёта"""

    id: int
    composition_percent: list[float] = field(default_factory=list)
    pressure: float = 0.0
    temperature: float = 0.0
    enthalpy: float = 0.0
    entropy: float = 0.0
    heat_capacity: float = 0.0
    density: float = 0.0
    molar_mass: float = 0.0
    adiabatic_index: float = 0.0
    volume_gas: float = 0.0  # V гф - объём газовой фазы
    condensed_fraction: float = 0.0  # Z кф - доля конденсированных продуктов
    equilibrium_gas: dict = field(default_factory=dict)
    equilibrium_condensed: dict = field(default_factory=dict)
    calculation_date: str = ""
    calculation_time: str = ""


@dataclass
class ResData:
    """Данные из .res файла"""

    filename: str
    mixture_name: str = ""
    mixture_density: float = 0.0
    components: list[ResComponent] = field(default_factory=list)
    element_composition: dict = field(default_factory=dict)
    calculations: list[CalculationResult] = field(default_factory=list)


class ResParser:
    """Парсер файлов .res"""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.data = ResData(filename=self.filepath.name)

    def parse(self) -> ResData:
        """Основной метод парсинга"""
        with open(self.filepath, "r", encoding="cp866", errors="replace") as f:
            content = f.read()

        self._parse_header(content)
        self._parse_components(content)
        self._parse_element_composition(content)
        self._parse_all_calculations(content)

        return self.data

    def _parse_header(self, content: str):
        """Парсинг заголовка"""
        match = re.search(r"Давление в системе:\s*([\d.]+)", content)
        if match:
            self.data.mixture_density = float(match.group(1))

        lines = content.split("\n")
        for line in lines[:5]:
            stripped = line.strip()
            if stripped and len(stripped) > 3 and "Давление" not in stripped:
                self.data.mixture_name = stripped
                break

    def _parse_components(self, content: str):
        """Парсинг компонентов"""
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            hf_match = re.search(r"HF298\s+(-?[\d.]+)", line)
            if hf_match:
                hf298 = float(hf_match.group(1))
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    name_match = re.search(r"Формула\s+(\S+)", next_line)
                    if name_match:
                        name = re.sub(r"[^\w.-]", "", name_match.group(1).strip())
                        if re.search(r"[A-Z]", name, re.IGNORECASE):
                            self.data.components.append(
                                ResComponent(name=name, hf298=hf298)
                            )
            i += 1

    def _parse_element_composition(self, content: str):
        """Парсинг элементного состава"""
        pattern = re.compile(r"\[([A-Z][a-z]?)\s?\]\s+([\d.E+-]+)")
        for match in pattern.finditer(content):
            self.data.element_composition[match.group(1).strip()] = float(
                match.group(2)
            )

    def _parse_all_calculations(self, content: str):
        """Извлечение всех расчётов"""
        lines = content.split("\n")

        # Находим строки с параметрами: " P     1.0000E-01    T ..." или "|     P         1.0000E-01"
        calc_markers = []
        for i, line in enumerate(lines):
            # Формат 1: " P     1.0000E-01    T ..."
            if line.startswith(" P ") and "T" in line and "E+" in line:
                calc_markers.append(i)
            # Формат 2: "|     P         1.0000E-01" (внутри таблицы) - ищем первую строку P
            elif "|     P" in line and ("E-" in line or "E+" in line):
                # Проверяем, что это первая строка с P (не состав)
                if "T" in "".join(lines[max(0, i - 2) : i + 2]):  # Есть T поблизости
                    calc_markers.append(i)

        if not calc_markers:
            return  # Нет расчётов

        # Извлекаем каждый расчёт
        for idx, marker_idx in enumerate(calc_markers):
            # Берём строки от предыдущего маркера до следующего
            prev_idx = (
                calc_markers[idx - 1] + 20 if idx > 0 else max(0, marker_idx - 15)
            )
            next_idx = (
                calc_markers[idx + 1] if idx + 1 < len(calc_markers) else len(lines)
            )

            start_idx = max(prev_idx, marker_idx - 15)
            # Увеличиваем end_idx чтобы захватить секцию "Равновесный состав"
            end_idx = min(next_idx, marker_idx + 60)

            section_lines = lines[start_idx:end_idx]
            all_lines = lines

            # Находим смещение маркера в section_lines
            marker_offset = marker_idx - start_idx

            # Проверяем, что marker_offset в пределах section_lines
            if marker_offset >= len(section_lines):
                continue

            calc = self._parse_single_calculation(
                idx + 1, section_lines, all_lines, marker_offset
            )
            if calc:
                self.data.calculations.append(calc)

    def _parse_single_calculation(
        self, calc_id: int, section_lines: list, all_lines: list, marker_offset: int
    ) -> CalculationResult:
        """Парсинг одного расчёта"""
        calc = CalculationResult(id=calc_id)

        # Ищем процентный состав в строках перед маркером
        for i in range(min(marker_offset, len(section_lines))):
            line = section_lines[i]
            match = re.match(r"^\s*\d+\.\s+([\d.]+(?:\s+[\d.]+)+)", line)
            if match:
                calc.composition_percent = [float(x) for x in match.group(1).split()]
                break

        # Парсим термодинамические параметры из строки маркера и следующих
        for i in range(min(marker_offset + 30, len(section_lines))):
            line = section_lines[i]
            stripped = line.strip()

            # Строка параметров: P ... T ... I ... S ... (формат 1)
            if line.startswith(" P ") and "T" in line:
                # P
                match = re.search(r"P\s+([\d.E+-]+)", line)
                if match:
                    calc.pressure = float(match.group(1))

                # T - ищем T с последующим числом
                match = re.search(r"T\s+\S+\s*([\d.E+-]+)", line)
                if match:
                    try:
                        calc.temperature = float(match.group(1))
                    except ValueError:
                        pass

                # I - ищем I с последующим числом
                match = re.search(r"I\s+\S+\s*(-?[\d.E+-]+)", line)
                if match:
                    try:
                        calc.enthalpy = float(match.group(1))
                    except ValueError:
                        pass

                # S - ищем S с последующим числом
                match = re.search(r"S\s+\S+\s*([\d.E+-]+)", line)
                if match:
                    try:
                        calc.entropy = float(match.group(1))
                    except ValueError:
                        pass

                # C (теплоёмкость) - ищем в начале строки
                match = re.search(r"^C\s+\S+\s*([\d.E+-]+)", stripped)
                if match:
                    try:
                        val = float(match.group(1))
                        if 0.1 < val < 20:
                            calc.heat_capacity = val
                    except ValueError:
                        pass

                # R (плотность)
                match = re.search(r"R\s+\S+\s*([\d.E+-]+)", stripped)
                if match:
                    try:
                        val = float(match.group(1))
                        if val > 0.0001:
                            calc.density = val
                    except ValueError:
                        pass

                # M (молярная масса)
                match = re.search(r"M\s+\S+\s*([\d.E+-]+)", stripped)
                if match:
                    try:
                        val = float(match.group(1))
                        if val > 0.1:
                            calc.molar_mass = val
                    except ValueError:
                        pass

                # K (адиабата)
                match = re.search(r"K\s+\S+\s*([\d.E+-]+)", stripped)
                if match:
                    try:
                        val = float(match.group(1))
                        if val > 0.5:
                            calc.adiabatic_index = val
                    except ValueError:
                        pass
                break

            # Формат 2: "|     P         1.0000E-01" (внутри таблицы)
            if "|     P" in line:
                match = re.search(r"\|\s*P\s+([\d.E+-]+)", line)
                if match:
                    calc.pressure = float(match.group(1))

            if "|     T" in line:
                match = re.search(r"\|\s*T\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    calc.temperature = float(match.group(1))

            if "|     I" in line:
                match = re.search(r"\|\s*I\s+\S*\s*(-?[\d.E+-]+)", line)
                if match:
                    calc.enthalpy = float(match.group(1))

            if "|     S" in line:
                match = re.search(r"\|\s*S\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    calc.entropy = float(match.group(1))

            if "|     C" in line and not calc.heat_capacity:
                match = re.search(r"\|\s*C\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    val = float(match.group(1))
                    if 0.1 < val < 20:
                        calc.heat_capacity = val

            if "|     R" in line and not calc.density:
                match = re.search(r"\|\s*R\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    val = float(match.group(1))
                    if val > 0.0001:
                        calc.density = val

            if "|     M" in line and not calc.molar_mass:
                match = re.search(r"\|\s*M\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    val = float(match.group(1))
                    if val > 0.1:
                        calc.molar_mass = val

            if "|     K" in line and not calc.adiabatic_index:
                match = re.search(r"\|\s*K\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    val = float(match.group(1))
                    if val > 0.5:
                        calc.adiabatic_index = val

            if "|     V" in line and not calc.volume_gas:
                match = re.search(r"\|\s*V\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    calc.volume_gas = float(match.group(1))

            if "|     Z" in line and not calc.condensed_fraction:
                match = re.search(r"\|\s*Z\s+\S*\s*([\d.E+-]+)", line)
                if match:
                    calc.condensed_fraction = float(match.group(1))

        # Парсим равновесный состав (после строки с параметрами)
        # Ищем строки с компонентами после строки "Pавновесный состав" или пустой строки
        in_composition = False
        composition_start_found = False

        for i in range(marker_offset, len(section_lines)):
            line = section_lines[i]
            stripped = line.strip()

            # Начало секции состава - ищем "Mоль / K" или "/ K" с "M" в начале
            # В кодировке CP866 русские слова отображаются как кракозябры, но "Mоль / K" работает
            if "Mоль / K" in stripped or ("/ K" in stripped and "M" in stripped):
                composition_start_found = True
                continue

            # Если нашли начало секции состава
            if composition_start_found and not in_composition:
                # Проверяем, начинается ли строка с "|     X" где X - компонент
                # Учитываем пробелы перед |
                match = re.match(r"\s*\|\s*([A-Z][A-Za-z0-9]{1,3})\s+([\d.E+-]+)", line)
                if match:
                    in_composition = True
                    comp = match.group(1)
                    if len(comp) >= 2 and comp not in ["NC"]:
                        calc.equilibrium_gas[comp] = float(match.group(2))
                    continue

            if in_composition:
                # Конец секции - пустая строка или конец таблицы
                if stripped == "" and "|" not in line:
                    break
                if stripped.startswith("___"):
                    break

                # Конденсированные продукты: C*        2.2575E+00 или |     Al2O3*    2.8328E+00
                match = re.match(
                    r"\s*(?:\|\s*)?([A-Z][A-Za-z0-9]*)\*\s+([\d.E+-]+)", line
                )
                if match:
                    calc.equilibrium_condensed[match.group(1)] = float(match.group(2))
                    continue

                # Газовая фаза: формат "|     H         3.9021E+00"
                match = re.match(r"\s*\|\s*([A-Z][A-Za-z0-9]{1,3})\s+([\d.E+-]+)", line)
                if match:
                    comp = match.group(1)
                    if len(comp) >= 2 and comp not in ["NC"]:
                        calc.equilibrium_gas[comp] = float(match.group(2))
                    continue

                # Газовая фаза: обычный формат
                match = re.match(r"^([A-Z][A-Za-z0-9]{1,3})\s+([\d.E+-]+)", stripped)
                if match:
                    comp = match.group(1)
                    # Пропускаем однобуквенные и параметры
                    if len(comp) >= 2 and comp not in ["NC"]:
                        calc.equilibrium_gas[comp] = float(match.group(2))

        # Дата и время
        date_match = re.search(
            r"(\d{2}:\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{2})", "\n".join(all_lines)
        )
        if date_match:
            calc.calculation_time = date_match.group(1)
            calc.calculation_date = date_match.group(2)

        return calc


def parse_res_file(filepath: str) -> ResData:
    """Парсинг одного файла"""
    parser = ResParser(filepath)
    return parser.parse()


def parse_directory(directory: str, pattern: str = "*.res") -> list[ResData]:
    """Парсинг всех .res файлов в директории"""
    results = []
    dir_path = Path(directory)

    for filepath in dir_path.glob(pattern):
        try:
            data = parse_res_file(str(filepath))
            results.append(data)
        except Exception as e:
            print(f"Ошибка при парсинге {filepath}: {e}")

    return results


def print_structured_data(data: ResData):
    """Вывод структурированных данных"""
    print("=" * 70)
    print(f"File: {data.filename}")
    print("=" * 70)

    if data.mixture_name:
        print(f"Mixture: {data.mixture_name}")
    if data.mixture_density:
        print(f"Mixture density: {data.mixture_density}")

    if data.components:
        print("\nComponents:")
        for comp in data.components:
            print(f"  {comp.name}: HF298 = {comp.hf298}")

    if data.element_composition:
        print("\nElement composition:")
        for elem, value in data.element_composition.items():
            print(f"  [{elem}]: {value:.6e}")

    if data.calculations:
        print(f"\n{'=' * 70}")
        print(f"Number of calculations: {len(data.calculations)}")
        print(f"{'=' * 70}")

        for calc in data.calculations:
            print(f"\n--- Calculation #{calc.id} ---")

            if calc.composition_percent:
                print(f"  Composition (%): {calc.composition_percent}")

            # Термодинамические параметры
            print("  Thermodynamic parameters:")
            if calc.pressure:
                print(f"    Pressure (P):        {calc.pressure:.6e}")
            if calc.temperature:
                print(f"    Temperature (T):     {calc.temperature:.2f} K")
            if calc.enthalpy:
                print(f"    Enthalpy (I):        {calc.enthalpy:.2f}")
            if calc.entropy:
                print(f"    Entropy (S):         {calc.entropy:.4f}")
            if calc.heat_capacity:
                print(f"    Heat capacity (C):   {calc.heat_capacity:.4f}")
            if calc.density:
                print(f"    Density (R):         {calc.density:.4f}")
            if calc.molar_mass:
                print(f"    Molar mass (M):      {calc.molar_mass:.2f}")
            if calc.adiabatic_index:
                print(f"    Adiabatic index (K): {calc.adiabatic_index:.4f}")
            if calc.volume_gas:
                print(f"    Volume gas (V гф):     {calc.volume_gas:.4f}")
            if calc.condensed_fraction:
                print(f"    Condensed frac (Z кф): {calc.condensed_fraction:.4f}")

            # Равновесный состав газовой фазы
            if calc.equilibrium_gas:
                print(f"  Equilibrium gas ({len(calc.equilibrium_gas)} components):")
                sorted_gas = sorted(calc.equilibrium_gas.items(), key=lambda x: -x[1])[
                    :15
                ]
                for comp, value in sorted_gas:
                    print(f"    {comp}: {value:.6e}")
                if len(calc.equilibrium_gas) > 15:
                    print(f"    ... and {len(calc.equilibrium_gas) - 15} more")

            # Конденсированные продукты
            if calc.equilibrium_condensed:
                print("  Condensed products:")
                for comp, value in sorted(
                    calc.equilibrium_condensed.items(), key=lambda x: -x[1]
                ):
                    print(f"    {comp}*: {value:.6e}")

            if calc.calculation_date:
                print(f"  Date/Time: {calc.calculation_date} {calc.calculation_time}")

    print()


def export_to_json(data: ResData) -> dict:
    """Экспорт в JSON"""
    return {
        "filename": data.filename,
        "mixture_name": data.mixture_name,
        "mixture_density": data.mixture_density,
        "components": [{"name": c.name, "hf298": c.hf298} for c in data.components],
        "element_composition": data.element_composition,
        "calculations": [
            {
                "id": calc.id,
                "composition_percent": calc.composition_percent,
                "pressure": calc.pressure,
                "temperature": calc.temperature,
                "enthalpy": calc.enthalpy,
                "entropy": calc.entropy,
                "heat_capacity": calc.heat_capacity,
                "density": calc.density,
                "molar_mass": calc.molar_mass,
                "adiabatic_index": calc.adiabatic_index,
                "volume_gas": calc.volume_gas,
                "condensed_fraction": calc.condensed_fraction,
                "equilibrium_gas": calc.equilibrium_gas,
                "equilibrium_condensed": calc.equilibrium_condensed,
                "calculation_date": calc.calculation_date,
                "calculation_time": calc.calculation_time,
            }
            for calc in data.calculations
        ],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = sys.argv[1]
        output_format = sys.argv[2] if len(sys.argv) > 2 else "text"

        if os.path.isdir(path):
            results = parse_directory(path)
        else:
            results = [parse_res_file(path)]

        if output_format == "json":
            output = [export_to_json(data) for data in results]
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            for data in results:
                print_structured_data(data)
    else:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        results = parse_directory(current_dir)
        print(f"Found {len(results)} .res files\n")
        for data in results:
            print_structured_data(data)

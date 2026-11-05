#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер файлов .res (выходные файлы термохимической программы TERMPS/TERM94).

Извлекает все расчёты с полным равновесным составом.
Поддерживает как одиночные значения, так и множественные (N точек).
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

from models.res_component import ResComponent, ResData
from models.results import Result

logger = logging.getLogger(__name__)

# Константы для парсинга
CALCULATION_CONTEXT_LINES_BEFORE = 15
CALCULATION_CONTEXT_LINES_AFTER = 60
MAX_GAS_COMPONENTS_DISPLAY = 30
MAX_GAS_COMPONENTS_DETAILED = 15

# Паттерн для извлечения всех чисел в научной нотации из строки
NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?")

def _extract_numbers(text: str) -> list[float]:
    """Извлечь все числа в научной нотации из строки."""
    return [float(m) for m in NUMBER_PATTERN.findall(text)]

# Универсальный паттерн для строк термодинамических параметров.
# Группа 1: буква параметра (P, T, I, S, C, R, M, K, V, Z)
# Группа 2: необязательный суффикс (см, гф, кф)
# Группа 3: остаток строки, содержащий числа
PARAM_PATTERN = re.compile(r"^\s*\|?\s*([PTISCRMKVZ])\s+(?:([а-яА-Яa-zA-Z*]+)\s+)?(.*)")

# Паттерн для компонентов равновесного состава
# Группа 1: имя компонента (начинается с большой буквы, может содержать цифры и *)
# Группа 2: остаток строки с числами
COMP_PATTERN = re.compile(r"^\s*\|?\s*([A-Z][A-Za-z0-9*]*)\s+(.*)")


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
            # Примечание: в оригинале это присваивалось mixture_density, 
            # оставляем как есть для совместимости, но имейте в виду.
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

        # Находим маркеры начала расчёта (строки с параметрами)
        calc_markers = []
        for i, line in enumerate(lines):
            # Ищем строку, которая начинается с P (с | или без) и содержит числа
            if PARAM_PATTERN.match(line):
                # Дополнительная проверка: это должна быть строка P, и рядом должна быть строка T
                if "P" in PARAM_PATTERN.match(line).group(1):
                    # Проверяем, есть ли T в соседних строках, чтобы убедиться, что это блок параметров
                    context = "\n".join(lines[max(0, i - 2) : i + 5])
                    if PARAM_PATTERN.search(context) and "T" in context:
                        calc_markers.append(i)

        if not calc_markers:
            return

        # Извлекаем каждый расчёт
        for idx, marker_idx in enumerate(calc_markers):
            prev_idx = (
                calc_markers[idx - 1] + 20
                if idx > 0
                else max(0, marker_idx - CALCULATION_CONTEXT_LINES_BEFORE)
            )
            next_idx = (
                calc_markers[idx + 1] if idx + 1 < len(calc_markers) else len(lines)
            )

            start_idx = max(prev_idx, marker_idx - CALCULATION_CONTEXT_LINES_BEFORE)
            end_idx = min(next_idx, marker_idx + CALCULATION_CONTEXT_LINES_AFTER)

            section_lines = lines[start_idx:end_idx]
            all_lines = lines

            marker_offset = marker_idx - start_idx

            if marker_offset >= len(section_lines):
                continue

            calc = self._parse_single_calculation(
                idx + 1, section_lines, all_lines, marker_offset
            )
            if calc:
                self.data.calculations.append(calc)

    def _parse_single_calculation(
        self, calc_id: int, section_lines: list, all_lines: list, marker_offset: int
    ) -> Result:
        """Парсинг одного расчёта"""
        # Все числовые поля инициализируются пустыми списками
        calc_data = {
            "id": calc_id,
            "composition_percent": [],
            "pressure": [],
            "temperature": [],
            "enthalpy": [],
            "entropy": [],
            "heat_capacity": [],
            "density": [],
            "molar_mass": [],
            "adiabatic_index": [],
            "volume_gas": [],
            "condensed_fraction": [],
            "equilibrium_gas": {},
            "equilibrium_condensed": {},
            "calculation_date": "",
            "calculation_time": "",
        }

        # 1. Ищем процентный состав в строках перед маркером
        for i in range(min(marker_offset, len(section_lines))):
            line = section_lines[i]
            match = re.match(r"^\s*\d+\.\s+([\d.]+(?:\s+[\d.]+)+)", line)
            if match:
                calc_data["composition_percent"] = [
                    float(x) for x in match.group(1).split()
                ]
                break

        # 2. Парсим термодинамические параметры с помощью универсального паттерна
        for i in range(min(marker_offset + 30, len(section_lines))):
            line = section_lines[i]
            match = PARAM_PATTERN.match(line)
            if not match:
                continue

            param = match.group(1)
            suffix = (match.group(2) or "").lower()
            rest = match.group(3)
            
            values = _extract_numbers(rest)
            if not values:
                continue

            # Маппинг параметров с учетом суффиксов для однозначности
            if param == "P":
                calc_data["pressure"] = values
            elif param == "T" and "см" in suffix:
                calc_data["temperature"] = values
            elif param == "I" and "см" in suffix:
                calc_data["enthalpy"] = values
            elif param == "S" and "см" in suffix:
                calc_data["entropy"] = values
            elif param == "C" and "см" in suffix:
                if all(0.1 < v < 20 for v in values):
                    calc_data["heat_capacity"] = values
            elif param == "R" and "см" in suffix:
                if all(v > 0.0001 for v in values):
                    calc_data["density"] = values
            elif param == "M" and "см" in suffix:
                if all(v > 0.1 for v in values):
                    calc_data["molar_mass"] = values
            elif param == "K" and "см" in suffix:
                if all(v > 0.5 for v in values):
                    calc_data["adiabatic_index"] = values
            elif param == "V" and "гф" in suffix:
                calc_data["volume_gas"] = values
            elif param == "Z" and "кф" in suffix:
                calc_data["condensed_fraction"] = values

        # 3. Парсим равновесный состав
        in_composition = False
        composition_start_found = False

        for i in range(marker_offset, len(section_lines)):
            line = section_lines[i]
            stripped = line.strip()

            if "Mоль / K" in stripped or ("/ K" in stripped and "M" in stripped):
                composition_start_found = True
                continue

            if composition_start_found and not in_composition:
                match = COMP_PATTERN.match(line)
                if match:
                    in_composition = True
                    comp = match.group(1)
                    rest = match.group(2)
                    values = _extract_numbers(rest)
                    if len(comp) >= 2 and comp not in ["NC"]:
                        calc_data["equilibrium_gas"][comp] = values
                    continue

            if in_composition:
                if stripped == "" and "|" not in line:
                    break
                if stripped.startswith("___") or stripped.startswith("---"):
                    break

                match = COMP_PATTERN.match(line)
                if match:
                    comp = match.group(1)
                    rest = match.group(2)
                    values = _extract_numbers(rest)
                    
                    # Конденсированные продукты отмечены звездочкой
                    if comp.endswith("*"):
                        calc_data["equilibrium_condensed"][comp.rstrip("*")] = values
                    else:
                        if len(comp) >= 2 and comp not in ["NC"]:
                            calc_data["equilibrium_gas"][comp] = values
                    continue

        # 4. Дата и время (поиск по всему файлу для надежности)
        date_match = re.search(
            r"(\d{2}:\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{2})", "\n".join(all_lines)
        )
        if date_match:
            calc_data["calculation_time"] = date_match.group(1)
            calc_data["calculation_date"] = date_match.group(2)

        return Result(**calc_data)


def parse_res_file(filepath: str) -> ResData:
    """Парсинг одного файла"""
    parser = ResParser(filepath)
    return parser.parse()


def parse_directory(directory: str, pattern: str = "*.res") -> List[ResData]:
    """Парсинг всех .res файлов в директории."""
    results: List[ResData] = []
    dir_path = Path(directory)

    for filepath in dir_path.glob(pattern):
        try:
            data = parse_res_file(str(filepath))
            results.append(data)
        except Exception as e:
            logger.error(f"Ошибка при парсинге {filepath}: {e}")

    return results


def print_structured_data(data: ResData) -> None:
    """Вывод структурированных данных в консоль."""
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

            print("  Thermodynamic parameters:")
            if calc.pressure:
                print(f"    Pressure (P):        {calc.pressure}")
            if calc.temperature:
                print(f"    Temperature (T):     {calc.temperature}")
            if calc.enthalpy:
                print(f"    Enthalpy (I):        {calc.enthalpy}")
            if calc.entropy:
                print(f"    Entropy (S):         {calc.entropy}")
            if calc.heat_capacity:
                print(f"    Heat capacity (C):   {calc.heat_capacity}")
            if calc.density:
                print(f"    Density (R):         {calc.density}")
            if calc.molar_mass:
                print(f"    Molar mass (M):      {calc.molar_mass}")
            if calc.adiabatic_index:
                print(f"    Adiabatic index (K): {calc.adiabatic_index}")
            if calc.volume_gas:
                print(f"    Volume gas (V гф):     {calc.volume_gas}")
            if calc.condensed_fraction:
                print(f"    Condensed frac (Z кф): {calc.condensed_fraction}")

            if calc.equilibrium_gas:
                print(f"  Equilibrium gas ({len(calc.equilibrium_gas)} components):")
                sorted_gas = sorted(
                    calc.equilibrium_gas.items(), key=lambda x: -x[1][0] if x[1] else 0
                )[:MAX_GAS_COMPONENTS_DETAILED]
                for comp, values in sorted_gas:
                    print(f"    {comp}: {values}")
                if len(calc.equilibrium_gas) > MAX_GAS_COMPONENTS_DETAILED:
                    print(
                        f"    ... and {len(calc.equilibrium_gas) - MAX_GAS_COMPONENTS_DETAILED} more"
                    )

            if calc.equilibrium_condensed:
                print("  Condensed products:")
                for comp, values in sorted(
                    calc.equilibrium_condensed.items(),
                    key=lambda x: -x[1][0] if x[1] else 0,
                ):
                    print(f"    {comp}*: {values}")

            if calc.calculation_date:
                print(f"  Date/Time: {calc.calculation_date} {calc.calculation_time}")

    print()


def export_to_json(data: ResData) -> Dict:
    """Экспорт распарсенных данных в JSON-совместимый словарь."""
    return {
        "filename": data.filename,
        "mixture_name": data.mixture_name,
        "mixture_density": data.mixture_density,
        "components": [{"name": c.name, "hf298": c.hf298} for c in data.components],
        "element_composition": data.element_composition,
        "calculations": [calc.to_dict() for calc in data.calculations],
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
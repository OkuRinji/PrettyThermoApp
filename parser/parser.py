import struct
import json


def parse_comp_ps(file_path):
    """
    Парсинг бинарного файла COMP.PS (формат Fortran).
    
    Структура записи (372 байта):
    - 4 байта: ID (int32)
    - 124 байта: название вещества (CP866)
    - 128 байт: формула
    - 16 байт: зарезервировано
    - 4 байта: enthalpy (float32) по смещению 0x114 = 276
    - 88 байт: завершение
    """
    records = []
    record_size = 372  # Размер одной записи
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    num_records = len(data) // record_size
    
    for i in range(num_records):
        offset = i * record_size
        
        # Читаем ID (4 байта по смещению 0)
        rec_id = struct.unpack('<i', data[offset:offset + 4])[0]
        
        # Пропускаем записи с ID=0
        if rec_id == 0:
            continue
        
        # Читаем название (124 байта по смещению 4)
        name_bytes = data[offset + 4:offset + 128]
        name = name_bytes.decode('cp866', errors='ignore').strip()
        name = ''.join(c for c in name if ord(c) >= 32).strip()
        
        # Читаем формулу (128 байт по смещению 128)
        formula_bytes = data[offset + 128:offset + 256]
        formula = formula_bytes.decode('cp866', errors='ignore').strip()
        formula = ''.join(c for c in formula if ord(c) >= 32).strip()
        
        # Читаем enthalpy (4 байта float32 по смещению 0x114 = 276)
        enthalpy_offset = offset + 0x114
        enthalpy = struct.unpack('<f', data[enthalpy_offset:enthalpy_offset + 4])[0]
        
        # Пропускаем пустые записи
        if name or formula:
            record = {
                "id": rec_id,
                "name": name,
                "formula": formula,
                "enthalpy": round(enthalpy, 2)
            }
            records.append(record)
    
    return records


def main():
    import os
    from pathlib import Path
    base_dir = Path(__file__).parent if '__file__' in globals() else Path.cwd()
    input_file = base_dir / "COMP.PS"
    output_file = base_dir / "output.json"
    
    records = parse_comp_ps(str(input_file))
    
    with open(str(output_file), 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"Спарсено {len(records)} записей")
    print(f"Результат сохранён в {output_file}")
    
    # Показать первые 5 и последние 5 записей для проверки
    print("\nПервые 5 записей:")
    for rec in records[:5]:
        print(f"  {rec['id']}: {rec['name']} | {rec['enthalpy']}")
    
    print("\nПоследние 5 записей:")
    for rec in records[-5:]:
        print(f"  {rec['id']}: {rec['name']} | {rec['enthalpy']}")


if __name__ == "__main__":
    main()

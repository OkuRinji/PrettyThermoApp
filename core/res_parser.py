# core/res_parser.py
import re
import os

class RESParser:
    def __init__(self, work_dir):
        self.work_dir = work_dir
    
    def parse(self, filename='input.res'):
        """
        Читает файл результатов и возвращает структурированные данные
        """
        filepath = os.path.join(self.work_dir, filename)
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='cp866') as f:
            content = f.read()
        
        results = {
            'header': '',
            'tables': [],
            'raw': content
        }
        
        # Пример парсинга таблицы результатов (нужно адаптировать под реальный формат)
        # Ищем числовые строки с характеристиками (давление, температура и т.д.)
        number_pattern = r'[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?'
        
        lines = content.split('\n')
        current_table = []
        
        for line in lines:
            # Пропускаем пустые строки
            if not line.strip():
                if current_table:
                    results['tables'].append(current_table)
                    current_table = []
                continue
            
            # Пытаемся извлечь числа из строки
            numbers = re.findall(number_pattern, line)
            if numbers:
                current_table.append([float(n) for n in numbers])
        
        return results
    
    # def to_excel(self, results, output_path='results.xlsx'):
    #     """
    #     Экспорт результатов в Excel (требуется библиотека openpyxl)
    #     """
    #     try:
    #         from openpyxl import Workbook
    #         wb = Workbook()
    #         ws = wb.active
    #         ws.title = "Результаты"
            
    #         for i, table in enumerate(results['tables']):
    #             for row_idx, row in enumerate(table, start=1):
    #                 for col_idx, value in enumerate(row, start=1):
    #                     ws.cell(row=row_idx, column=col_idx, value=value)
            
    #         wb.save(os.path.join(self.work_dir, output_path))
    #         return True
    #     except ImportError:
    #         print("Установите openpyxl: pip install openpyxl")
    #         return False
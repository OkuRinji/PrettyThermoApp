import json
import os
from typing import Dict,List,Optional
from core.component import Component

class CatalogManager:
    "Менджер каталога (синглтон)"

    _instanse= None
    _initialized=False

    def __new__(cls):
        if cls._instanse is None:
            cls._instanse=super().__new__(cls)
        return cls._instanse
    
    def __init__(self):
        if CatalogManager._initialized:
            return
        CatalogManager._initialized=True

        self.components:Dict[int,Component]={}
        self.name_index: Dict[str,int]={}

    def load_fromJson(self,filepath:str)->bool:
        "Загрузка каталога из json файла"
        if not os.path.exists(filepath):
            print(f"⚠ Файл каталога не найден: {filepath}")
            return False
        
        try :
            with open(filepath,"r",encoding="utf-8") as f:
                data=json.load(f)

            for item in data:
                comp=Component(
                    id=item["id"],
                    name=item["name"],
                    formula=item["formula"],
                    enthalpy=item["enthalpy"]
                )
                self.components[comp.id]=comp
                self.name_index[comp.name.lower()]=comp.id
            print(f"Загружен {len(self.components)} компонентов")
            return True
        except Exception as e :
            print(f"Ошибка загрузки каталога {e}")
            return False
    def search(self, query: str) -> List[Component]:
        """Поиск компонентов по названию или формуле"""
        query_lower = query.lower()
        results = []
        
        for comp in self.components.values():
            if (query_lower in comp.name.lower() or 
                query_lower in comp.formula.lower() or
                str(comp.id) == query):
                results.append(comp)
        
        return sorted(results, key=lambda x: x.id)
    
    def get_by_id(self, comp_id: int) -> Optional[Component]:
        """Получение компонента по ID"""
        return self.components.get(comp_id)
    
    def get_by_ids(self, ids: List[int]) -> List[Component]:
        """Получение нескольких компонентов по ID"""
        return [self.components[i] for i in ids if i in self.components]
    
    def get_all(self) -> List[Component]:
        """Получение всех компонентов (отсортировано по ID)"""
        return sorted(self.components.values(), key=lambda x: x.id)
    
    def get_categories(self) -> List[str]:
        """Получение списка категорий (по первым буквам названий)"""
        categories = set()
        for comp in self.components.values():
            # Первая буква или первые 2-3 символа
            cat = comp.name.split()[0][:3] if comp.name else "???"
            categories.add(cat)
        return sorted(categories)
    def get_count(self):
        return len(self.components)
    
a=CatalogManager()

a.load_fromJson("core/components_clean.json")
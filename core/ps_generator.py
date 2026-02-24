# core/ps_generator.py
import os


class PSGenerator:
    def __init__(self, work_dir):
        self.work_dir = work_dir

    def generate(self, params, filename="input.ps"):
        """
        Генерирует файл .PS для TERMO94 по реальным примерам
        """
        filepath = os.path.join(self.work_dir, filename)

        with open(filepath, "w", encoding="cp866", newline="\r\n") as f:
            # 1. Метаданные (строка ~60 символов)
            author = params.get("author", "Калмыков")
            code = params.get("code", "*")
            meta = f"Исполнитель : * {author:<10} *   Шифр {code:<10}   *\n"
            f.write(meta)

            # 2. Блок директив NAMELIST RRP
            f.write(self._build_rrp_block(params.get("directives", {})))

            # 3. Параметры процесса (PK, PC, AL, TP и т.д.)
            for param in ["PK", "PC", "AL", "VK", "PH", "OP", "OF", "TP"]:
                if param in params and params[param] is not None:
                    f.write(f"{param}={params[param]}\n")

            # 4. Рецептура (N вариантов, NB компонентов)
            f.write(f"N={params['N']}  NB={params['NB']}\n")

            # 5. Варианты и концентрации
            for variant in params["variants"]:
                concentrations = ",".join(
                    [self._format_conc(x) for x in variant["concentrations"]]
                )
                f.write(f"{variant['id']},{concentrations}\n")

            # 6. Компоненты (9 символов энтальпия + формула)
            for comp in params["components"]:
                # Энтальпия: 9 символов, выровнено по правому краю
                enthalpy_str = f"{comp['enthalpy']:>9.2f}"
                formula_str = comp["formula"]
                f.write(f"{enthalpy_str}{formula_str}\n")
            # 7. Участие внешенго окислителя
            if params["AL"] and params["AL"] != 0:
                f.write(f"N={params['AL_N']}  NB={params['AL_NB']}\n")
                for variant in params["AL_variants"]:
                    concentrations = ",".join(
                        [self._format_conc(x) for x in variant["concentrations"]]
                    )
                    f.write(f"{variant['id']},{concentrations}\n")
                for comp in params["outer_oxy"]:
                    # Энтальпия: 9 символов, выровнено по правому краю
                    enthalpy_str = f"{comp['enthalpy']:>9.2f}"
                    formula_str = comp["formula"]
                    f.write(f"{enthalpy_str}{formula_str}\n")

        # 'outer_oxy':{
        #             'id': 603,
        #             'formula': "N 54.8972O 14.4375"                                                    ,
        #             'enthalpy': 0.00}
        return filepath

    def _build_rrp_block(self, directives):
        """
        Формирует строку &RRP ... /&END
        Директивы могут быть разбиты на несколько строк
        """
        parts = []
        line = " &RRP "

        for key, value in directives.items():
            if isinstance(value, bool):
                parts.append(f"{key}={'T' if value else 'F'}")
            else:
                parts.append(f"{key}={value}")

        # Формируем строку с директивами (можно разбить на несколько строк)
        directive_line = line + ",".join(parts) + " /&END\n"
        return directive_line

    def _format_conc(self, value):
        """
        Форматирует концентрацию как в примерах (50., 66.7, 10.4)
        """
        if value == int(value):
            return f"{int(value)}."
        else:
            # Убираем лишние нули после запятой
            return (
                f"{value:.1f}".rstrip("0").rstrip(".") + "."
                if "." in f"{value:.1f}"
                else f"{value:.1f}"
            )


params1 = {
    "author": "Калмыков",
    "directives": {"LNN": True, "TABL": True},
    "PK": 0.1,
    "AL": 0.2,
    "N": 1,
    "NB": 2,
    "AL_N": 1,
    "AL_NB": 1,
    "variants": [{"id": 1, "concentrations": [50.0, 50.0]}],
    "AL_variants": [{"id": 1, "concentrations": [100.0]}],
    "components": [
        {"enthalpy": -2463.27, "formula": "N H 4.CLO 4."},
        {"enthalpy": 0.00, "formula": "AL18.53MG20.57"},
    ],
    "outer_oxy": [{"id": 603, "formula": "N 54.8972O 14.4375", "enthalpy": 0.00}],
}
# a=PSGenerator(r"c:\THERMO")
# a.generate(params1,"Rnd.ps")

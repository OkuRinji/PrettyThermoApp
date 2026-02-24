# core/runner.py
import subprocess


class DOSBoxRunner:
    def __init__(self, dosbox_path, work_dir):
        self.dosbox_path = dosbox_path
        self.work_dir = work_dir

    def run(self, exe_name="TERM94.EXE"):
        """
        Запускает расчет через DOSBox
        """
        commands = [
            self.dosbox_path,
            "-c",
            f"mount c {self.work_dir}",
            "-c",
            "c:",
            "-c",
            f"{exe_name}",
            "-c",
            "exit",
        ]

        try:
            # Запуск в фоновом режиме (без ожидания окна)
            subprocess.run(commands, cwd=self.work_dir)
            return True
        except Exception as e:
            print(f"Ошибка запуска DOSBox: {e}")
            return False

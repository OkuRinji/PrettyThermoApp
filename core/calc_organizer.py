from core.runner import OTVDMMRunner
from models.results import ResultSeries,Result
from models.res_component import ResData

class Calculator:
    def __init__(self,runner,series):
        self.runner= runner
        self.series=series

    
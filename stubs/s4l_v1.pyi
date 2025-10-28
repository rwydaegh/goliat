from typing import Any

class analysis:
    class Extractor:
        def __getitem__(self, key: str) -> Any: ...
        @property
        def FrequencySettings(self) -> Any: ...
        @property
        def Outputs(self) -> Any: ...

    @staticmethod
    def GetResult(entity_path: str, result_type: str) -> Any: ...

    em_evaluators: Any

class document:
    @staticmethod
    def IsOpen(project_path: str) -> bool: ...
    @staticmethod
    def AllEntities() -> list[Any]: ...
    @staticmethod
    def GetEntity(name: str) -> Any: ...
    @staticmethod
    def AllSimulations() -> list[Any]: ...
    @staticmethod
    def Close() -> None: ...
    @staticmethod
    def New() -> None: ...
    @staticmethod
    def SaveAs(path: str) -> None: ...

class materials:
    database: Any

simulation: Any
model: Any
units: Any
data: Any

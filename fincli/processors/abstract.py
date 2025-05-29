from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import BaseModel

class AbstractProcessor(ABC):
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    @abstractmethod
    def process(self, data: BaseModel) -> BaseModel: ...




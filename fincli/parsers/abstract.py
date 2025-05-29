from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type
from pydantic import BaseModel
import pandas as pd


class AbstractParser(ABC):
    """A data-source adapter."""

    config_model: Type[BaseModel]

    def __init__(self, config: BaseModel):
        self.config = config

    @abstractmethod
    def load(self) -> pd.DataFrame:
        """Return a typed dataframe ready for downstream processors."""
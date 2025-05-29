from __future__ import annotations
from abc import ABC, abstractmethod
from pydantic import BaseModel


class AbstractOutputPipe(ABC):
    """Something that turns processor results into a deliverable."""

    @abstractmethod
    def render(self, *results: BaseModel) -> str: ...

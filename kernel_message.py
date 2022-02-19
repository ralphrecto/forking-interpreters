from dataclasses import dataclass
from abc import ABC, abstractmethod

class KernelMessage(ABC):
    """Messages from the Driver to the Kernel."""

    @property
    @abstractmethod
    def has_response(self) -> bool:
        raise NotImplementedError

@dataclass
class CellInput(KernelMessage):
    """Execute a new cell of input."""
    cell: str

    def has_response(self):
        return False

class Checkpoint(KernelMessage):
    """Checkpoint the kernel."""

    def has_response(self):
        return True

class Shutdown(KernelMessage):
    """Shutdown the Kernel receiving this message."""

    def has_response(self):
        return True

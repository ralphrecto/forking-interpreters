from dataclasses import dataclass
from abc import ABC, abstractmethod

class KernelMessage(ABC):
    """Messages from the Driver to the Kernel."""

@dataclass
class CellInput(KernelMessage):
    """Execute a new cell of input."""
    cell: str

class Checkpoint(KernelMessage):
    """Checkpoint the kernel."""
    pass

class Shutdown(KernelMessage):
    """Shutdown the Kernel receiving this message."""
    pass

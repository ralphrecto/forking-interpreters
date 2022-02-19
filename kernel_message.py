from dataclasses import dataclass
from abc import ABC

class KernelMessage(ABC):
    """Messages from the Driver to the Kernel."""
    pass

class CellInput(KernelMessage):
    """Execute a new cell of input."""
    pass

class Checkpoint(KernelMessage):
    """Checkpoint the kernel."""
    pass

class Shutdown(KernelMessage):
    """Shutdown the Kernel receiving this message."""
    pass

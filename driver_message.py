from dataclasses import dataclass
from abc import ABC

class DriverMessage(ABC):
    pass

@dataclass
class CheckpointCreated(DriverMessage):
    """Message indicating a checkpoint was successfully created."""

    # Pid of the newly created checkpoint process.
    checkpoint_pid: int

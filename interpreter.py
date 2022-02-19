from multiprocessing import Process, Pipe
import signal
import os
import sys
import psutil
from typing import Optional
from dataclasses import dataclass
from enum import Enum

def signal_handler(signal_number, frame):
    pass

def spawn_new_kernel(driver_pid: int, driver_pipe: Pipe):
    kernel = Kernel(driver_pid, driver_pipe)
    kernel.run()

def init_kernel() -> KernelClient:
    driver_pid = os.getpid()
    parent_pipe, child_pipe = Pipe()
    kernel_proc = Process(target=spawn_new_kernel, args=(driver_pid, child_pipe))

    return KernelClient(kernel_proc.pid, parent_pipe)

class KernelMessageType(Enum):
    # Execute a new cell of input.
    CELL_INPUT = 1
    # Checkpoint the kernel.
    CHECKPOINT = 2
    # Shutdown the Kernel receiving this message.
    SHUTDOWN = 3

@dataclass
class KernelMessage:
    """Messages from the Driver to the Kernel."""
    msg_type: KernelMessageType
    msg: Optional[str]

class DriverMessageType:
    # Output from executing an input cell.
    CELL_OUTPUT = 1

class DriverMessage:
    """Messages from the Kernel to the Driver."""
    msg_type: DriverMessageType
    msg: Optional[str]

class KernelClient:

    def __init__(self, kernel_pid: int, kernel_pipe: Pipe):
        self.kernel_pid = kernel_pid
        # Pipe to send messages to the Kernel process this Client is for
        self.kernel_pipe = kernel_pipe

class Kernel:

    def __init__(self, driver_pid: int, driver_pipe: Pipe):
        self.driver_pid = driver_pid
        self.driver_pipe = driver_pipe

        self.local_env = dict()
        self.global_env = dict()

        self.back = []

        self.checkpoint_pids = []

    def run():
        while True:
            msg: KernelMessage = self.driver_pipe.recv()
            if msg.msg_type == KernelMessageType.CELL_INPUT:
                # TODO
                pass
            elif msg.msg_type == KernelMessageType.CHECKPOINT:
                # TODO
                pass
            elif msg.msg_type == KernelMessageType.SHUTDOWN:
                # TODO
                pass
            else:
                raise ValueError(f"Fatal error: uknown KernelMessageType {msg.msg_type}")

    def checkpoint(self):
        current_pid = os.getpid()
        pid = os.fork()
        if pid == 0:
            # child logic

            parent_proc = psutil.Process(current_pid)

            signal.signal(signal.SIGCONT, signal_handler)
            signal.pause()

            # Terminate parent.
            # parent_proc.terminate()
        else:
            # parent logic

            self.checkpoint_pids.append(pid)

    def restore_checkpoint(self, checkpoint_pid):
        checkpoint_proc = psutil.Process(checkpoint_pid)
        checkpoint_proc.resume()
        sys.exit(0)

    def next(self, cell: str):
        self.back.append(cell)

        # TODO double check these exec() params
        # TODO we need to route the Kernel proc's stdout/stderr *back*
        # to the Driver proc, or at least stdout/stderr generated
        # by this exec.
        exec(cell, self.global_env, self.local_env)

    def undo(self):
        checkpoint_pid = self.checkpoint_pids.pop()
        self.restore_checkpoint(checkpoint_pid)

        self.back.pop()

class Driver:

    def __init__(self):
        # Start up kernel child process
        kernel = Kernel()

        # Listen for user input

def main():
    kernel = Kernel()

    kernel.next("x = 1")
    kernel.next("print(x)")
    kernel.next("x += 1")
    kernel.next("print(x)")

    kernel.undo()
    kernel.undo()

    kernel.next("print(x)")

if __name__ == "__main__":
    main()

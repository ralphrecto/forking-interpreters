from multiprocessing import Process, Pipe
import signal
import os
import sys
import psutil
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from abc import ABC
import driver_message
import kernel_message

def signal_handler(signal_number, frame):
    pass

class KernelClient:
    """Client to interact with a Kernel process."""

    def __init__(self, kernel_pid: int, kernel_pipe: Pipe):
        # Pid of the Kernel
        self.kernel_pid = kernel_pid
        # Pipe to communicate with the Kernel
        self.kernel_pipe = kernel_pipe

    def send_message(self, msg: kernel_message.KernelMessage) -> Optional[driver_message.DriverMessage]:
        self.kernel_pipe.send(msg)
        if msg.has_response():
            return self.kernel_pipe.recv()

class Kernel:
    """Kernel that executes Python programs."""

    def __init__(self, driver_pid: int, driver_pipe: Pipe):
        self.pid = os.getpid()
        self.driver_pid = driver_pid
        self.driver_pipe = driver_pipe

        self.local_env = dict()
        self.global_env = dict()

        self.back = []

    def run(self):
        while True:
            msg: kernel_message.KernelMessage = self.driver_pipe.recv()
            if isinstance(msg, kernel_message.CellInput):
                self.next(msg.cell)
            elif isinstance(msg, kernel_message.Checkpoint):
                checkpoint_pid = self.checkpoint()
                if checkpoint_pid is None:
                    raise Error("Fatal error: could not get pid for checkpointed process")

                self.driver_pipe.send(
                    driver_message.CheckpointCreated(checkpoint_pid)
                )
            elif isinstance(msg, kernel_message.Shutdown):
                print(f"Kernel at pid {self.pid} shutting down.")
                sys.exit(0)
            else:
                raise ValueError(f"Fatal error: uknown KernelMessage {msg.__class__}")

    def checkpoint(self) -> Optional[int]:
        current_pid = os.getpid()
        pid = os.fork()
        if pid == 0:
            # child logic

            parent_proc = psutil.Process(current_pid)

            # The child process sleeps until it is restored.
            signal.signal(signal.SIGCONT, signal_handler)
            signal.pause()

            # TODO implement logic for checkpoint restoration
        else:
            # This proc is the parent.
            # We return the child pid
            return pid

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

def spawn_new_kernel(driver_pid: int, driver_pipe: Pipe):
    kernel = Kernel(driver_pid, driver_pipe)
    kernel.run()

class Driver:

    def __init__(self):
        self.pid = os.getpid()
        self.checkpoint_pids = []

        # Start up kernel child process
        parent_pipe, child_pipe = Pipe()
        kernel_proc = Process(target=spawn_new_kernel, args=(self.pid, child_pipe))
        kernel_proc.start()

        self.kernel_client = KernelClient(kernel_proc.pid, parent_pipe)

    def exec_cell(self, cell: str) -> None:
        retmsg = self.kernel_client.send_message(kernel_message.Checkpoint())
        self.checkpoint_pids.append(retmsg.checkpoint_pid)

        self.kernel_client.send_message(kernel_message.CellInput(cell))

    def shutdown(self):
        for checkpoint_pid in self.checkpoint_pids:
            # TODO is there a better way to do this?
            os.kill(checkpoint_pid, signal.SIGKILL)

        self.kernel_client.send_message(kernel_message.Shutdown())

def main():

    driver = Driver()

    driver.exec_cell("x = 1")
    driver.exec_cell("print(x)")
    driver.exec_cell("x += 1")
    driver.exec_cell("print(x)")

    driver.shutdown()

if __name__ == "__main__":
    main()

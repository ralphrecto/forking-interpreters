from multiprocessing import Process, Pipe
import signal
import os
import sys
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from abc import ABC
import driver_message
import kernel_message
import logging

def signal_handler(*args):
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
                    continue

                self.driver_pipe.send(
                    driver_message.CheckpointCreated(checkpoint_pid)
                )
            elif isinstance(msg, kernel_message.Shutdown):
                logging.debug(f"Kernel at pid {self.pid} shutting down.")
                self.driver_pipe.send(driver_message.ShutdownAck())
                sys.exit(0)
            else:
                raise ValueError(f"Fatal error: uknown KernelMessage {msg.__class__}")

    def checkpoint(self) -> Optional[int]:
        current_pid = os.getpid()
        pid = os.fork()
        if pid == 0:
            # This proc is the child.
            # The child process sleeps until it is restored.
            signal.signal(signal.SIGCONT, signal_handler)
            signal.pause()

            self.pid = os.getpid()

            logging.debug(f"Kernel with pid {self.pid} is restored")
            self.driver_pipe.send(driver_message.CheckpointRestored())
        else:
            # This proc is the parent.
            # We return the child pid.
            return pid

    def next(self, cell: str):
        self.back.append(cell)

        # TODO we need to route the Kernel proc's stdout/stderr *back*
        # to the Driver proc, or at least stdout/stderr generated
        # by this exec.
        exec(cell, self.global_env, self.local_env)

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
        # TODO implement checkpoint pruning

    def shutdown(self):
        for checkpoint_pid in self.checkpoint_pids:
            # TODO is there a better way to do this?
            os.kill(checkpoint_pid, signal.SIGKILL)

        self.kernel_client.send_message(kernel_message.Shutdown())

    def undo(self):
        if len(self.checkpoint_pids) == 0:
            raise Error("Nothing to undo.")

        checkpoint_pid = self.checkpoint_pids.pop()
        ack = self.kernel_client.send_message(kernel_message.Shutdown())
        self.kernel_client.kernel_pid = checkpoint_pid

        os.kill(checkpoint_pid, signal.SIGCONT)
        msg = self.kernel_client.kernel_pipe.recv()
        assert isinstance(msg, driver_message.CheckpointRestored)


def main():

    driver = Driver()

    driver.exec_cell("x = 1")
    driver.exec_cell("print(x)")
    driver.exec_cell("x += 1")
    driver.exec_cell("print(x)")

    driver.undo()
    driver.undo()

    driver.exec_cell("print(x)")

    driver.shutdown()

if __name__ == "__main__":
    main()

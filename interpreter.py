"""Implementation of a time-traveling Python interpreter.

Explicitly, this program provides a Driver, which lets users operate
the interpreter. The Driver provides two main functions:

    - exec_cell(cell): executes a cell of Python code.
    - undo(): time-travel back to the state of the interpreter
              before the execution of the last cell.

Each interpreter has one Driver process and one current Kernel process.
The Driver and the Kernel perform interprocess communication via Pipes.

Each time exec_cell() is called on the Driver, it first snapshots the
current Kernel process. This snapshot is achieved by calling fork() on
the Kernel process and immediately putting the child process to sleep
to wait for a SIGCONT signal. The pid of the child process is maintained
by the Driver in a buffer of snapshot pids. After the snapshot, the code
cell is executed in the current Kernel.

To restore a snapshot (i.e. when undo() is called):
    - the current Kernel is SIGKILLed,
    - SIGCONT is sent to the latest snapshot pid, and
    - the restored snapshot Kernel is treated as the new current Kernel.

At any time, only the current Kernel process will read from the Kernel
end of a Pipe that the Driver writes to (since all snapshots are asleep).
"""
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

# Special REPL token that tells the interpreter to undo the last command.
_UNDO_REPL_TOKEN = "!!"

class KernelClient:
    """Client to interact with a Kernel process."""

    def __init__(self, kernel_pid: int, kernel_pipe: Pipe):
        # Pid of the Kernel
        self.kernel_pid = kernel_pid
        # Pipe to communicate with the Kernel
        self.kernel_pipe = kernel_pipe

    def send_message(self, msg: kernel_message.KernelMessage) -> driver_message.DriverMessage:
        """Send a message to the Kernel."""
        self.kernel_pipe.send(msg)
        return self.kernel_pipe.recv()

class Kernel:
    """Maintains state generated by the execution of code cells."""

    def __init__(self, driver_pid: int, driver_pipe: Pipe):
        # Pid of the Kernel process
        self.pid = os.getpid()
        # Pid of the Driver communicating with this Kernel.
        self.driver_pid = driver_pid
        # Pipe to communicate with the Driver.
        self.driver_pipe = driver_pipe

        # Environment in which cells are executed. These environments maintain
        # any state that is generated by executing cells.
        self.local_env = dict()
        self.global_env = dict()

    def run(self):
        """Begin the Kernel's execution.

        The Kernel waits for messages from the Driver and reacts to them."""
        while True:
            msg: kernel_message.KernelMessage = self.driver_pipe.recv()
            if isinstance(msg, kernel_message.CellInput):
                self.next(msg.cell)
                self.driver_pipe.send(driver_message.Ack())
            elif isinstance(msg, kernel_message.Checkpoint):
                checkpoint_pid = self.checkpoint()
                if checkpoint_pid is None:
                    # This branch is taken by a restored snapshot Kernel.
                    continue

                self.driver_pipe.send(
                    driver_message.CheckpointCreated(checkpoint_pid)
                )
            elif isinstance(msg, kernel_message.Shutdown):
                logging.debug(f"Kernel at pid {self.pid} shutting down.")
                self.driver_pipe.send(driver_message.Ack())
                sys.exit(0)
            else:
                raise ValueError(f"Fatal error: uknown KernelMessage {msg.__class__}")

    def checkpoint(self) -> Optional[int]:
        """Checkpoint the current Kernel.

        The current Kernel process is forked. If the current process
        is the parent, the child pid is returned; otherwise, if it
        is the child, None is returned.
        """
        current_pid = os.getpid()
        pid = os.fork()
        if pid == 0:
            # This proc is the child.
            # The child process sleeps until it is restored.

            # TODO using signal.SIG_IGN / signal.SIG_DFL instead
            # of the no-op lambda doesn't work here. Why?
            signal.signal(signal.SIGCONT, lambda signum, stack: None)
            signal.pause()

            self.pid = os.getpid()

            logging.debug(f"Kernel with pid {self.pid} is restored")
            self.driver_pipe.send(driver_message.CheckpointRestored())
        else:
            # This proc is the parent.
            # We return the child pid.
            return pid

    def next(self, cell: str):
        """Execute the next cell of code in the Kernel."""
        # TODO add error handling when exec() throws an exception
        exec(cell, self.global_env, self.local_env)

def spawn_new_kernel(driver_pid: int, driver_pipe: Pipe):
    """Launch function for a new Kernel."""
    kernel = Kernel(driver_pid, driver_pipe)
    kernel.run()

class Driver:
    """Class for operating the interpreter."""

    def __init__(self):
        # The Driver process' pid.
        self.pid = os.getpid()
        # Pids of checkpointed Kernels.
        self.checkpoint_pids = []

        # Start up Kernel child process
        parent_pipe, child_pipe = Pipe()
        kernel_proc = Process(target=spawn_new_kernel, args=(self.pid, child_pipe))
        kernel_proc.start()

        # Client to the current Kernel.
        self.kernel_client = KernelClient(kernel_proc.pid, parent_pipe)

    def exec_cell(self, cell: str) -> None:
        """Execute the given cell in the current Kernel."""
        retmsg = self.kernel_client.send_message(kernel_message.Checkpoint())
        self.checkpoint_pids.append(retmsg.checkpoint_pid)

        self.kernel_client.send_message(kernel_message.CellInput(cell))
        # TODO implement checkpoint pruning

    def shutdown(self):
        """Shutdown the Driver and associated Kernels.

        The current Kernel and all sleeping snapshots are SIGKILLed."""
        for checkpoint_pid in self.checkpoint_pids:
            # TODO is there a better way to do this?
            os.kill(checkpoint_pid, signal.SIGKILL)

        self.kernel_client.send_message(kernel_message.Shutdown())

    def undo(self):
        """Undo the last operation made on the Kernel.

        Explicitly, this restores the last snapshot that was captured
        right before the execution of the latest cell of code."""
        if len(self.checkpoint_pids) == 0:
            raise Error("Nothing to undo.")

        checkpoint_pid = self.checkpoint_pids.pop()

        # Shutdown the current Kernel.
        ack = self.kernel_client.send_message(kernel_message.Shutdown())

        # Restore the snapshotted Kernel.
        self.kernel_client.kernel_pid = checkpoint_pid
        os.kill(checkpoint_pid, signal.SIGCONT)
        msg = self.kernel_client.kernel_pipe.recv()
        assert isinstance(msg, driver_message.CheckpointRestored)


def main():
    driver = Driver()
    signal.signal(signal.SIGTERM, lambda signum, stack: driver.shutdown())

    while True:
        cell = input(">> ").strip()

        if cell == _UNDO_REPL_TOKEN:
            driver.undo()
        else:
            driver.exec_cell(cell)

if __name__ == "__main__":
    main()

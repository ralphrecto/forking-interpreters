from multiprocessing import Process
import signal
import os
import psutil

def signal_handler(signal_number, frame):
    pass

class Kernel:

    def __init__(self):
        self.environment = dict()

        self.back = []
        self.front = []

        self.checkpoint_pids = []

    def checkpoint(self):
        current_pid = os.getpid()
        pid = os.fork()
        if pid == 0:
            # child logic

            parent_pid = current_pid

            signal.signal(signal.SIGCONT, signal_handler)
            signal.pause()

            # Terminate parent.
            signal.pidfd_send_signal(parent_pid, signal.SIGKILL)
        else:
            # parent logic

            self.checkpoint_pids.append(pid)


    def restore_checkpoint(self, checkpoint_pid):
        checkpoint_proc = psutil.Process(pid)
        signal.pidfd_send_signal(checkpoint_pid, signal.SIGCONT)
        checkpoint_proc.join()

    def new_cell(self, cell):
        self.back.append(cell)

        # TODO do something with result
        print("before")
        print(self.environment)

        self.checkpoint()
        result = eval(cell, self.environment)

        print("after")
        print(self.environment)

    def up(self):
        if len(self.back) > 0:
            self.front.append(self.back.pop())

    def down(self):
        self.back.append(self.front.pop())

    def undo(self):
        checkpoint_pid = self.checkpoint_pids.pop()
        self.restore(checkpoint_pid)

        self.back.pop()

def main():
    kernel = Kernel()



if __name__ == "__main__":
    main()

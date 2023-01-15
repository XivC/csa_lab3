from dataclasses import dataclass

from typing import List

from misc import Device
from misc import Number


class FileInputDevice(Device):
    def __init__(self):
        super().__init__()
        self.buffer: List[Number] = []
        self.pointer = 0
        self.load_buffer()

    def read(self) -> Number:
        if self.pointer >= len(self.buffer):
            return Number(self.bit_depth, 0)
        else:
            ret = self.buffer[self.pointer]
            self.pointer += 1
            return ret

    def write(self, n: Number) -> None:
        pass

    def load_buffer(self) -> None:
        try:
            f = open('in.txt')
            f.close()
        except FileNotFoundError:
            open('in.txt', 'w').close()  # create file if not exists

        with open('in.txt') as f:
            tokens = f.read()
            for token in tokens:
                self.buffer.append(Number(self.bit_depth, ord(token)))


class FileOutputDevice(Device):

    def __init__(self):
        super().__init__()

        with open('out.txt', 'w') as f:
            f.write('')  # clean file

    def read(self) -> Number:
        pass

    def write(self, n: Number) -> None:
        with open('out.txt', 'a') as f:
            f.write(chr(n.value))

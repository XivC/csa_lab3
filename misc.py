import abc
import math
from typing import Union


class Number:
    def __init__(self, bit_depth: int, value: int = None):

        assert bit_depth >= 1
        self._bit_depth: int = bit_depth
        self._value: int = 0
        if value:
            self.set_value(value)

    def set_value(self, value: Union[int, 'Number']) -> None:
        # Симулируется ограничение битности числа.
        # Если число - 16-битное, а мы пишем >16 бит, то то старшие разряды будут отброшены
        if type(value) == Number:
            value = value.value
        self._value = int(math.copysign(abs(value) & (2 ** self._bit_depth - 1), value))

    @property
    def value(self) -> int:
        return self._value

    @property
    def bit_depth(self):
        return self._bit_depth

    # при сложении или вычитании таких чисел битность результата = мин. битности слагаемых
    def __add__(self, n: 'Number') -> 'Number':
        return Number(min(self.bit_depth, n.bit_depth), value=self.value + n.value)

    def __sub__(self, n: 'Number') -> 'Number':
        return Number(min(self.bit_depth, n.bit_depth), value=self.value - n.value)

    def __int__(self):
        return self._value


class Register:

    def __init__(self, bit_depth: int):
        self._number: Number = Number(bit_depth)
        self._read_opened: bool = False
        self._write_opened: bool = False

    def read(self) -> Number:
        if self._read_opened:
            return self._number
        return Number(self._number.bit_depth)

    def write(self, n: Number) -> None:
        if self._write_opened:
            self._number.set_value(n)

    def open_read(self):
        self._read_opened = True

    def close_read(self):
        self._read_opened = False

    def open_write(self):
        self._write_opened = True

    def close_write(self):
        self._write_opened = False

    @property
    def value(self) -> Number:
        return self._number

    @property
    def bit_depth(self) -> int:
        return self._number.bit_depth


class Device(abc.ABC):
    bit_depth: int = 16

    @abc.abstractmethod
    def read(self) -> Number:
        pass

    @abc.abstractmethod
    def write(self, n: Number) -> None:
        pass




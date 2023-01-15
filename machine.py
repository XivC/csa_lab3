import typing
from typing import Optional

from typing import List

from device import FileInputDevice
from device import FileOutputDevice
from misc import Device
from misc import Number
from misc import Register


class InstructionError(RuntimeError):
    def __init__(self, instruction: dict, msg: str):
        super().__init__(f'Error in instruction {instruction}: {msg}')


class HaltedError(RuntimeError):
    pass


class InstructionsMemory:
    """
    Instruction format:
    {
        "operation": <op-code>,
        "fetch_type": "<const/rel/abs/acc>",
        "data": <number>,
    }
    const = data->data_reg
    const_rel (instr_pointer + data) -> data_reg
    abs_mem = mem(data)->data_reg
    rel_mem = mem(addr_reg+data) -> data_reg
    acc = acc->data_reg
    """

    def __init__(self, instr_pointer: Register, program: List[Optional[dict]] = None):
        self._instr_pointer: Register = instr_pointer
        if program:
            assert len(program) < 2 ** self._instr_pointer.bit_depth
            self._mem = program + [None for _ in range(2 ** self._instr_pointer.bit_depth - len(program))]
        else:
            self._mem: List[Optional[dict]] = [None for _ in range(2 ** self._instr_pointer.bit_depth)]

    def read(self) -> Optional[dict]:
        return self._mem[self._instr_pointer.read().value]


class DataMemory:

    def __init__(self, addr_reg: Register, data_reg: Register, devs: List[Device], data: List[Number] = None):
        self._addr_reg = addr_reg
        self._data_reg = data_reg
        self._devs = devs
        if data:
            assert len(data) < 2 ** self._addr_reg.bit_depth
            self._mem = data + [Number(self._data_reg.bit_depth) for _ in
                                range(2 ** self._addr_reg.bit_depth - len(data))]
        else:
            self._mem: List[Number] = [Number(self._data_reg.bit_depth) for _ in range(2 ** self._addr_reg.bit_depth)]

    def read(self) -> None:
        addr: Number = self._addr_reg.read()
        if addr.value < 0:
            raise RuntimeError(f'Invalid address ({addr.value}) in address register')

        if int(addr) < 4:
            read = self._read_from_device(addr)
            self._mem[int(addr)] = read

        read = self._mem[int(addr)]

        self._data_reg.write(read)

    def _read_from_device(self, addr: Number) -> Number:
        return self._devs[int(addr)].read()

    def write(self) -> None:
        addr: Number = self._addr_reg.read()
        if addr.value < 0:
            raise RuntimeError(f'Invalid address ({addr.value}) in address register')

        to_write = Number(self._data_reg.bit_depth, self._data_reg.read().value)
        if int(addr) < 4:
            self._write_to_device(addr, to_write)

        self._mem[int(addr)] = to_write

    def _write_to_device(self, addr: Number, to_write: Number) -> None:
        self._devs[int(addr)].write(to_write)


class ALU:
    bit_depth = 16

    def __init__(self, acc: Register, addr_reg: Register, data_reg: Register, instr_pointer: Register):
        self._acc: Register = acc
        self._addr_reg: Register = addr_reg
        self._data_reg: Register = data_reg
        self._instr_pointer: Register = instr_pointer

    def perform(self, signals: list) -> None:
        left: Number = Number(self.bit_depth, int(self._acc.read()) | int(self._instr_pointer.read()))
        right: Number = Number(self.bit_depth, int(self._data_reg.read()) | int(self._addr_reg.read()))
        res: Number = Number(self.bit_depth)
        if 'inc' in signals:
            res.set_value(res.value + 1)

        if 'inv_left' in signals:
            left.set_value(-int(left))

        if 'inv_right' in signals:
            right.set_value(-int(right))

        res.set_value(res + left + right)

        for reg in (self._acc, self._instr_pointer, self._addr_reg, self._data_reg):
            reg.write(res)


class ControlUnit:

    def __init__(self,
                 acc: Register,
                 addr_reg: Register,
                 data_reg: Register,
                 instr_pointer: Register,
                 instr_mem: InstructionsMemory,
                 data_mem: DataMemory,
                 alu: ALU,
                 ):
        self._acc = acc
        self._addr_reg = addr_reg
        self._data_reg = data_reg
        self._instr_pointer = instr_pointer
        self._instr_mem = instr_mem
        self._data_mem = data_mem
        self._alu = alu
        self.instruction: Optional[dict] = None
        self.lock_inc: bool = False
        self.halted = False

    def step(self) -> None:
        if self.halted:
            raise HaltedError()

        self.lock_inc = False
        self._fetch_instruction()
        self._perform()
        self._next()

    def _fetch_instruction(self):
        self._instr_pointer.open_read()
        self.instruction = self._instr_mem.read()
        self._instr_pointer.close_read()

    def _fetch_data(self):
        def _fetch_from_mem(rel=False):
            self._addr_reg.open_write()

            if not rel:
                addr = value
            else:
                addr = self._addr_reg.value + value

            self._addr_reg.write(addr)
            self._addr_reg.open_read()
            self._data_mem.read()
            self._addr_reg.close_read()

        value = Number(self._acc.bit_depth, self.instruction['data'])
        fetch_type = self.instruction['fetch_type']
        self._data_reg.open_write()

        if fetch_type == 'const':
            self._data_reg.write(value)
        elif fetch_type == 'const_rel':
            self._data_reg.write(self._instr_pointer.value + value)

        elif fetch_type == 'acc':
            self._acc.open_read()
            self._alu.perform([])
            self._acc.close_read()
        elif fetch_type == 'abs_mem':
            _fetch_from_mem()
        elif fetch_type == 'rel_mem':
            _fetch_from_mem(rel=True)
        else:
            raise InstructionError(self.instruction, 'invalid fetch_type')

        self._data_reg.close_write()

    def _perform(self):
        if not self.instruction:
            return

        {
            'INC': self._inc,
            'INV': self._inv,
            'ADD': self._add,
            'SUB': self._sub,
            'LD': self._ld,
            'SV': self._sv,
            'JMP': self._jmp,
            'JZ': self._jz,
            'JP': self._jp,
            'JN': self._jn,
            'HLT': self._halt,

        }.get(self.instruction['operation'], self._invalid_operation)()

    def _next(self):
        if not self.lock_inc:
            self._instr_pointer.open_read()
            self._instr_pointer.open_write()
            self._alu.perform(['inc'])
            self._instr_pointer.close_read()
            self._instr_pointer.close_write()

    def _invalid_operation(self):
        raise InstructionError(self.instruction, 'invalid operation code')

    def _inc(self):
        self._acc.open_read()
        self._acc.open_write()

        self._alu.perform(['inc'])

        self._acc.close_read()
        self._acc.close_write()

    def _inv(self):
        self._acc.open_read()
        self._acc.open_write()

        self._alu.perform(['inv_left'])

        self._acc.close_read()
        self._acc.close_write()

    def _add(self, inv=False):
        self._fetch_data()
        self._data_reg.open_read()
        self._acc.open_read()
        self._acc.open_write()

        signals = []
        if inv:
            signals += ['inv_right']

        self._alu.perform(signals)

        self._data_reg.close_read()
        self._acc.close_write()
        self._acc.close_read()

    def _sub(self):
        self._add(inv=True)

    def _data_reg_to_addr_reg(self):
        self._data_reg.open_read()
        self._addr_reg.open_write()
        self._alu.perform([])
        self._data_reg.close_read()
        self._addr_reg.close_write()

    def _ld(self):
        self._fetch_data()

        self._data_reg_to_addr_reg()

        # read
        self._addr_reg.open_read()
        self._data_reg.open_write()
        self._data_mem.read()
        self._addr_reg.close_read()
        self._data_reg.close_write()

        # data_reg -> acc

        self._data_reg.open_read()
        self._acc.open_write()
        self._alu.perform([])
        self._data_reg.close_read()
        self._acc.close_write()

    def _sv(self):
        self._fetch_data()

        self._data_reg_to_addr_reg()

        # acc -> data_reg
        self._acc.open_read()
        self._data_reg.open_write()
        self._alu.perform([])
        self._acc.close_read()
        self._data_reg.close_write()

        # write
        self._data_reg.open_read()
        self._addr_reg.open_read()
        self._data_mem.write()
        self._data_reg.close_read()
        self._addr_reg.close_read()

    def _jmp(self, ):
        self._fetch_data()
        self.lock_inc = True

        self._data_reg.open_read()
        self._instr_pointer.open_write()
        self._alu.perform([])
        self._data_reg.close_read()
        self._instr_pointer.close_write()

    def _jz(self):

        if self._acc.value.value == 0:
            self._jmp()

    def _jp(self):

        if self._acc.value.value > 0:
            self._jmp()

    def _jn(self):

        if self._acc.value.value < 0:
            self._jmp()

    def _halt(self):
        self.halted = True


class Machine:
    bit_depth = 16

    def __init__(self, initial: Optional[dict] = None):
        memory, program = self._parse_initial(initial)

        # Собираем машину
        self._acc: Register = Register(self.bit_depth)
        self._addr_reg: Register = Register(self.bit_depth)
        self._data_reg: Register = Register(self.bit_depth)
        self._instr_pointer: Register = Register(self.bit_depth)
        self._instr_mem: InstructionsMemory = InstructionsMemory(self._instr_pointer, program)

        self._data_mem: DataMemory = DataMemory(
            self._addr_reg,
            self._data_reg,
            [FileInputDevice(), FileOutputDevice()],
            data=memory,
        )
        self._alu: ALU = ALU(self._acc, self._addr_reg, self._data_reg, self._instr_pointer)
        self._control_unit: ControlUnit = ControlUnit(
            self._acc,
            self._addr_reg,
            self._data_reg,
            self._instr_pointer,
            self._instr_mem,
            self._data_mem,
            self._alu,
        )

    def _parse_initial(self, initial: dict) -> typing.Tuple[List[Number], List[dict]]:
        """
        format:
        {
        "data": [1,2,3,4,5,6...]
        "program": [{instr}, ...]
        }
        """
        data_raw = initial.get('data')
        data: List[Number] = []
        for token in data_raw:
            if type(token) != int:
                raise RuntimeError(f'Parsing error: token {token} should be int')
            data.append(Number(self.bit_depth, token))

        instructions: List[dict] = initial.get('program', [])

        return data, instructions

    def single_step(self) -> None:
        try:
            self._control_unit.step()
        except HaltedError:
            print('Machine halted')

    def run(self) -> None:
        while True:
            try:
                self._control_unit.step()
            except HaltedError:
                print('Machine halted')
                return

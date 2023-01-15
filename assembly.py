import json
import sys
from typing import List
from typing import Optional
from typing import Tuple


def split_strings(strings: List[str]) -> Tuple[List[str], List[str]]:
    data_strings = []
    program_strings = []
    skipped = []

    mode = None

    for string in strings:
        string = string.replace('\n', '')
        if len(string.strip()) == 0:
            continue
        if string == '.data':
            mode = 'data'
            continue
        elif string == '.text':
            mode = 'text'
            continue
        {
            'data': data_strings,
            'text': program_strings,
        }.get(mode, skipped).append(string)

    return data_strings, program_strings


def str_to_int(s: str) -> int:
    s = s.strip()
    try:
        value = int(s)
    except ValueError:
        try:
            value = ord(s)
        except TypeError:
            raise RuntimeError(f'Invalid value: {s}')

    return value


def parse_data(data_strings: List[str]) -> List[int]:
    """format: <cell_number>. value (char or int)"""
    cells = {}
    for string in data_strings:
        cell, value_raw = string.strip().split('.')
        try:
            cell = int(cell)
        except ValueError:
            raise RuntimeError(f'Invalid cell number. {cell} ')

        cells[cell] = str_to_int(value_raw)

    data = []
    for i in range(max(cells.keys()) + 1):
        data.append(cells.get(i) or 0)

    return data


def parse_program(program_strings: List[str]) -> List[Optional[dict]]:
    """
    format <cell_number>. <instr> <mode> <value>
    example: 1. LD abs 1
    """
    cells = {}
    for string in program_strings:
        cell, instr = string.strip().split('.')
        try:
            cell = int(cell)
        except ValueError:
            raise RuntimeError(f'Invalid cell number {cell} ')
        raw_instr = instr.strip().split(' ')
        if len(raw_instr) not in (1, 2, 3):
            raise RuntimeError(f'Invalid instruction {string}')

        if len(raw_instr) == 1:
            instruction = {'operation': raw_instr[0]}
        else:

            instruction = {
                'operation': raw_instr[0],
                'fetch_type': raw_instr[1],
                'data': str_to_int(raw_instr[2] if len(raw_instr) == 3 else '0')
            }
        cells[cell] = instruction

    instructions = []
    for i in range(max(cells.keys()) + 1):
        instructions.append(cells.get(i) or None)

    return instructions


def parse(text: List[str]) -> dict:
    data_strings, program_strings = split_strings(text)
    data, instructions = parse_data(data_strings), parse_program(program_strings)
    return {
        'data': data,
        'program': instructions,
    }


def main():
    if len(sys.argv) < 3:
        print('Usage: py assembly.py <in> <out>')

    in_path = sys.argv[1]
    out_path = sys.argv[2]

    with open(in_path) as f:
        strings = f.readlines()

    with open(out_path, 'w') as f:
        f.write(json.dumps(
            parse(strings)
        ))


if __name__ == "__main__":
    main()

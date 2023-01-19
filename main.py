from assembly import parse
from machine import Machine

with open('prog.as') as f:
    text = f.readlines()

program = parse(text)
machine = Machine(initial=program, need_log_registers=True)

while True:
    machine.single_step()
    input()

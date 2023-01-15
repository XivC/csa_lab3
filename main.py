from assembly import parse
from machine import Machine

with open('prog.as') as f:
    text = f.readlines()

program = parse(text)
machine = Machine(program)
machine.run()

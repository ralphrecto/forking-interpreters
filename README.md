# Time-traveling Python interpreter
This is a demonstration of a time-traveling Python interpreter -- one where you can undo the effects of previous statements that have been executed.

Run `python interpreter.py` with a recent-ish Python 3 (I used 3.9) to get a REPL. This REPL treats each line input as a Python statement, with one special addition: an input of `!!` in a single line is treated as a command to undo the effects of the previously executed line.
```
>> x = 1
>> print(x)
1
>> x += 2
>> print(x)
3
>> !!
>> !!
>> print(x)
1
```
This is by no means supposed be robust in any way. I just had an idea of using `fork()` to snapshot interpreter state. For details on the design, see the module comment in `interpreter.py`.

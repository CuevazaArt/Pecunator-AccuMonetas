import py_compile
import os

errs = []
for root, _, files in os.walk("runtime"):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                errs.append(str(e))

if errs:
    print("Syntax Errors Found:")
    for e in errs:
        print(e)
else:
    print("No syntax errors found.")

# FYP_JITPy
LLVMlite based JIT Python compiler

List of files:
tests/ directory for test cases but at the moment there isn't much left. Also missing a testing function to compare native python with LLVM JIT compiled python.


typedefs.py
A few data structures for type inference
TVar: A variable to be typed
TFun: A function to be typed
TCon: A type constructor to generate types
TApp: A type applicator e.g for applying array type to int or double type

datatypes.py 
A few data structures to compress the python AST into for later codegeneration

parseAST.py
A recursive descent visitor class which transforms the python AST into the compressed form with data from datatypes.py

typeVisitor.py
A recursive descent visitor class which traverses our compressed untyped form and generates a list of constraints and variables to be typed

typeinver.py
A type inference algorithm implementation which uses our constraints and untyped variables to generate a solution if one exists which will add the correct types to the variables in our compressed AST. The input argument types are taken into account.

codegen.py 
A recursive descent LLVMlite code generator which traverses our typed and compressed AST and generates LLVM intermediate code for execution by the LLVM execution engine.

toplevel.py 
Ties everything together wraps everything at the top level and calls the LLVM code using a python C Function and a function pointer.
This will segfault/access invalid memory if the cfunc is called incorrectly



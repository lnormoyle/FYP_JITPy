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


###BUGS#####################


Known bugs:
The program breaks at a few places if you use a single argument input types because of the iterators on argument lists. Shouldn't take too long to fix.

The typeVisitor class doesn't support some of the AST nodes that the parseAST class supports so it will break at the type inferece stage.

Probably bugged:

The type inference doesn't seem to apply the inferred types to every variable e.g the Assign variable and some of the return types. I have a work around in place at the moment.

While/If/Cond statements aren't tested and almost certainly have a few small problems.


TODOs for project:
-Various #TODOs through the code

-Test cases and a test program for iterating through all tests

-A lot of commenting needed as the code can be dense and full of references to other files.

-Debugging anything failing tests.

-Turn on the LLVM optimiser 

-Benchmarking

-Support for python 3 static typing/python 3

-Support for more AST nodes.

-Split up the toplevel file into smaller parts perhaps

-Some of the e.g type mapping code has been repeated in parts and could be put into another file

-A lot of the naming is inconsistent and perhaps confusing in places.





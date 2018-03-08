import ast
import sys
import ctypes
from ctypes import CFUNCTYPE, c_double
from llvmlite import ir
from textwrap import dedent
import llvmlite.binding as llvm
import parseAST as pAST
import codegen as cgen
import typedefs as td
from typeinfer import apply
import typeinfer as ti
import typeVisitor as tv
import numpy as np




#pointer     = ir.PointerType()
int_type    = ir.IntType(32)
float_type  = ir.FloatType()
double_type = ir.DoubleType()
void_type   = ir.VoidType()
void_ptr    = ir.PointerType(8)

##TODO add import here
int32 = td.TCon("Int32")
int64 = td.TCon("Int64")
float32 = td.TCon("Float")
double64 = td.TCon("Double")
void = td.TCon("Void")
array = lambda t: td.TApp(td.TCon("Array"), t)

array_int32 = array(int32)
array_int64 = array(int64)
array_double64 = array(double64)

def array_type(elt_type):
    return ir.LiteralStructType([
        ir.PointerType(elt_type),  # data
        int_type,				   # dimensions
        ir.PointerType(int_type),  # shape
    ])

int32_array = ir.PointerType(array_type (int_type) )
int64_array = ir.PointerType(array_type (ir.IntType(64) ) )
double_array = ir.PointerType(array_type (double_type) )


def to_lltype(ptype):
    return int_type

def determined(ty):
	return len(td.ftv(ty)) == 0

def create_execution_engine():
    """
    Create an ExecutionEngine suitable for JIT code generation on
    the host CPU.  The engine is reusable for an arbitrary number of
    modules.
    """
    # Create a target machine representing the host
    target = llvm.Target.from_default_triple()
    target_machine = target.create_target_machine()
    # And an execution engine with an empty backing module
    backing_mod = llvm.parse_assembly("")
    engine = llvm.create_mcjit_compiler(backing_mod, target_machine)
    return engine


def compile_ir(engine, llvm_ir):
    """
    Compile the LLVM IR string with the given engine.
    The compiled module object is returned.
    """
    # Create a LLVM module object from the IR
    mod = llvm.parse_assembly(llvm_ir)
    mod.verify()
    # Now add the module and make sure it is ready for execution
    engine.add_module(mod)
    engine.finalize_object()
    return mod

def wrap_type(llvm_type):
    kind = llvm_type
    if kind == int_type:
        ctype = getattr(ctypes, "c_int"+str(32))
    elif kind == double_type:
        ctype = ctypes.c_double
    elif kind == void_type:
        ctype = None
    else:
        raise Exception("Unknown LLVM type %s" % kind)
    return ctype

def wrap_pyarg(arg):
    if isinstance(arg, np.ndarray):
        if arg.dtype == np.dtype('int32'):
            return array(int32)
        elif arg.dtype == np.dtype('int64'):
            return array(int64)
        elif arg.dtype == np.dtype('double'):
            return array(double64)
        elif arg.dtype == np.dtype('float'):
            return array(float32)
    elif isinstance(arg, int) & (arg < 2**32):
        ctype = getattr(ctypes, "c_int"+str(32))
    elif isinstance(arg, int) & (arg < sys.maxint):
        ctype = getattr(ctypes, "c_int"+str(64))
    elif isinstance(arg, float):
        ctype = ctypes.c_double
    else:
        raise Exception("Unknown type %s" % arg)
    return ctype

def wrap_pytype(py_type):
    kind = py_type
    if kind == int32:
        ctype = getattr(ctypes, "c_int"+str(32))
    elif kind == int64:
        ctype = getattr(ctypes, "c_int"+str(64))
    elif kind == double64:
        ctype = ctypes.c_double
    else:
        raise Exception("Unknown type %s" % kind)
    return ctype

def type_infer(fn, ast, input_fn, args_in, verbose = False):
    infer = tv.TypeInfer(input_fn, args_in)
    ty = infer.visit(ast)   	
    mgu = ti.solve(infer.constraints)
    #TypeInfer returns multiple TFun objects
    infer_ty = []
    #TODO check with 1, should work normally
    #check this works properly
    for i in range (len(ty)-1):
        unifier = ti.unify(ty[i], ty[i+1])
        specializer = ti.compose(unifier,mgu)


    #adds all tfuns into a list with all the rets/argtys
    for tFun in ty: 
        infer_ty_single = ti.apply(specializer, tFun)  
        #add functions into a list
        infer_ty.append(infer_ty_single)
        #get the args/ret for ctypes func call

    #TODO needs clean up
    # this is just a quick fix because I was using wrong variable 
    for i in range (len(infer_ty)):
            if(infer_ty[i].name == input_fn): 
                top_retty = infer_ty[i].retty 
                top_argtys = infer_ty[i].argtys



    if (verbose):  
        print('Unifier: ')
        for (a,b) in mgu.iteritems():
            print(a + ' ~ ' + str(b))
        print('Solution: ', infer_ty)
    return infer_ty, top_retty, top_argtys
#We are going to return dict objects for argty and retty based on function name
#We have all of these in the infer_ty variable which stores a TFun object for every function

#We only need to specialize the function we are calling
def specialize(ast, infer_ty):
    #gather return types and arg types of all the functions we will codegen
    ret_dict = {}
    arg_dict = {}    
    for tfun in infer_ty:  
        ret_dict[tfun.name] = tfun.retty
        arg_dict[tfun.name] = tfun.argtys
   
    specializer = infer_ty
    ir_module = codegen(ast, specializer, ret_dict, arg_dict)      
    return ir_module

def codegen(ast, specializer, retty, argtys):
    codegen = cgen.LLVMEmitter(specializer, retty, argtys)
    module = codegen.visit(ast)
    #cgen.function.verify()       
    #TODO put in optimiser 
    return codegen.builder.module


def wrap_function(ret_type, args, function_name, engine):
    ret_ctype = wrap_pytype(ret_type)
    args_ctypes = map(wrap_pyarg, args)

    func_ptr = engine.get_function_address(function_name)
    cfunc = CFUNCTYPE(ret_ctype, *args_ctypes)(func_ptr)
    return cfunc

            
def wrap_ndarray(na):
    # For NumPy arrays grab the underlying data pointer. Doesn't copy.
    ctype = _nptypemap[na.dtype.char]
    _shape = list(na.shape)
    data = na.ctypes.data_as(ctypes.POINTER(ctype))
    dims = len(na.strides)
    shape = (ctypes.c_int*dims)(*_shape)
    return (data, dims, shape)


def JIT(file_name, function_name, args, opt_on=False, verbose = False):
    src = ""
    with open (file_name, "r") as src_file:
        src = src_file.read()
    if(verbose):
        print("Reading source:")
        print(src)   
     
    llvm.initialize()
    llvm.initialize_native_target()
    llvm.initialize_native_asmprinter()  
    transformer=pAST.PythonVisitor()
    ast=transformer(src)
    module = ir.Module(name="JITPy")

	#for only 1 arg
    args_in = []
    if (len(args_in) ==1):
        args.append(args)
    else:
        args_in = args

    infer_ty, ret_ty, arg_tys = type_infer(src, ast, function_name, args_in)   
    #print(infer_ty)
    ir_module = specialize(ast, infer_ty)
    llvm_ir = str(ir_module)
    if (verbose):
        print(llvm_ir)
    engine = create_execution_engine()
    mod = compile_ir(engine, llvm_ir)
    cfunc = wrap_function(ret_ty, args_in, function_name, engine)
    result = cfunc(*args_in)
    result_str = function_name + "(" + str(args_in) +")" + " = " + str(result)
    print(result_str)
JIT("tests/fcalls.py","main",[12,6])





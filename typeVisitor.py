import sys
import typedefs as tdef
import string
import typedefs as td
from llvmlite import ir
import numpy as np


def arg_pytype(arg):
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
        return int32
    elif isinstance(arg, int) & (arg < sys.maxint):
        return int64
    elif isinstance(arg, float):
        return double64
    else:
        raise Exception("Type not supported: %s" % type(arg))

pointer     = ir.PointerType
int_type    = ir.IntType(32)
float_type  = ir.FloatType()
double_type = ir.DoubleType()
void_type   = ir.VoidType()
void_ptr    = pointer(8)
short_ptr = pointer(32)
long_ptr = pointer(64)

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

lltypes_map = {
    int32          : int_type,
    int64          : int_type,
    float32        : float_type,
    double64       : double_type,
    array_int32    : int32_array,
    array_int64    : int64_array,
    array_double64 : double_array
}

def to_lltype(ptype):
    return lltypes_map[ptype]

def determined(ty):
	return len(ftv(ty)) == 0



def naming():
    k = 0
    while True:
        for a in string.ascii_lowercase:
            yield ("'"+a+str(k)) if (k > 0) else (a)
        k = k+1

class TypeInfer(object):

    def __init__(self, input_fn, args_in):
        self.constraints = []
        self.env = {}
        self.names = naming()    
        self.rets = {} #rets of each fn
        self.argtys = {}
        self.args_in = map(arg_pytype, list(args_in)) #get the types of the inputs
        self.currentfn = ""
        self.input_fn = input_fn #add the input fn to add input types for solving 

    def fresh(self):
        return tdef.TVar('$' + next(self.names))  # New meta type variable.

    def visit(self, node):
        name = "visit_%s" % type(node).__name__
        if hasattr(self, name):
            return getattr(self, name)(node)
        else:
            return self.generic_visit(node)

    def visit_Module(self, node):
        map(self.visit_FuncDef,node.body)
        body = map(self.visit, node.body)  
        return body
        

    def visit_FuncDef(self,node):   
        fname = node.fname
        if(fname == self.input_fn): #we have argument types already
            self.argtys[fname] = self.args_in
        else:
            self.argtys[fname] = [self.fresh() for v in node.args]

        for (arg, ty) in zip(node.args, self.argtys[fname]):
            arg.type = ty
            self.env[arg.id] = ty    
        ret_str = "$ret_ty_" + fname
        self.rets[fname] = tdef.TVar(ret_str)

    def visit_Fun(self, node):
        self.currentfn = node.fname
        map(self.visit, node.body)
        return tdef.TFun(self.argtys[node.fname], self.rets[node.fname], node.fname)

    def visit_Noop(self, node):
        return None

    def visit_LitInt(self, node):
        tv = int32
        node.type = tv
        return tv

    def visit_LitFloat(self, node):
        tv = double64
        node.type = tv
        return tv

    def visit_Assign(self, node):       
        ty = self.visit(node.val)
        if node.ref in self.env:
            # Subsequent uses of a variable must have the same type.
            self.constraints += [(ty, self.env[node.ref])]
        self.env[node.ref] = ty
        node.type = ty
        return None

    def visit_Index(self, node):
        tv = self.fresh()
        ty = self.visit(node.val)
        ixty = self.visit(node.ix)
        self.constraints += [(ty, array(tv)), (ixty, int32)]
        return tv

    def visit_Prim(self, node):
        if node.fn == "shape#":
            return array(int32)
        elif node.fn == "UAdd#" or node.fn == "Neg#" or node.fn == "Not#" or node.fn == "Inv#":
            tya = self.visit(node.args[0])
            self.constraints += [(tya)]
            return tya
        else: #All other prim ops are binops
            tya = self.visit(node.args[0])
            tyb = self.visit(node.args[1])
            self.constraints += [(tya, tyb)]
            return tyb

    def visit_Var(self, node):
        ty = self.env[node.id]
        node.type = ty
        return ty

    def visit_Return(self, node):
        ty = self.visit(node.val)
        self.constraints += [(ty, self.rets[self.currentfn])]

    def visit_App(self, node):        
        fname = node.fn.id  #called function name
        argtys = self.argtys[fname] 
        for (arg, ty) in zip(node.args, argtys):           
            if arg.id in self.env:
                # Subsequent uses of a variable must have the same type.
                self.constraints += [(ty, self.env[arg.id])]
                arg.type = ty            
                #function arg type must match input type i.e a ~ $a 
                #e.g inputs a,b to function [$a,$b] --> $retty
                #if int32 d = func(int32 a, int32b)
                #we known func = [Int32, Int32 -> Int32]
        #return type of called fn equals type of variable its assigned to    
        
        return self.rets[fname]

    def visit_Loop(self, node):
        self.env[node.var.id] = int32
        varty = self.visit(node.var)
        begin = self.visit(node.begin)
        end = self.visit(node.end)

        self.constraints += [(varty, int32), (
            begin, int32), (end, int32)]
        map(self.visit, node.body)

    def generic_visit(self, node):
        raise NotImplementedError

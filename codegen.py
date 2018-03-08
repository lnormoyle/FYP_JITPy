from llvmlite import ir
from textwrap import dedent
from collections import deque, defaultdict
import datatypes as data
import typedefs as td

module = ir.Module(name="JITPy")


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

def is_array(ty):
    return isinstance(ty, td.TApp) and ty.a == td.TCon("Array")

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
	
class LLVMEmitter(object):
    def __init__(self, spec_types, retty, argtys):
        self.function = None             # LLVM Function
        self.fnames = {}                 # Dict of fns
        self.builder = None              # LLVM Builder
        self.locals = {}                 # Local variables
        self.arrays = defaultdict(dict)  # Array metadata
        self.exit_block = None           # Exit block
        self.spec_types = spec_types     # Type specialization
        self.retty = retty              # Return type
        self.argtys = argtys            # Argument types

    def visit_Module(self, node):
        func_defs = map(self.visit_FuncDef,node.body)
        body = map(self.visit, node.body)
        self.builder.position_at_end(self.exit_block)
  

    def visit_FuncDef(self,node):
        #do a lookup to get ret and arg types  
        name = node.fname
        
        rettype = to_lltype(self.retty[name])
        #loop lltypesmap 
        argtypes = [] 
        for argty in self.argtys[name]:
            argtypes.append(to_lltype(argty))
    
        func_type = ir.FunctionType(rettype, argtypes, False)       
        function = ir.Function(module, func_type, name)
        self.fnames[name] = function

    def start_function(self, name, module, rettype, argtypes):
        func_type = ir.FunctionType(rettype, argtypes, False)
        function = self.fnames[name]
        entry_block = function.append_basic_block("entry")
        builder =ir.IRBuilder(entry_block)
        self.exit_block = function.append_basic_block("exit")
        self.function = function
        self.builder = builder


    def end_function(self):
        self.builder.position_at_end(self.exit_block)
        if 'retval' in self.locals:
            retval = self.builder.load(self.locals['retval'])
            self.builder.ret(retval)
        else:
            self.builder.ret_void()

    def add_block(self, name):
        return self.function.append_basic_block(name)

    def set_block(self, block):
        self.block = block
        self.builder.position_at_end(block)

    def cbranch(self, cond, true_block, false_block):
        self.builder.cbranch(cond, true_block, false_block)

    def branch(self, next_block):
        self.builder.branch(next_block)

    def specialize(self, val):
        if isinstance(val.type, td.TVar):
            return to_lltype(self.spec_types[val.type.s])
        else:
            return val.type
				
    def const(self, val):
        if isinstance(val, (int, long)):
            return ir.Constant(int_type, val)
        elif isinstance(val, float):
            return ir.Constant(double_type, val)
        elif isinstance(val, bool):
            return ir.Constantint(bool_type, int(val))
        elif isinstance(val, str):
            return ir.Constant(val)
        else:
            raise NotImplementedError

    def visit_LitInt(self, node):
        typdef = self.specialize(node)        
        ty = to_lltype(typdef)
        if ty is double_type:
            return ir.Constant(double_type, node.n)
        elif ty == int_type:
            return ir.Constant(int_type, node.n)
        else:
            raise NotImplementedError

    def visit_LitFloat(self, node):
        typdef = self.specialize(node)
        ty = to_lltype(typdef)
        if ty is double_type:
            return ir.Constant(double_type, node.n)
        elif ty == int_type:
            return Constant.int(int_type, node.n)

    def visit_Noop(self, node):
        pass

    def visit_Fun(self, node):
        func_name = node.fname
        rettype = to_lltype(self.retty[func_name])	
        argtypes = []	
        for argty in self.argtys[func_name]:
            argtypes.append(to_lltype(argty))
 
        self.start_function(func_name, module, rettype, argtypes)
        if  isinstance(self.argtys[func_name],list):  
            for (ar, llarg, argty) in zip(node.args, self.function.args, self.argtys[func_name]):
                name = ar.id
                llarg.name = name  
                
                if is_array(argty):
                    zero = self.const(0)
                    one = self.const(1)
                    two = self.const(2)

                    data = self.builder.gep(llarg, [
                                            zero, zero], name=(name + '_data'))
                    dims = self.builder.gep(llarg, [
                                            zero, one], name=(name + '_dims'))
                    shape = self.builder.gep(llarg, [
                                             zero, two], name=(name + '_strides'))

                    self.arrays[name]['data'] = self.builder.load(data)
                    self.arrays[name]['dims'] = self.builder.load(dims)
                    self.arrays[name]['shape'] = self.builder.load(shape)
                    self.locals[name] = llarg
                else:
                    argref = self.builder.alloca(to_lltype(argty))
                    self.builder.store(llarg, argref)
                    
                    self.locals[name] = argref
                    
        else:      
            #TODO Check this works properly. only one argument so should be okay
            name = node.args[0].id  
            self.function.args[0].name = name
            argref = self.builder.alloca(argtypes[0])
            self.builder.store(self.function.args[0], argref)
            self.locals[name] = argref 

        # Setup the register for return type.
        if rettype is not void_type:
            self.locals['retval'] = self.builder.alloca(rettype, name="retval")
        map(self.visit, node.body)
        self.end_function()

    def visit_Index(self, node):
        if isinstance(node.val, data.Var) and node.val.id in self.arrays:
            val = self.visit(node.val)
            ix = self.visit(node.ix)
            dataptr = self.arrays[node.val.id]['data']
            ret = self.builder.gep(dataptr, [ix])
            return self.builder.load(ret)
        else:
            val = self.visit(node.val)
            ix = self.visit(node.ix)
            ret = self.builder.gep(val, [ix])
            return self.builder.load(ret)

    def visit_Var(self, node):
        return self.builder.load(self.locals[node.id])

    def visit_Return(self, node):
        val = self.visit(node.val)
        if val.type != void_type:
            self.builder.store(val, self.locals['retval'])
        self.builder.branch(self.exit_block)

	def visit_WhileLoop(self,node):
		cond_block=self.function.append_basic_block('while.cond')
		body_block=self.function.append_basic_block('while.body')
		end_block=self.function.append_basic_block('while.end')
		#set up test block
		self.branch(cond_block)
		self.set_block(cond_block)
		cond=self.visit(node.test)
		self.builder.cbranch(cond,body_block,end_block)
		#set up body block
		self.set_block(body_block)
		map(self.visit, node.body)
		#TODO check this in if test
		self.builder.branch(cond_block)
		self.set_block(end_block)

    def visit_Loop(self, node):
        init_block = self.function.append_basic_block('for.init')
        test_block = self.function.append_basic_block('for.cond')
        body_block = self.function.append_basic_block('for.body')
        end_block = self.function.append_basic_block("for.end")

        self.branch(init_block)
        self.set_block(init_block)

        start = self.visit(node.begin)
        stop = self.visit(node.end)
        step = 1

        # Setup the increment variable
        varname = node.var.id
        inc = self.builder.alloca(int_type, name=varname)
        self.builder.store(start, inc)
        self.locals[varname] = inc

        # Setup the loop condition
        self.branch(test_block)
        self.set_block(test_block)
        #TODO check
        #cond = self.builder.icmp(lc.ICMP_SLT, self.builder.load(inc), stop)
        cond=self.builder.icmp_signed("<", self.builder.load(inc),stop)
        self.builder.cbranch(cond, body_block, end_block)

        # Generate the loop body
        self.set_block(body_block)
        map(self.visit, node.body)

        # Increment the counter
        succ = self.builder.add(self.const(step), self.builder.load(inc))
        self.builder.store(succ, inc)

        # Exit the loop
        self.builder.branch(test_block)
        self.set_block(end_block)

    def visit_App(self, node):
        name = str(node.fn.id)
        fn = self.fnames[name]
        args = map(self.visit,node.args)
        return self.builder.call(fn, args, name='', cconv=None, tail=False, fastmath=())

	#TODO test other version
	def visit_Cond(self, node):

		test_block=self.builder.append_basic_block('if_cond')
		if_block=self.builder.append_basic_block('if_then')
		else_block=self.builder.append_basic_block('if_else')
		end_block=self.builder.append_basic_block('if.end')

		#set up the if cond
		self.branch(test_block)
		self.set_block(test_block)
		cond = self.visit(node.test)
		self.builder.cbranch(cond,if_block,else_block)
		#set up the if body
		self.set_block(if_block)
		map(self.visit,node.body)
		self.builder.branch(end_block)
		#set up the else body
		self.set_block(else_block)
		map(self.visit, node.body)
		self.builder.branch(end_block)
		self.builder.set_block(end_block)
        
    #TODO fix typing here
    def visit_Prim(self, node):
        if node.fn == "shape#":
            ref = node.args[0]
            shape = self.arrays[ref.id]['shape']
            return shape
        elif node.fn == "mult#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            if a.type == double_type:
                return self.builder.fmul(a, b)
            else:
                return self.builder.mul(a, b)
        elif node.fn == "add#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            if a.type == double_type:
                return self.builder.fadd(a, b)
            else:
                return self.builder.add(a, b)
        elif node.fn == "sub#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            if a.type == double_type:
                return self.builder.fsub(a, b)
            else:
                return self.builder.sub(a, b)
        elif node.fn == "mod#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            if a.type == double_type:
                 return self.builder.frem(a,b)
            else:
                 if a.type == int_type:
                    return self.builder.sdiv(a, b)
                 else:
                    return self.builder.udiv(a, b)

        elif node.fn == "BitAnd#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.and_(a,b)

        elif node.fn == "BitXor#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.xor(a,b)

        elif node.fn == "BitOr#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.or_(a,b)

        elif node.fn == "lshift#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.shl(a,b)

      #TODO check logical vs arithmetic shift for signed/unsigned etc
	  #TODO check icmp signed type vs unsigned type
        elif node.fn == "rshift#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            if a.type == int_type:
                return self.builder.ashr(a, b)
            else:
                return self.builder.lshr(a,b)
        elif node.fn == "eq#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, "==")

        elif node.fn == "neq#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, "!=")

        elif node.fn == "lt#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, "<")

        elif node.fn == "lte#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, "<=")
        elif node.fn == "gt#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, ">")

        elif node.fn == "gte#":
            a = self.visit(node.args[0])
            b = self.visit(node.args[1])
            return self.builder.icmp_signed(int_type, a,b, ">=")

        elif node.fn == "Neg#":
            a = self.visit(node.args[0])
            return self.builder.neg(a)

        elif node.fn == "Not#":
            a = self.visit(node.args[0])
            return self.builder.not_(a)

        elif node.fn == "Inv#":
            a = self.visit(node.args[0])
            return self.builder.not_(a)

        elif node.fn == "UAdd#":
            pass #No Op

        else:
            raise NotImplementedError

    def visit_Assign(self, node):

        # Subsequent assignment
        if node.ref in self.locals:
            name = node.ref
            var = self.locals[name]
            val = self.visit(node.val)

            self.builder.store(val, var)
            self.locals[name] = var
            return var

        # First assignment
        else:            
            name = node.ref
            #types weren't applied to function calls in type infer
            #quick fix here is to get type from the final inference result
            if (isinstance, node.val, data.App):
                ty = self.retty[node.val.fn.id]
                ty = to_lltype(ty)
            else:
                ty = self.specialize(node)
            var = self.builder.alloca(ty, name=name)            
            val = self.visit(node.val)	
            self.builder.store(val, var)
            self.locals[name] = var
            return var

    def visit(self, node):
        name = "visit_%s" % type(node).__name__
        if hasattr(self, name):
            return getattr(self, name)(node)
        else:
			return self.generic_visit(node)


from __future__ import print_function
from llvmlite import ir
from textwrap import dedent
import sys
import ast
import pprint
import datatypes as data
import typedefs as td

##TODO add import here
int32 = td.TCon("Int32")
int64 = td.TCon("Int64")
float32 = td.TCon("Float")
double64 = td.TCon("Double")
void = td.TCon("Void")
array = lambda t: td.TApp(td.TCon("Array"), t)



def printAst(ast, indent='  ', stream=sys.stdout, initlevel=0):
    "Pretty-print an AST to the given output stream."
    print_node(ast, initlevel, indent, stream.write)
    stream.write('\n')

def print_node(node, level, indent, write):
    "Recurse through a node, pretty-printing it."
    pfx = indent * level
    pfx_prev = indent * (level - 1)
    if not isinstance(node, list):
        write(node.__class__.__name__)
    if hasattr(node, 'body'):
        if hasattr(node, 'name'):
            write(" '" + node.name + "' ")
        write('(\n')
        for child in node.body:
            write(pfx)
            print_node(child, level+1, indent, write)
            write('\n')
        write(pfx_prev + ')')
    elif hasattr(node, 'value'):
        write('[ ')
        if hasattr(node, 'targets'):
            print_node(node.targets, level+1, indent, write)
            write(' = ')
        print_node(node.value, level+1, indent, write)
        if hasattr(node, 'attr'):
            write('.')
            write(node.attr)
        write(' ]')
    elif hasattr(node, 'func'):
        write('(')
        print_node(node.func, level+1, indent, write)
        if hasattr(node, 'args'):
            write('(')
            print_node(node.args, level+1, indent, write)
            write(')')
        write(')')
    elif isinstance(node, list):
        for n in node:
            print_node(n, level+1, indent, write)
            write(',')
    elif hasattr(node, 'id'):
        write('(' + repr(node.id) + ')')
    elif hasattr(node, 's'):
        write('(' + repr(node.s) + ')')



primops = {ast.Add: "add#", ast.Mult: "mult#", ast.Sub: "sub#", ast.Div: "div#", ast.FloorDiv: "floordiv#", ast.Mod: "mod#", ast.Pow: "pow#", ast.LShift: "lshift#", ast.RShift: "rshift#", ast.BitOr: "BitOr#", ast.BitXor: "BitXor#", ast.BitAnd: "BitAnd#", ast.Compare: "comp#", ast.Eq: "eq#", ast.NotEq: "neq#", ast.Lt: "lt#", ast.LtE: "lte#", ast.Gt: "gt#", ast.GtE: "gte#", ast.Is: "is#", ast.IsNot: "isnot#", ast.In: "in#", ast.NotIn: "notin#", ast.UAdd: "UAdd#",  ast.USub: "Neg#", ast.Not: "Not#", ast.Invert: "Inv#"}
        
class PythonVisitor(ast.NodeVisitor):

    def __init__(self):    
        pass

    def __call__(self, source, verbose = False):
		#todo fix
        if isinstance(source, ir.Module):
            source = dedent(inspect.getsource(source))
        if isinstance(source, ir.FunctionType):
            source = dedent(inspect.getsource(source))
        #if isinstance(source, ir.LambdaType):
        #    source = dedent(inspect.getsource(source))
        elif isinstance(source, (str, unicode)):
            source = dedent(source)
        else:
            raise NotImplementedError

        self._source = source
        self._ast = ast.parse(source)
        if(verbose):		
            printAst(self._ast)
        return self.visit(self._ast)

    def visit_Module(self, node):
        body = map(self.visit, node.body)
        return data.Module(body)

    def visit_Name(self, node):
        return data.Var(node.id)

    def visit_Num(self, node):
        if isinstance(node.n, float):
            return data.LitFloat(node.n)
        else:
            return data.LitInt(node.n)

    def visit_Bool(self, node):
        return data.LitBool(node.n)

    def visit_Call(self, node):
        name = self.visit(node.func)
        args = map(self.visit, node.args)
        keywords = map(self.visit, node.keywords)
        return data.App(name, args)

    def visit_Compare(self,node):
        left = self.visit(node.left)
        right = self.visit(node.comparators[0])
        op = node.ops[0]
        opname = op.__class__
        return data.Prim(opname, [left, right])

    def visit_BinOp(self, node):
        op_str = node.op.__class__
        a = self.visit(node.left)
        b = self.visit(node.right)
        opname = primops[op_str]
        return data.Prim(opname, [a, b])

    def visit_UnaryOp(self,node):
        op_str = node.op.__class__
        operand = self.visit(node.operand)
        opname = primops[op_str]
        return data.Prim(opname, operand)

    def visit_Assign(self, node):
        targets = node.targets

        assert len(node.targets) == 1
        var = node.targets[0].id
        val = self.visit(node.value)
        return data.Assign(var, val)

    def visit_FunctionDef(self, node):
        stmts = list(node.body)
        stmts = map(self.visit, stmts)
        args = map(self.visit, node.args.args)
        res = data.Fun(node.name, args, stmts)
        return res

    def visit_Pass(self, node):
        return data.Noop()

    def visit_Lambda(self, node):
        args = self.visit(node.args)
        body = self.visit(node.body)

    def visit_Return(self, node):
        val = self.visit(node.value)
        return data.Return(val)

    def visit_Attribute(self, node):
        if node.attr == "shape":
            val = self.visit(node.value)
            return data.Prim("shape#", [val])
        else:
            raise NotImplementedError

    def visit_Subscript(self, node):
        if isinstance(node.ctx, ast.Load):
            if node.slice:
                val = self.visit(node.value)
                ix = self.visit(node.slice.value)
                return data.Index(val, ix)
        elif isinstance(node.ctx, ast.Store):
            raise NotImplementedError

    def visit_If(self, node):

        test = self.visit(node.test)
        body_stmts = map(self.visit, node.body)
        #TODO test a null if statement
        else_stmts = map(self.visit, node.orelse)
        return data.Cond(test,body_stmts,else_stmts)

    def visit_While(self,node):

        test= self.visit(node.test)
        body = self.visit(nobe.body)
        end=(node.orelse)
        return WhileLoop(test,body,end)

#TODO check that the end/or else part is needed/or working

    def visit_For(self, node):
        target = self.visit(node.target)
        stmts = map(self.visit, node.body)
        if node.iter.func.id in {"xrange", "range"}:
            args = map(self.visit, node.iter.args)
        else:
            raise Exception("Loop must be over range")

        if len(args) == 1:   # xrange(n)
            return data.Loop(target, data.LitInt(0, type=int32), args[0], stmts)
        elif len(args) == 2:  # xrange(n,m)
            return data.Loop(target, args[0], args[1], stmts)

       
       
        

    def visit_AugAssign(self, node):
        if isinstance(node.op, ast.Add):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("add#", [data.Var(ref), value]))
        if isinstance(node.op, ast.Sub):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("sub#", [data.Var(ref), value]))
        if isinstance(node.op, ast.Mul):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("mult#", [data.Var(ref), value]))
        if isinstance(node.op, ast.Div):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("div#", [data.Var(ref), value]))
        if isinstance(node.op, ast.FloorDiv):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("floordiv#", [data.Var(ref), value]))
        if isinstance(node.op, ast.Mod):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("mod#", [data.Var(ref), value]))
        if isinstance(node.op, ast.Pow):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("pow#", [data.Var(ref), value]))
        if isinstance(node.op, ast.LShift):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("lshift#", [data.Var(ref), value]))
        if isinstance(node.op, ast.RShift):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("rshift#", [data.Var(ref), value]))
        if isinstance(node.op, ast.BitOr):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("BitOr#", [data.Var(ref), value]))
        if isinstance(node.op, ast.BitXor):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("BitXor#", [data.Var(ref), value]))
        if isinstance(node.op, ast.BitAnd):
            ref = node.target.id
            value = self.visit(node.value)
            return data.Assign(ref, data.Prim("BitAnd#", [data.Var(ref), value]))
        else:
            raise NotImplementedError



    def generic_visit(self, node):
        raise NotImplementedError


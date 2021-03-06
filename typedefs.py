class TVar(object):
    def __init__(self, s):
        self.s = s

    def __hash__(self):
        return hash(self.s)

    def __eq__(self, other):
        if isinstance(other, TVar):
            return (self.s == other.s)
        else:
            return False

    def __str__(self):
        return self.s
    __repr__ = __str__

class TCon(object):
    def __init__(self, s):
        self.s = s

    def __eq__(self, other):
        if isinstance(other, TCon):
            return (self.s == other.s)
        else:
            return False

    def __hash__(self):
        return hash(self.s)

    def __str__(self):
        return self.s
    __repr__ = __str__

class TApp(object):
    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __eq__(self, other):
        if isinstance(other, TApp):
            return (self.a == other.a) & (self.b == other.b)
        else:
            return False

    def __hash__(self):
        return hash((self.a, self.b))

    def __str__(self):
        return str(self.a) + " " + str(self.b)
    __repr__ = __str__

class TFun(object):
    def __init__(self, argtys, retty, name = ""):
        assert isinstance(argtys, list)
        self.argtys = argtys
        self.retty = retty
        self.name = name

    def __eq__(self, other):
        if isinstance(other, TFun):
            return (self.argtys == other.argtys) & (self.retty == other.retty)
        else:
            return False

    def __str__(self):
        return str(self.argtys) + " -> " + str(self.retty)
    __repr__ = __str__

def ftv(x):
    if isinstance(x, TCon):
        return set()
    elif isinstance(x, TApp):
        return ftv(x.a) | ftv(x.b)
    elif isinstance(x, TFun):
        return reduce(set.union, map(ftv, x.argtys)) | ftv(x.retty)
    elif isinstance(x, TVar):
        return set([x])

def is_array(ty):
    return isinstance(ty, TApp) and ty.a == TCon("Array")


import sys
from _quake import lib, ffi
import time


class Edict(object):
    def __init__(self, index):
        self._index = index


def float_read(p):
    return p._float
def float_write(p, value):
    p._float = value

def vec_read(p):
    return (p.vector[0], p.vector[1], p.vector[2])
def vec_write(p, value):
    (p.vector[0], p.vector[1], p.vector[2]) = value

def string_read(p):
    return ffi.string(lib.pr_strings + p._int)
def string_write(p, value):
    print "writing string %r: not supported" % (value,)


EVAL_TYPES = {
    lib.ev_float: (float_read, float_write),
    lib.ev_vector: (vec_read, vec_write),
    lib.ev_string: (string_read, string_write),
}


def make_edict_property(ddef):
    fieldindex = ddef.ofs
    name = ffi.string(lib.pr_strings + ddef.s_name)
    #
    def missing_eval(p, value=None):
        print 'missing type support for %r' % (name,)
    #
    eval_read, eval_write = EVAL_TYPES.get(
        ddef.type, (missing_eval, missing_eval))
    #
    def getter(self):
        return eval_read(lib.get_edict_field(self._index, fieldindex))
    def setter(self, value):
        eval_write(lib.get_edict_field(self._index, fieldindex), value)
    #
    setattr(Edict, name, property(getter, setter))


def initialize():
    global initialized

    for i in range(1, lib.progs.numfielddefs):
        make_edict_property(lib.pr_fielddefs[i])

    initialized = True
initialized = False


@ffi.def_extern()
def PQuake_frame_update():
    print 'updating'
    if not initialized:
        initialize()
    import pdb;pdb.set_trace()
    time.sleep(0.05)


lib.PQuake_main(3, [ffi.new("char[]", sys.executable),
                    ffi.new("char[]", "+map"),
                    ffi.new("char[]", "e1m1")])

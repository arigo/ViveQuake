import sys
from _quake import lib, ffi
import time
import thread


class Edict(object):
    def __init__(self, index):
        if index >= lib.sv.num_edicts:
            raise IndexError
        self._index = index

    def __eq__(self, other):
        return isinstance(other, Edict) and other._index == self._index

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self._index

    def __repr__(self):
        return 'Edict(%r)' % (self._index,)

def edicts():
    try:
        i = 0
        while True:
            yield Edict(i)
            i += 1
    except IndexError:
        pass

def float_read(p):
    return p._float
def float_write(p, value):
    p._float = value

def vec_read(p):
    return (p.vector[0], p.vector[1], p.vector[2])
def vec_write(p, value):
    (p.vector[0], p.vector[1], p.vector[2]) = value

def string_read(p):
    if p._int == 0:
        return None
    return ffi.string(lib.pr_strings + p._int)
def string_write(p, value):
    print "writing string %r: not supported" % (value,)

def entity_read(p):
    if p._int == 0:
        return None
    else:
        return Edict(p._int)
def entity_write(p, value):
    if value is None:
        p._int = 0
    else:
        p._int = value._index

EVAL_TYPES = {
    lib.ev_float: (float_read, float_write),
    lib.ev_vector: (vec_read, vec_write),
    lib.ev_string: (string_read, string_write),
    lib.ev_entity: (entity_read, entity_write),
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
    for i in range(1, lib.progs.numfielddefs):
        make_edict_property(lib.pr_fielddefs[i])
    print 'Python initialized'


# ------------------------------------------------------------


class QuakeServer(object):
    debug_init = False

    def __init__(self, args):
        args = [sys.executable] + args
        self.argv = [ffi.new("char[]", a) for a in args]
        self.argv_list = ffi.new("char *[]", self.argv)
        lib.PQuake_Ready(len(self.argv), self.argv_list)
        self.prev_time = time.time()
        self.initialized = False

    def host_frame(self):
        if not self.initialized and lib.progs != ffi.NULL:
            initialize()
            if self.debug_init:
                import pdb; pdb.set_trace()
            self.initialized = True
        next_time = time.time()
        delay = next_time - self.prev_time
        self.prev_time = next_time
        lib.Host_Frame(delay)

    def get_level_model_name(self):
        res = Edict(0).model
        assert res.startswith('maps/') and res.endswith('.bsp')
        return res[5:-4]

    def get_player_start_position(self):
        for ed in edicts():
            if ed.classname == 'info_player_start':
                return ed.origin
        raise LookupError("'info_player_start' not found")


if __name__ == "__main__":
    srv = QuakeServer(["+map", "e1m1"])
    srv.debug_init = True
    while True:
        srv.host_frame()
        time.sleep(0.1)

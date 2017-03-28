import sys
from _quake import lib, ffi
import time
import thread

from maploader import map_vertex, map_angles


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

def edicts(start=0):
    try:
        i = start
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

    def __init__(self, args, debug_init=False):
        args = [sys.executable] + args
        self.argv = [ffi.new("char[]", a) for a in args]
        self.argv_list = ffi.new("char *[]", self.argv)
        lib.PQuake_Ready(len(self.argv), self.argv_list)
        self.prev_time = time.time()
        self.initialized = False
        for i in range(30):
            self.host_frame(0.1)
            if lib.progs != ffi.NULL:
                break
        else:
            raise RuntimeError("Quake does not start a map (args=%r)" %
                               (args[1:],))
        initialize()
        self.model_by_index = {}

    def host_frame(self, forced_delay=None):
        next_time = time.time()
        delay = next_time - self.prev_time
        self.prev_time = next_time
        if forced_delay is not None:
            delay = forced_delay
        elif delay > 0.1:
            delay = 0.1
        #print "%.3f host frame" % delay
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

    def get_lightstyles(self, first=0):
        lightstyles = []
        for p in lib.sv.lightstyles[first : len(lib.sv.lightstyles)]:
            lightstyles.append(ffi.string(p) if p else "m")
        return lightstyles

    def enum_snapshot_models(self):
        NULLVEC = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        for ed in edicts(start=1):
            index = int(ed.modelindex)
            # XXX use sv.model_precache instead
            try:
                if index <= 0:    # removed or invisible edict
                    model = ""
                else:
                    model = self.model_by_index[index]
            except KeyError:
                if ed.model.startswith('progs/') and ed.model.endswith('.mdl'):
                    model = ed.model[6:-4]
                elif ed.model.startswith('*'):
                    levelname = self.get_level_model_name()
                    model = '%s,%d' % (levelname, ed.modelindex - 1)
                elif ed.model.startswith('maps/') and ed.model.endswith('.bsp'):
                    model = ed.model[5:-4] + ',0'
                else:
                    print "WARNING: model missing for %r" % (ed.model,)
                    model = ""
                self.model_by_index[index] = model

            if model:
                frame = ed.frame
                org = map_vertex(ed.origin)
                ang = map_angles(ed.angles)
            else:
                frame = 0.0
                org = NULLVEC
                ang = NULLVEC
            yield [model,
                   frame,
                   org['x'], org['y'], org['z'],
                   ang['x'], ang['y'], ang['z'],
                   ]

    def get_snapshot(self):
        lightstyles = self.get_lightstyles(first=32)
        snapshot = [len(lightstyles)]
        snapshot += lightstyles
        for entry in self.enum_snapshot_models():
            snapshot += entry
        return snapshot


if __name__ == "__main__":
    srv = QuakeServer(sys.argv[1:])
    import pdb;pdb.set_trace()
    while True:
        time.sleep(0.1)
        srv.host_frame()

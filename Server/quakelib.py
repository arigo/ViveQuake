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


class StaticEntity(object):
    solid = lib.SOLID_NOT
    effects = 0

    def __init__(self, se):
        self.modelindex = se.modelindex
        self.model = ffi.string(se.model)
        self.frame = se.frame
        self.origin = tuple(se.origin)
        self.angles = tuple(se.angles)


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
        self.client = None

    def setup(self, playername="quake_player"):
        for n in range(4):
            if n == 1:
                self.spawn_client(playername=playername)
            if n == 2:
                self.cmd("spawn")
            time.sleep(0.1)
            self.host_frame()

    def spawn_client(self, clientnum=0, playername=None):
        assert 0 <= clientnum < lib.svs.maxclients
        self.client_ed = Edict(clientnum + 1)
        self.client = lib.svs.clients + clientnum
        self.qsocket = ffi.new("qsocket_t *")
        self.client.netconnection = self.qsocket
        lib.SV_ConnectClient(clientnum)
        if playername:
            n = min(len(playername), len(self.client.name)-1)
            for i in range(n):
                self.client.name[i] = playername[i]
            self.client.name[n] = '\x00'

    def cmd(self, string):
        lib.host_client = self.client
        lib.Cmd_ExecuteString(string, lib.src_client)

    def host_frame(self, forced_delay=None):
        next_time = time.time()
        delay = next_time - self.prev_time
        self.prev_time = next_time
        if forced_delay is not None:
            delay = forced_delay
        elif delay > 0.1:
            delay = 0.1
        #print "%.3f host frame" % delay
        lib.PQuake_Host_Frame(delay)

    def get_level_model_name(self):
        res = Edict(0).model
        assert res.startswith('maps/') and res.endswith('.bsp')
        return res[5:-4]

    def get_full_level_path(self):
        return Edict(0).model

    def get_player_start_position(self):
        for ed in edicts():
            if ed.classname == 'info_player_start':
                return ed.origin
        raise LookupError("'info_player_start' not found")

    def get_lightstyles(self, first=0):
        lightstyles = []
        for p in lib.sv.lightstyles[first : len(lib.sv.lightstyles)]:
            lightstyles.append(ffi.string(p) if p else "a")
        return lightstyles

    def get_precache_models(self):
        precaches = []
        for p in lib.sv.model_precache:
            if p == ffi.NULL:
                break
            s = ffi.string(p)
            if s and s != self.get_full_level_path():
                if not s.endswith('.spr'):   # XXX temporary
                    precaches.append(s)
        return precaches

    def enum_static_entities(self):
        n = lib.pquake_count_staticentities()
        for i in range(n):
            yield StaticEntity(lib.pquake_staticentities[i])

    def enum_snapshot_models(self):
        NULLVEC = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        SOLID2FLAGS = {lib.SOLID_NOT:     0x1000,
                       lib.SOLID_TRIGGER: 0x2000}
        #
        for ed in (list(self.enum_static_entities()) +
                   list(edicts(start=1))):
            index = int(ed.modelindex)
            try:
                if index <= 0:    # removed or invisible edict
                    model = ""
                else:
                    model = self.model_by_index[index]
            except KeyError:
                if ed.model == self.get_full_level_path():
                    model = '*0'
                else:
                    model = ed.model
                self.model_by_index[index] = model

            if model:
                frame = ed.frame
                # format of the 'flags': this contains ed.effects,
                # which is the EF_xxx flags defined in src/server.h;
                # it is or'ed with some custom-valued flags based on
                # SOLID_xxx.  Do not confuse these EF_xxx flags with
                # the ones stored in the model, returned through the
                # url path /model/xxx by server.py, which come from
                # EF_xxx in src/model.h.
                flags = SOLID2FLAGS.get(int(ed.solid), 0)
                flags |= (int(ed.effects) & 0xFFF)
                org = map_vertex(ed.origin)
                ang = map_angles(ed.angles)
            else:
                frame = 0.0
                flags = 0.0
                org = NULLVEC
                ang = NULLVEC
            yield [model, frame, flags,
                   org['x'], org['y'], org['z'],
                   ang['x'], ang['y'], ang['z'],
                   ]

    def get_snapshot(self):
        lightstyles = self.get_lightstyles(first=32)
        snapshot = [len(lightstyles)]
        snapshot += lightstyles

        snapshot.append(self.client_ed.weaponmodel or "")
        snapshot.append(self.client_ed.weaponframe)

        for entry in self.enum_snapshot_models():
            snapshot += entry
        return snapshot


if __name__ == "__main__":
    srv = QuakeServer(sys.argv[1:])
    srv.setup()
    n = 0
    while True:
        time.sleep(0.1)
        srv.host_frame()
        n += 1
        #if n == 5:
        #    import pdb;pdb.set_trace()

import struct, os
from cStringIO import StringIO


class QData(object):
    repr_flag = False

    def __init__(self, *args, **kwds):
        if args:
            self._rawdata = args[0]
            self._args = args[1:]
        self.__dict__.update(kwds)

    def __getattr__(self, attr):
        if attr == 'rawdata':
            try:
                return self._rawdata
            except AttributeError:
                f = StringIO()
                self.pack(f)
                return f.getvalue()
        if attr.startswith('_') or not hasattr(self, '_rawdata'):
            raise AttributeError, attr
        self.unpack(StringIO(self._rawdata), *self._args)
        del self._rawdata
        return getattr(self, attr)

    def __repr__(self):
        # hack!
        if not QData.repr_flag:
            self.force()
            QData.repr_flag = True
            try:
                items = []
                for name, fld in getattr(self.__class__, 'FIELDS', []):
                    items.append(name)
                keys = self.__dict__.keys()
                keys.sort()
                for name in keys:
                    if not name.startswith('_') and name not in items:
                        items.append(name)
                dpy = []
                for name in items:
                    value = self.__dict__[name]
                    if isinstance(value, str) and len(value) > 200:
                        value = repr(value)[:180] + '...'
                    else:
                        value = repr(value)
                    dpy.append('%s=%s' % (name, value))
                if not dpy and hasattr(self, '_rawdata'):
                    dpy.append('%d bytes' % (len(self._rawdata),))
            finally:
                QData.repr_flag = False
        elif hasattr(self, '_rawdata'):
            dpy = ['?']
        else:
            dpy = ['...']
        return '%s(%s)' % (self.__class__.__name__, ', '.join(dpy))

    def save(self, filename):
        data = self.rawdata
        f = file(filename, 'wb')
        f.write(data)
        f.close()

    def force(self):
        getattr(self, 'FORCE!', None)

    # default field-based implementation

    def unpack(self, f, *ignored):
        for name, fld in self.__class__.FIELDS:
            x = fld.read(f, self)
            setattr(self, name, x)

    def pack(self, f):
        temp = []
        for name, fld in self.__class__.FIELDS:
            x = getattr(self, name)
            temp.append(fld.write(f, x))
        for extra in temp:
            if extra:
                extra()

    def __getitem__(self, index):
        return self.list[index]

    def __len__(self):
        return len(self.list)


class FSignature:
    def __init__(self, expected):
        if isinstance(expected, int):
            expected = struct.pack("<i", expected)
        self.expected = expected
    def read(self, f, ctx):
        sig = f.read(len(self.expected))
        assert sig == self.expected, "bad signature: %r instead of %r" % (
            sig, self.expected)
        return sig
    def write(self, f, sig):
        assert sig == self.expected
        f.write(sig)

class FLump:
    def __init__(self, lumpcls, align=4):
        self.lumpcls = lumpcls
        self.align = align
    def read(self, f, ctx):
        ofs, size = struct.unpack("<ii", f.read(8))
        cur = f.tell()
        f.seek(ofs)
        data = f.read(size)
        f.seek(cur)
        assert len(data) == size, "premature end of file"
        return self.lumpcls(data, ctx)
    def write(self, f, lump):
        data = lump.rawdata
        p = f.tell()
        f.write(struct.pack("<ii", 0, 0))
        def patch():
            cur = f.tell()
            f.seek(p)
            f.write(struct.pack("<ii", cur, len(data)))
            f.seek(cur)
            f.write(data)
            f.write('\x00' * ((self.align-len(data)) % self.align))
        return patch

class FOfsArray:
    def __init__(self, itemcls, fixedlength=None):
        self.itemcls = itemcls
        self.fixedlength = fixedlength
    def read(self, f, ctx):
        result = []
        count = self.fixedlength
        if count is None:
            count, = struct.unpack("<i", f.read(4))
        ofslist = list(struct.unpack("<" + "i"*count, f.read(4*count)))
        cur = f.tell()
        f.seek(0, 2)
        ofslist.append(f.tell())
        for i in range(count):
            f.seek(ofslist[i])
            data = f.read(ofslist[i+1] - ofslist[i])
            result.append(self.itemcls(data, ctx, i))
        return result
    def write(self, f, lst):
        if self.fixedlength is None:
            f.write(struct.pack("<i", len(lst)))
        else:
            assert len(lst) == self.fixedlength
        hdrpos = f.tell()
        f.write(struct.pack("<i", 0) * len(lst))
        ofslist = []
        for x in lst:
            ofslist.append(f.tell())
            data = x.rawdata
            f.write(data)
        endpos = f.tell()
        f.seek(hdrpos)
        f.write(struct.pack("<" + "i"*len(lst), *ofslist))
        f.seek(endpos)

class FArray:
    def __init__(self, itemcls):
        self.itemcls = itemcls
    def read(self, f, ctx):
        result = []
        p = f.tell()
        f.seek(0, 2)
        end = f.tell()
        f.seek(p, 0)
        while f.tell() < end:
            item = self.itemcls()
            item.unpack(f)
            result.append(item)
        return result
    def write(self, f, value):
        for x in value:
            x.pack(f)

class FArrayOf:
    def __init__(self, fitem):
        self.fitem = fitem
    def read(self, f, ctx):
        result = []
        p = f.tell()
        f.seek(0, 2)
        end = f.tell()
        f.seek(p, 0)
        while f.tell() < end:
            result.append(self.fitem.read(f, ctx))
        return result
##    def write(self, f, value):
##        for x in value:
##            self.fitem.write(f, x)

class FCharPtr:
    def __init__(self, size):
        self.size = size
    def read(self, f, ctx):
        data = f.read(self.size)
        i = data.find('\x00')
        if i >= 0:
            data = data[:i]
        return data
    def write(self, f, data):
        assert len(data) < self.size
        f.write(data + '\x00' * (self.size - len(data)))

class FInt:
    def read(self, f, ctx):
        x, = struct.unpack("<i", f.read(4))
        return x
    def write(self, f, x):
        f.write(struct.pack("<i", x))

class FInt3b:
    def read(self, f, ctx):
        x, = struct.unpack("<i", f.read(3) + '\x00')
        return x
    def write(self, f, x):
        f.write(struct.pack("<i", x)[:3])

class FInt2b:
    def read(self, f, ctx):
        x, = struct.unpack("<h", f.read(2))
        return x
    def write(self, f, x):
        f.write(struct.pack("<h", x))

class FInt1b:
    def read(self, f, ctx):
        x, = struct.unpack("<b", f.read(1))
        return x
    def write(self, f, x):
        f.write(struct.pack("<b", x))

class FUShort:
    def read(self, f, ctx):
        x, = struct.unpack("<H", f.read(2))
        return x
    def write(self, f, x):
        f.write(struct.pack("<H", x))

class FUChar:
    def read(self, f, ctx):
        x, = struct.unpack("<B", f.read(1))
        return x
    def write(self, f, x):
        f.write(struct.pack("<B", x))

class FFloat:
    def read(self, f, ctx):
        x, = struct.unpack("<f", f.read(4))
        return x
    def write(self, f, x):
        f.write(struct.pack("<f", x))

class FVec3:
    def read(self, f, ctx):
        return struct.unpack("<fff", f.read(12))
    def write(self, f, (x, y, z)):
        f.write(struct.pack("<fff", x, y, z))

class FVec4:
    def read(self, f, ctx):
        return struct.unpack("<ffff", f.read(16))
    def write(self, f, (x, y, z, ofs)):
        f.write(struct.pack("<ffff", x, y, z, ofs))

class FEnum:
    def __init__(self, choices):
        self.choices = choices
    def read(self, f, ctx):
        x, = struct.unpack("<i", f.read(4))
        return self.choices[x]
    def write(self, f, value):
        x = self.choices.index(value)
        f.write(struct.pack("<i", x))

##class FTrivertx:
##    def read(self, f, ctx):
##        x, y, z, l = struct.unpack("<BBBB", f.read(4))
##        x = ctx.scale_origin[0] + x*ctx.scale[0]
##        y = ctx.scale_origin[1] + y*ctx.scale[1]
##        z = ctx.scale_origin[2] + z*ctx.scale[2]
##        return x, y, z, l
##    def write(self, f, (x, y, z, l)):
##        x = int((x - ctx.scale_origin[0]) / ctx.scale[0])
##        y = int((y - ctx.scale_origin[1]) / ctx.scale[1])
##        z = int((z - ctx.scale_origin[2]) / ctx.scale[2])
##        f.write(struct.pack("<BBBB", x, y, z, l))

# ____________________________________________________________


class QMipmap(QData):
    def unpack(self, f, texture, index):
        data = f.read()
        w = texture.width
        h = texture.height
        if not data:
            self.data24 = ''
            self.w = self.h = 0
            return
        if index == 0 and len(data) == 3*w*h:
            self.data24 = data
            self.w = w
            self.h = h
            return
        assert w % (1<<index) == h % (1<<index) == 0, "%dx%d >> %d" % (w, h, index)
        w >>= index
        h >>= index
        assert w*h == len(data)
        self.w = w
        self.h = h
        self.data = data
    def pack(self, f):
        if hasattr(self, 'data24'):
            assert self.w*self.h*3 == len(self.data24)
            f.write(self.data24)
        else:
            assert self.w*self.h == len(self.data)
            f.write(self.data)

QMipmap.Empty = QMipmap(w=0, h=0, data24='')

class QTexture(QData):
    FIELDS = [
        ('name',    FCharPtr(16)),
        ('width',   FInt()),
        ('height',  FInt3b()),
        ('gl_resolution', FInt1b()),
        ('mipmaps', FOfsArray(QMipmap, 4)),
        ]

class QTextures(QData):
    FIELDS = [
        ('list', FOfsArray(QTexture)),
        ]

class QTexinfo(QData):
    FIELDS = [
        ('s',       FVec4()),
        ('t',       FVec4()),
        ('miptex',  FInt()),
        ('flags',   FInt()),
        ]

class QTexinfos(QData):
    FIELDS = [
        ('list', FArray(QTexinfo)),
        ]

class QBspFace(QData):
    FIELDS = [
        ('plane_id', FUShort()),
        ('side', FUShort()),
        ('ledge_id', FInt()),
        ('ledge_num', FUShort()),
        ('texinfo_id', FUShort()),
        ('typelight', FUChar()),
        ('baselight', FUChar()),
        ('light0', FUChar()),
        ('light1', FUChar()),
        ('lightmap', FInt()),
        ]

class QBspFaces(QData):
    FIELDS = [
        ('list', FArray(QBspFace)),
        ]

class QBspEdge(QData):
    FIELDS = [
        ('vertex0', FUShort()),
        ('vertex1', FUShort()),
        ]

class QBspEdges(QData):
    FIELDS = [
        ('list', FArray(QBspEdge)),
        ]

class QBspModel(QData):
    FIELDS = [
        ('bound_min', FVec3()),
        ('bound_max', FVec3()),
        ('origin', FVec3()),
        ('node_id0', FInt()),
        ('node_id1', FInt()),
        ('node_id2', FInt()),
        ('node_id3', FInt()),
        ('numleafs', FInt()),
        ('face_id', FInt()),
        ('face_num', FInt()),
        ]

class QBspModels(QData):
    FIELDS = [
        ('list', FArray(QBspModel)),
        ]

class QListOfInt(QData):
    FIELDS = [
        ('list', FArrayOf(FInt())),
        ]

class QListOfVec3(QData):
    FIELDS = [
        ('list', FArrayOf(FVec3())),
        ]

class QBsp(QData):
    FIELDS = [
        ('signature', FSignature(29)),
        ('entities',  FLump(QData)),
        ('planes',  FLump(QData)),
        ('textures',  FLump(QTextures)),
        ('vertexes',  FLump(QListOfVec3)),
        ('visibility',  FLump(QData)),
        ('nodes',  FLump(QData)),
        ('texinfo',  FLump(QTexinfos)),
        ('faces',  FLump(QBspFaces)),
        ('lighting',  FLump(QData)),
        ('clipnodes',  FLump(QData)),
        ('leafs',  FLump(QData)),
        ('lface',   FLump(QData)),
        ('edges',   FLump(QBspEdges)),
        ('ledges',  FLump(QListOfInt)),
        ('models',  FLump(QBspModels)),
        ]

class QFrame:
##    FIELDS = [
##        ('bboxmin',        FTrivertx()),
##        ('bboxmax',        FTrivertx()),
##        ('name',           FCharPtr(16)),
##        ('v',              FArrayOf(FTrivertx())),
##        ]
    def __init__(self, name, v):
        self.name = name
        self.v = v

class QMdl(QData):
    FIELDS = [
        ('signature',      FSignature('IDPO')),
        ('version',        FSignature(6)),
        ('scale',          FVec3()),
        ('scale_origin',   FVec3()),
        ('boundingradius', FFloat()),
        ('eyeposition',    FVec3()),
        ('numskins_',      FInt()),
        ('skinwidth',      FInt()),
        ('skinheight',     FInt()),
        ('numverts_',      FInt()),
        ('numtris_',       FInt()),
        ('numframes_',     FInt()),
        ('synctype',       FEnum(['sync', 'rand'])),
        ('flags',          FInt()),
        ('size',           FFloat()),
        ]

    Normals = [
        (-0.525731, 0.000000, 0.850651),
        (-0.442863, 0.238856, 0.864188),
        (-0.295242, 0.000000, 0.955423),
        (-0.309017, 0.500000, 0.809017),
        (-0.162460, 0.262866, 0.951056),
        (0.000000, 0.000000, 1.000000),
        (0.000000, 0.850651, 0.525731),
        (-0.147621, 0.716567, 0.681718),
        (0.147621, 0.716567, 0.681718),
        (0.000000, 0.525731, 0.850651),
        (0.309017, 0.500000, 0.809017),
        (0.525731, 0.000000, 0.850651),
        (0.295242, 0.000000, 0.955423),
        (0.442863, 0.238856, 0.864188),
        (0.162460, 0.262866, 0.951056),
        (-0.681718, 0.147621, 0.716567),
        (-0.809017, 0.309017, 0.500000),
        (-0.587785, 0.425325, 0.688191),
        (-0.850651, 0.525731, 0.000000),
        (-0.864188, 0.442863, 0.238856),
        (-0.716567, 0.681718, 0.147621),
        (-0.688191, 0.587785, 0.425325),
        (-0.500000, 0.809017, 0.309017),
        (-0.238856, 0.864188, 0.442863),
        (-0.425325, 0.688191, 0.587785),
        (-0.716567, 0.681718, -0.147621),
        (-0.500000, 0.809017, -0.309017),
        (-0.525731, 0.850651, 0.000000),
        (0.000000, 0.850651, -0.525731),
        (-0.238856, 0.864188, -0.442863),
        (0.000000, 0.955423, -0.295242),
        (-0.262866, 0.951056, -0.162460),
        (0.000000, 1.000000, 0.000000),
        (0.000000, 0.955423, 0.295242),
        (-0.262866, 0.951056, 0.162460),
        (0.238856, 0.864188, 0.442863),
        (0.262866, 0.951056, 0.162460),
        (0.500000, 0.809017, 0.309017),
        (0.238856, 0.864188, -0.442863),
        (0.262866, 0.951056, -0.162460),
        (0.500000, 0.809017, -0.309017),
        (0.850651, 0.525731, 0.000000),
        (0.716567, 0.681718, 0.147621),
        (0.716567, 0.681718, -0.147621),
        (0.525731, 0.850651, 0.000000),
        (0.425325, 0.688191, 0.587785),
        (0.864188, 0.442863, 0.238856),
        (0.688191, 0.587785, 0.425325),
        (0.809017, 0.309017, 0.500000),
        (0.681718, 0.147621, 0.716567),
        (0.587785, 0.425325, 0.688191),
        (0.955423, 0.295242, 0.000000),
        (1.000000, 0.000000, 0.000000),
        (0.951056, 0.162460, 0.262866),
        (0.850651, -0.525731, 0.000000),
        (0.955423, -0.295242, 0.000000),
        (0.864188, -0.442863, 0.238856),
        (0.951056, -0.162460, 0.262866),
        (0.809017, -0.309017, 0.500000),
        (0.681718, -0.147621, 0.716567),
        (0.850651, 0.000000, 0.525731),
        (0.864188, 0.442863, -0.238856),
        (0.809017, 0.309017, -0.500000),
        (0.951056, 0.162460, -0.262866),
        (0.525731, 0.000000, -0.850651),
        (0.681718, 0.147621, -0.716567),
        (0.681718, -0.147621, -0.716567),
        (0.850651, 0.000000, -0.525731),
        (0.809017, -0.309017, -0.500000),
        (0.864188, -0.442863, -0.238856),
        (0.951056, -0.162460, -0.262866),
        (0.147621, 0.716567, -0.681718),
        (0.309017, 0.500000, -0.809017),
        (0.425325, 0.688191, -0.587785),
        (0.442863, 0.238856, -0.864188),
        (0.587785, 0.425325, -0.688191),
        (0.688191, 0.587785, -0.425325),
        (-0.147621, 0.716567, -0.681718),
        (-0.309017, 0.500000, -0.809017),
        (0.000000, 0.525731, -0.850651),
        (-0.525731, 0.000000, -0.850651),
        (-0.442863, 0.238856, -0.864188),
        (-0.295242, 0.000000, -0.955423),
        (-0.162460, 0.262866, -0.951056),
        (0.000000, 0.000000, -1.000000),
        (0.295242, 0.000000, -0.955423),
        (0.162460, 0.262866, -0.951056),
        (-0.442863, -0.238856, -0.864188),
        (-0.309017, -0.500000, -0.809017),
        (-0.162460, -0.262866, -0.951056),
        (0.000000, -0.850651, -0.525731),
        (-0.147621, -0.716567, -0.681718),
        (0.147621, -0.716567, -0.681718),
        (0.000000, -0.525731, -0.850651),
        (0.309017, -0.500000, -0.809017),
        (0.442863, -0.238856, -0.864188),
        (0.162460, -0.262866, -0.951056),
        (0.238856, -0.864188, -0.442863),
        (0.500000, -0.809017, -0.309017),
        (0.425325, -0.688191, -0.587785),
        (0.716567, -0.681718, -0.147621),
        (0.688191, -0.587785, -0.425325),
        (0.587785, -0.425325, -0.688191),
        (0.000000, -0.955423, -0.295242),
        (0.000000, -1.000000, 0.000000),
        (0.262866, -0.951056, -0.162460),
        (0.000000, -0.850651, 0.525731),
        (0.000000, -0.955423, 0.295242),
        (0.238856, -0.864188, 0.442863),
        (0.262866, -0.951056, 0.162460),
        (0.500000, -0.809017, 0.309017),
        (0.716567, -0.681718, 0.147621),
        (0.525731, -0.850651, 0.000000),
        (-0.238856, -0.864188, -0.442863),
        (-0.500000, -0.809017, -0.309017),
        (-0.262866, -0.951056, -0.162460),
        (-0.850651, -0.525731, 0.000000),
        (-0.716567, -0.681718, -0.147621),
        (-0.716567, -0.681718, 0.147621),
        (-0.525731, -0.850651, 0.000000),
        (-0.500000, -0.809017, 0.309017),
        (-0.238856, -0.864188, 0.442863),
        (-0.262866, -0.951056, 0.162460),
        (-0.864188, -0.442863, 0.238856),
        (-0.809017, -0.309017, 0.500000),
        (-0.688191, -0.587785, 0.425325),
        (-0.681718, -0.147621, 0.716567),
        (-0.442863, -0.238856, 0.864188),
        (-0.587785, -0.425325, 0.688191),
        (-0.309017, -0.500000, 0.809017),
        (-0.147621, -0.716567, 0.681718),
        (-0.425325, -0.688191, 0.587785),
        (-0.162460, -0.262866, 0.951056),
        (0.442863, -0.238856, 0.864188),
        (0.162460, -0.262866, 0.951056),
        (0.309017, -0.500000, 0.809017),
        (0.147621, -0.716567, 0.681718),
        (0.000000, -0.525731, 0.850651),
        (0.425325, -0.688191, 0.587785),
        (0.587785, -0.425325, 0.688191),
        (0.688191, -0.587785, 0.425325),
        (-0.955423, 0.295242, 0.000000),
        (-0.951056, 0.162460, 0.262866),
        (-1.000000, 0.000000, 0.000000),
        (-0.850651, 0.000000, 0.525731),
        (-0.955423, -0.295242, 0.000000),
        (-0.951056, -0.162460, 0.262866),
        (-0.864188, 0.442863, -0.238856),
        (-0.951056, 0.162460, -0.262866),
        (-0.809017, 0.309017, -0.500000),
        (-0.864188, -0.442863, -0.238856),
        (-0.951056, -0.162460, -0.262866),
        (-0.809017, -0.309017, -0.500000),
        (-0.681718, 0.147621, -0.716567),
        (-0.681718, -0.147621, -0.716567),
        (-0.850651, 0.000000, -0.525731),
        (-0.688191, 0.587785, -0.425325),
        (-0.587785, 0.425325, -0.688191),
        (-0.425325, 0.688191, -0.587785),
        (-0.425325, -0.688191, -0.587785),
        (-0.587785, -0.425325, -0.688191),
        (-0.688191, -0.587785, -0.425325),
        ]

    def BestNormal(cls, x, y, z):
        choices = [((x-nx)*(x-nx) + (y-ny)*(y-ny) + (z-nz)*(z-nz), i)
                   for i, (nx, ny, nz) in enumerate(cls.Normals)]
        return min(choices)[1]
    BestNormal = classmethod(BestNormal)

    def unpack(self, f):
        QData.unpack(self, f)
        self.skins = []
        for i in range(self.numskins_):
            skintype = f.read(4)
            assert skintype == '\x00'*4
            self.skins.append(QMipmap(w=self.skinwidth,
                                      h=self.skinheight,
                                      data=f.read(self.skinwidth*self.skinheight)))
        self.vertices = []
        for i in range(self.numverts_):
            onseam, s, t = struct.unpack("<iii", f.read(12))
            self.vertices.append((s, t, bool(onseam & 0x20)))
        self.triangles = []
        for i in range(self.numtris_):
            front, p1, p2, p3 = struct.unpack("<iiii", f.read(16))
            self.triangles.append((p1, p2, p3, bool(front)))
        self.frames = []
        for i in range(self.numframes_):
            frametype = f.read(4)
            assert frametype == '\x00'*4
            f.read(8)   # ignore bboxmin, bboxmax
            name = FCharPtr(16).read(f, None)
            v = []
            for i in range(self.numverts_):
                x, y, z, l = struct.unpack("BBBB", f.read(4))
                x = self.scale_origin[0] + x*self.scale[0]
                y = self.scale_origin[1] + y*self.scale[1]
                z = self.scale_origin[2] + z*self.scale[2]
                v.append((x, y, z, l))
            self.frames.append(QFrame(name, v))

    def fix(self):
        allv = []
        for frame in self.frames:
            allv += frame.v
        bboxmin, bboxmax = getbbox(allv)
        self.scale = ((bboxmax[0] - bboxmin[0]) / 255.0,
                      (bboxmax[1] - bboxmin[1]) / 255.0,
                      (bboxmax[2] - bboxmin[2]) / 255.0)
        self.scale_origin = bboxmin
        #self.boundingradius = XXX
        self.numskins_ = len(self.skins)
        self.numverts_ = len(self.vertices)
        self.numtris_ = len(self.triangles)
        self.numframes_ = len(self.frames)

    def pack(self, f):
        self.fix()
        QData.pack(self, f)
        for skin in self.skins:
            f.write('\x00'*4)
            assert skin.w == self.skinwidth
            assert skin.h == self.skinheight
            skin.pack(f)
        for s, t, onseam in self.vertices:
            f.write(struct.pack("<iii", onseam and 0x20 or 0, s, t))
        for p1, p2, p3, front in self.triangles:
            f.write(struct.pack("<iiii", front, p1, p2, p3))
        def packv((x, y, z, l)):
            x = int((x - self.scale_origin[0]) / self.scale[0])
            y = int((y - self.scale_origin[1]) / self.scale[1])
            z = int((z - self.scale_origin[2]) / self.scale[2])
            assert 0 <= x <= 255
            assert 0 <= y <= 255
            assert 0 <= z <= 255
            return struct.pack("BBBB", x, y, z, l)
        for frame in self.frames:
            f.write('\x00'*4)
            assert len(frame.v) == self.numverts_
            bboxmin, bboxmax = getbbox(frame.v)
            f.write(packv(bboxmin + (0,)))
            f.write(packv(bboxmax + (0,)))
            FCharPtr(16).write(f, frame.name)
            f.writelines(map(packv, frame.v))

def getbbox(v):
    xs, ys, zs, ls = zip(*v)
    return ((min(xs), min(ys), min(zs)),
            (max(xs), max(ys), max(zs)))


class QPakEntry(QData):
    FIELDS = [
        ('name',      FCharPtr(56)),
        ('ofs',       FInt()),
        ('size',      FInt()),
        ]

class QPak(QData):
    FIELDS = [
        ('signature', FSignature('PACK')),
        ]
    align = 4

    def unpack(self, f):
        QData.unpack(self, f)
        dirpos, dirsize = struct.unpack("<ii", f.read(8))
        dirlen = dirsize / 64
        f.seek(dirpos)
        self.content = {}
        entries = [QPakEntry(f.read(64)) for i in range(dirlen)]
        self._names = [entry.name for entry in entries]
        for entry in entries:
            ext = entry.name[entry.name.rfind('.'):]
            cls = GUESS_CLASS.get(ext, QData)
            f.seek(entry.ofs)
            data = f.read(entry.size)
            self.content[entry.name] = cls(data)
    def pack(self, f):
        QData.pack(self, f)
        new = self.content.copy()
        names = []
        for name in self._names:
            if name in self.content:
                del new[name]
                names.append(name)
        names += new.keys()
        self._names = names
        hdrpos = f.tell()
        f.write(struct.pack("<ii", 0, 0))
        entries = []
        for name in names:
            x = self.content[name]
            data = x.rawdata
            entries.append(QPakEntry(name=name, ofs=f.tell(), size=len(data)))
            f.write(data)
            f.write('\x00' * ((self.align-len(data)) % self.align))
        dirpos = f.tell()
        for entry in entries:
            f.write(entry.rawdata)
        f.seek(hdrpos)
        f.write(struct.pack("<ii", dirpos, len(entries) * 64))


GUESS_CLASS = {
    '.pak': QPak,
    '.bsp': QBsp,
    '.mdl': QMdl,
    }

def load(filename):
    ext = filename[filename.rfind('.'):]
    cls = GUESS_CLASS.get(ext, QData)
    data = file(filename, 'rb').read()
    return cls(data)


if __name__ == '__main__':
    import sys, readline
    p = load('id1/pak0.pak')
    os.environ['PYTHONINSPECT'] = '1'

    for _src in sys.argv[1:]:
        _data = p.content[_src]                  # e.g. 'maps/e1m1.bsp'
        globals()[os.path.splitext(_src)[1][1:]] = _data   # e.g. 'bsp'

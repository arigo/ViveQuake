import md5
import qdata
import array


VERSION = 5

PAK0 = qdata.load('id1/pak0.pak')

_textures_by_name = {}


def map_vertex((x, y, z)):
    # swap y and z: in Quake, z is "up", but that's the role of y
    # in Unity (and presumably others).  Moreover, this makes a
    # mirror image, which also seems to be needed.
    return {'x': x, 'y': z, 'z': y}

def map_angles((pitch, yaw, roll)):
    # (pitch, yaw, roll) in degrees
    return {'x': pitch, 'y': yaw, 'z': roll}


def load_palette():
    palettelmp = PAK0.content['gfx/palette.lmp']
    r_palette = []
    for i in range(256):
        rgb = palettelmp.rawdata[i*3:i*3+3]
        r_palette.append({'r': ord(rgb[0]),
                          'g': ord(rgb[1]),
                          'b': ord(rgb[2]),
                          'a': 255})
    return r_palette


def load_level(levelname, model_index=0):
    bsp = PAK0.content['maps/%s.bsp' % (levelname,)]
    result = load_bsp_model(bsp, bsp.models[model_index])

    result['palette'] = load_palette()

    # static lights are the ones without a 'targetname'
    r_lights = []
    for entity in qdata.parse_entities(bsp.entities.rawdata):
        if (entity.get('classname', '').startswith('light')
                and not entity.get('targetname')):
            r_lights.append(load_light(entity))
    result['lights'] = r_lights

    return result


def load_light(entity):
    e_light = entity.get('light', 200)
    result = {
        'origin': map_vertex(qdata.parse_vec3(entity['origin'])),
        'light': float(e_light),
    }
    if entity.get('style', 0) != 0:
        result['style'] = int(entity['style'])
    return result


def load_bsp(bsp_name, model_index):
    bsp = PAK0.content['maps/%s.bsp' % (bsp_name,)]
    return load_bsp_model(bsp, bsp.models[model_index])


def load_bsp_model(bsp, model):
    r_vertices = []
    r_uvs = []
    r_normals = []

    _vertex_cache = {}
    def get_vertex(vec3, norm3, u, v):
        key = (vec3, norm3, round(u, 3), round(v, 3))
        try:
            result = _vertex_cache[key]
        except KeyError:
            result = len(r_vertices)
            r_vertices.append(map_vertex(vec3))
            r_uvs.append({'x': u, 'y': v})
            r_normals.append(map_vertex(norm3))
            _vertex_cache[key] = result
        return result

    vertexes = bsp.vertexes.list
    edges = bsp.edges.list
    ledges = bsp.ledges.list
    used_textures = {}

    r_faces = []
    for face in bsp.faces.list[model.face_id : model.face_id + model.face_num]:
        vnum = face.ledge_num
        vlist0 = []
        vlist1 = []
        for lindex in range(face.ledge_id, face.ledge_id + face.ledge_num):
            eindex = ledges[lindex]
            edge = edges[abs(eindex)]
            v0, v1 = edge.vertex0, edge.vertex1
            if eindex < 0:
                v0, v1 = v1, v0
            vlist0.append(v0)
            vlist1.append(v1)
        assert vlist0[1:] + vlist0[:1] == vlist1

        texinfo = bsp.texinfo[face.texinfo_id]
        s4 = texinfo.s
        t4 = texinfo.t
        texid = texinfo.miptex
        tex = bsp.textures[texid]
        i_width = 1.0 / tex.width
        i_height = 1.0 / tex.height
        normal = bsp.planes[face.plane_id].normal
        side = 1.0 if face.side == 0 else -1.0
        normal = (side * normal[0], side * normal[1], side * normal[2])
        r_v = []
        for k, vindex in enumerate(vlist0):
            v = vertexes[vindex]
            s = (v[0] * s4[0] + v[1] * s4[1] + v[2] * s4[2] + s4[3]) * i_width
            t = (v[0] * t4[0] + v[1] * t4[1] + v[2] * t4[2] + t4[3]) * i_height
            r_v.append(get_vertex(v, normal, s, t))

        texnum = used_textures.setdefault(texid, len(used_textures))
        r_faces.append({'v': r_v, 't': texnum})

    r_texturenames = []
    used_textures = used_textures.items()
    used_textures.sort(key = lambda (tid, num): num)
    for texid, texnum in used_textures:
        tex = bsp.textures[texid]
        assert tex.width == tex.mipmaps[0].w
        assert tex.height == tex.mipmaps[0].h
        hx = _get_texture_key(tex.mipmaps[0])
        assert texnum == len(r_texturenames)
        r_texturenames.append(hx)

    #print len(_vertex_cache)
    return {
        'frames': [{'v': r_vertices, 'n': r_normals}],
        'uvs': r_uvs,
        'faces': r_faces,
        'texturenames': r_texturenames,
        }


def load_texture(hx):
    mipmap = _textures_by_name[hx]
    r_data = mipmap.data.encode('base64')
    return {'width': mipmap.w, 'height': mipmap.h, 'data': r_data}

def _get_texture_key(mipmap):
    try:
        return mipmap._hx_key
    except AttributeError:
        key = '%d %d %s' % (mipmap.w, mipmap.h, mipmap.data)
        hx = md5.md5(key).hexdigest()
        mipmap._hx_key = hx
        _textures_by_name.setdefault(hx, mipmap)
        return hx


def load_model(modelname):
    mdl = PAK0.content['progs/%s.mdl' % (modelname,)]

    i_width = 1.0 / mdl.skinwidth
    i_height = 1.0 / mdl.skinheight
    expanded = {}      # {(mdl_vertex_index, facesfront): r_vertex_index}
    compressed = []    # list of mdl_vertex_index, indexed by r_vertex_index

    r_uvs = []
    r_faces = []
    for tri in mdl.triangles:
        r_v = []
        facesfront = tri[3]
        for j in range(3):
            try:
                vindex = expanded[tri[j], facesfront]
            except KeyError:
                s, t, on_seam = mdl.vertices[tri[j]]
                if on_seam and not facesfront:
                    s += mdl.skinwidth // 2
                vindex = len(compressed)
                compressed.append(tri[j])
                r_uvs.append({'x': s * i_width, 'y': t * i_height})
                expanded[tri[j], facesfront] = vindex
            r_v.append(vindex)
        #if not facesfront:
        #    r_v[1], r_v[2] = r_v[2], r_v[1]
        r_faces.append({'v': r_v, 't': 0})

    r_frames = []
    for frame in mdl.frames:
        r_vertices = []
        r_normals = []
        for mdl_vindex in compressed:
            x, y, z, n = frame.v[mdl_vindex]
            r_vertices.append(map_vertex((x, y, z)))
            r_normals.append(map_vertex(mdl.Normals[n]))
        r_frames.append({'v': r_vertices, 'n': r_normals})

    assert mdl.skins[0].w == mdl.skinwidth
    assert mdl.skins[0].h == mdl.skinheight
    r_texturenames = [_get_texture_key(mdl.skins[0])]

    result = {
        'frames': r_frames,
        'uvs': r_uvs,
        'faces': r_faces,
        'texturenames': r_texturenames,
        }
    if mdl.flags & 8:        # EF_ROTATE
        result['autorotate'] = 1

    return result


if __name__ == '__main__':
    import pprint
    m1 = load_level('e1m1')
    pprint.pprint(m1['lights'])
    #pprint.pprint(load_texture(m1['texturenames'][0]))
    #pprint.pprint(load_model('dog'))

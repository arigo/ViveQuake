import md5
import qdata
import array


MAPDATA_VERSION = 13

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

    r_lights = []
    for entity in qdata.parse_entities(bsp.entities.rawdata):
        if entity.get('classname', '').startswith('light'):
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

        vlist0 = [vertexes[vindex] for vindex in vlist0]
        if tex.name.startswith('sky'):
            vlistlist = []
            for vtri in triangulate(vlist0):
                explode_into_smaller_faces(vtri, vlistlist)
        else:
            vlistlist = [vlist0]

        i_width = 1.0 / tex.width
        i_height = 1.0 / tex.height
        normal = bsp.planes[face.plane_id].normal
        side = 1.0 if face.side == 0 else -1.0
        normal = (side * normal[0], side * normal[1], side * normal[2])
        texnum = used_textures.setdefault(texid, len(used_textures))
        for vlist in vlistlist:
            r_v = []
            for k, v in enumerate(vlist):
                s = v[0] * s4[0] + v[1] * s4[1] + v[2] * s4[2] + s4[3]
                t = v[0] * t4[0] + v[1] * t4[1] + v[2] * t4[2] + t4[3]
                r_v.append(get_vertex(v, normal, s * i_width, t * i_height))
            r_faces.append({'v': r_v, 't': texnum})

    r_texturenames = []
    used_textures = used_textures.items()
    used_textures.sort(key = lambda (tid, num): num)
    for texid, texnum in used_textures:
        tex = bsp.textures[texid]
        assert tex.width == tex.mipmaps[0].w
        assert tex.height == tex.mipmaps[0].h
        if tex.name.startswith('sky'):
            extra = 'sky'
        elif tex.name.startswith('*'):
            extra = 'water'
        else:
            extra = None
        hx = _get_texture_key(tex.mipmaps[0], extra=extra)
        assert texnum == len(r_texturenames)
        r_texturenames.append(hx)

    #print len(_vertex_cache)
    return {
        'frames': [{'a': [{'v': r_vertices, 'n': r_normals}]}],
        'uvs': r_uvs,
        'faces': r_faces,
        'texturenames': r_texturenames,
        }

def triangulate(vlist):
    # This logic is for the client, where the sky is typically rendered
    # with a shader.  This shader assumes the sky is made of small
    # enough triangles.
    cx = cy = cz = 0.0
    for (x, y, z) in vlist:
        cx += x
        cy += y
        cz += z
    cx /= len(vlist)
    cy /= len(vlist)
    cz /= len(vlist)
    center = (cx, cy, cz)
    v_prev = vlist[-1]
    for v_next in vlist:
        yield [center, v_prev, v_next]
        v_prev = v_next

def _dist2((x1, y1, z1), (x2, y2, z2)):
    x2 -= x1
    y2 -= y1
    z2 -= z1
    return x2 * x2 + y2 * y2 + z2 * z2

def explode_into_smaller_faces(vlist, vlistlist):
    v1, v2, v3 = vlist
    MAX = 5000
    if _dist2(v1, v2) > MAX or _dist2(v2, v3) > MAX or _dist2(v1, v3) > MAX:
        c1 = ((v2[0]+v3[0])*0.5, (v2[1]+v3[1])*0.5, (v2[2]+v3[2])*0.5)
        c2 = ((v1[0]+v3[0])*0.5, (v1[1]+v3[1])*0.5, (v1[2]+v3[2])*0.5)
        c3 = ((v1[0]+v2[0])*0.5, (v1[1]+v2[1])*0.5, (v1[2]+v2[2])*0.5)
        explode_into_smaller_faces([v1, c3, c2], vlistlist)
        explode_into_smaller_faces([v2, c1, c3], vlistlist)
        explode_into_smaller_faces([v3, c2, c1], vlistlist)
        explode_into_smaller_faces([c1, c2, c3], vlistlist)
    else:
        vlistlist.append(vlist)


def load_texture(hx):
    mipmap, extra = _textures_by_name[hx]
    r_data = mipmap.data.encode('base64')
    result = {'width': mipmap.w, 'height': mipmap.h, 'data': r_data}
    if extra:
        result['effect'] = extra
    return result

def _get_texture_key(mipmap, extra=None):
    try:
        return mipmap._hx_key
    except AttributeError:
        key = '%r %d %d %s' % (extra, mipmap.w, mipmap.h, mipmap.data)
        hx = md5.md5(key).hexdigest()
        mipmap._hx_key = hx
        _textures_by_name.setdefault(hx, (mipmap, extra))
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

    def get_frame(frame, time=1):
        r_vertices = []
        r_normals = []
        for mdl_vindex in compressed:
            x, y, z, n = frame.v[mdl_vindex]
            r_vertices.append(map_vertex((x, y, z)))
            r_normals.append(map_vertex(mdl.Normals[n]))
        return {'v': r_vertices, 'n': r_normals, 'time': time}

    for frame_or_group in mdl.frames:
        if isinstance(frame_or_group, qdata.QFrameGroup):
            framedata = []
            for fr, tm in zip(frame_or_group.frames, frame_or_group.times):
                framedata.append(get_frame(fr, tm))
        else:
            framedata = [get_frame(frame_or_group)]
        r_frames.append({'a': framedata})

    assert mdl.skins[0].w == mdl.skinwidth
    assert mdl.skins[0].h == mdl.skinheight
    r_texturenames = [_get_texture_key(mdl.skins[0])]

    return {
        'frames': r_frames,
        'uvs': r_uvs,
        'faces': r_faces,
        'texturenames': r_texturenames,
        'flags': mdl.flags,  # EF_xxx flags from src/model.h (not src/server.h!)
        }


if __name__ == '__main__':
    import pprint
    m1 = load_model('flame')
    #m1 = load_level('start')
    #pprint.pprint(m1['lights'])
    #pprint.pprint(load_texture(m1['texturenames'][0]))
    #pprint.pprint(load_model('dog'))

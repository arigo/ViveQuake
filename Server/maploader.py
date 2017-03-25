import qdata
import array


def map_vertex((x, y, z)):
    # swap y and z: in Quake, z is "up", but that's the role of y
    # in Unity (and presumably others).  Moreover, this makes a
    # mirror image, which also seems to be needed.
    return {'x': x, 'y': z, 'z': y}


def load_map(levelname):
    p = qdata.load('id1/pak0.pak')
    bsp = p.content['maps/%s.bsp' % (levelname,)]
    palettelmp = p.content['gfx/palette.lmp']

    r_vertices = []
    r_uvs = []

    _vertex_cache = {}
    def get_vertex(vec3, u, v):
        key = (vec3, round(u, 3), round(v, 3))
        try:
            result = _vertex_cache[key]
        except KeyError:
            result = len(r_vertices)
            r_vertices.append(map_vertex(vec3))
            r_uvs.append({'x': u, 'y': v})
            _vertex_cache[key] = result
        return result

    vertexes = bsp.vertexes.list
    edges = bsp.edges.list
    ledges = bsp.ledges.list
    model = bsp.models[0]
    active_textures = set()

    r_faces = []
    r_textures = []
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
        r_v = []
        for k, vindex in enumerate(vlist0):
            v = vertexes[vindex]
            s = (v[0] * s4[0] + v[1] * s4[1] + v[2] * s4[2] + s4[3]) * i_width
            t = (v[0] * t4[0] + v[1] * t4[1] + v[2] * t4[2] + t4[3]) * i_height
            r_v.append(get_vertex(v, s, t))

        active_textures.add(texid)
        r_faces.append({'v': r_v, 't': texid})

    r_textures = [None] * (max(active_textures) + 1)
    for texid in active_textures:
        tex = bsp.textures[texid]
        r_data = tex.mipmaps[0].data.encode('base64')
        r_textures[texid] = {'width': tex.width, 'height': tex.height,
                             'data': r_data}

    r_palette = []
    for i in range(256):
        rgb = palettelmp.rawdata[i*3:i*3+3]
        r_palette.append({'r': ord(rgb[0]),
                          'g': ord(rgb[1]),
                          'b': ord(rgb[2]),
                          'a': 255})

    #print len(_vertex_cache)
    return {
        'vertices': r_vertices,
        'uvs': r_uvs,
        'faces': r_faces,
        'textures': r_textures,
        'palette': r_palette,
        }


if __name__ == '__main__':
    import pprint
    pprint.pprint(load_map('e1m1'))

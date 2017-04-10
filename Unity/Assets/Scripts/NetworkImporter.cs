using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.RegularExpressions;
using System.Threading;
using UnityEngine;
using UnityEngine.Networking;
using WebSocketSharp;


[Serializable]
public class QFace
{
    public int[] v;
    public int t;               /* texture index */
}

[Serializable]
public class QTexture
{
    public int width, height;
    public string data;
    public string effect;
}

[Serializable]
public class QFrame
{
    public Vector3[] v;   /* vertices position */
    public Vector3[] n;   /* list of normals, same length */
    public float time;

    public Mesh m_mesh;
}

[Serializable]
public class QFrameGroup
{
    public QFrame[] a;
}

[Serializable]
public class QLight
{
    public Vector3 origin;
    public float light;
    public int style;
}

[Serializable]
public class QModel
{
    public QFrameGroup[] frames;
    public Vector2[] uvs;
    public QFace[] faces;
    public QTexture[] skins;
    public int flags;            // see EF_XXX here

    public Material[] m_materials;

    /* these are the EF_xxx coming from 'srv/model.h'. */
    public const int EF_ROCKET = 1;
    public const int EF_ROTATE = 8;
}

[Serializable]
public class QTreeNode
{
    public Vector4 plane;
    public int front = 0;
    public int back = 0;
}

[Serializable]
public class QTreeLeaf
{
    public int type;
    public byte sndwater = 0, sndsky = 0, sndslime = 0, sndlava = 0;
}

[Serializable]
public class QLevel
{
    public QModel[] models;
    public int liquid_model;
    public Color32[] palette;
    public QTexture[] textures;
    public QLight[] lights;
    public QTreeNode[] bspnodes;
    public QTreeLeaf[] bspleafs;
}

[Serializable]
public class QHello
{
    public int version;
    public string level;
    public Vector3 start_pos;
    public string[] lightstyles;
    public string[] precache_models;
}

public struct SnapEntry
{
    public float f;
    public string s;
    public int i { get { return (int)f; } }

    public SnapEntry(float _f, string _s)
    {
        f = _f;
        s = _s;
    }

    /* the 'flags' argument is a combination of SOLID_xxx and the EF_xxx
     * coming from 'srv/server.h'. */
    public const int SOLID_NOT     = 0x1000;
    public const int SOLID_TRIGGER = 0x2000;
}

public class DynamicLight
{
    public QLight qlight;
    public Light component;
    public float light_factor;

    public DynamicLight(QLight m_qlight) { qlight = m_qlight; }
}


public class NetworkImporter : MonoBehaviour {

    public string baseUrl = "192.168.0.10:8000";
    const int WEBSOCK_VERSION = 4;

    public GameObject worldObject, liquidObject;
    public Material worldMaterial;
    public Material skyMaterial;
    public Material waterMaterial;
    public QuakeEntity entityPrefab;
    public Light lightPrefab;
    public ParticleSystem[] particleSystems;
    public GameObject weaponController;
    public WaterScreenScript[] blurEffects;
    public Color[] blurColor;
    public Material uniformScreenTint;

    QHello level_info;
    QLevel world;
    bool worldReady;
    Dictionary<string, QModel> models;
    WebSocket ws;
    volatile SnapEntry[] currentUpdateMessage;
    SnapEntry[] workUpdateMessage;
    List<DynamicLight> varying_lights;
    string[] lightstyles;
    string current_weapon_model = "";
    QuakeEntity[] entities;
    QuakeEntity weapon_entity;
    Transform headset, playArea;
    Color uniformFadingColor;


    private void Start()
    {
        entities = new QuakeEntity[0];
        varying_lights = new List<DynamicLight>();

        StartCoroutine(GetHelloWorld().GetEnumerator());
    }

    void RemoveOldCachedFiles()
    {
        string localPath = Application.persistentDataPath;
        Regex r1 = new Regex(".*[\\\\/]([0-9]+),[^\\\\/]+$");
        foreach (string filename in System.IO.Directory.GetFiles(localPath))
        {
            Match match = r1.Match(filename);
            if (match.Success && match.Groups[1].Value != ("" + level_info.version))
            {
                Debug.Log("Removing old cached file: " + filename);
                System.IO.File.Delete(filename);
            }
        }
    }

    IEnumerable DownloadJson(string path, object obj, bool enable_cache=true)
    {
        string rawstring = null;
        string localPath = null;
        bool store_cache = false;
        Debug.Log(path);

        if (enable_cache)
        {
            localPath = Application.persistentDataPath + "/" + level_info.version + path.Replace("/", ",");
            if (System.IO.File.Exists(localPath))
                rawstring = System.IO.File.ReadAllText(localPath);
            else
                store_cache = true;
        }

        if (rawstring == null)
        {
            UnityWebRequest www = UnityWebRequest.Get("http://" + baseUrl + path);
            yield return www.Send();
            if (www.isError)
                throw new ApplicationException(path + ": " + www.error);

            rawstring = www.downloadHandler.text;
        }

        JsonUtility.FromJsonOverwrite(rawstring, obj);

        if (store_cache)
        {
            System.IO.File.WriteAllText(localPath, rawstring);
            Debug.Log("Downloaded and cached file: " + localPath);
        }
    }

    IEnumerable GetHelloWorld()
    {
        level_info = new QHello();
        foreach (var x in DownloadJson("/hello", level_info, false))
            yield return x;

        RemoveOldCachedFiles();

        Debug.Log("Loading level " + level_info.level);
        lightstyles = level_info.lightstyles;

        world = new QLevel();
        foreach (var x in DownloadJson("/level/" + level_info.level, world))
            yield return x;

        Material[] mat = new Material[world.textures.Length];
        for (int i = 0; i < world.textures.Length; i++)
            mat[i] = ImportTexture(world.textures[i]);

        foreach (var model in world.models)
        {
            ImportMeshes(model, mat);
        }

        models = new Dictionary<string, QModel>();
        for (int i = 0; i < world.models.Length; i++)
            models["*" + i] = world.models[i];

        foreach (var model_name in level_info.precache_models)
            if (!models.ContainsKey(model_name))
                foreach (var x in ImportModel(model_name))
                    yield return x;

        /* now we should be done with all the DownloadJson() */

        LoadLights();
        LoadEntity(worldObject, world.models[0]);
        if (world.liquid_model != 0)
            LoadEntity(liquidObject, world.models[world.liquid_model]);

        workUpdateMessage = new SnapEntry[0];
        ws = new WebSocket("ws://" + baseUrl + "/websock/" + WEBSOCK_VERSION);
        ws.OnMessage += (sender, e) => AsyncDecompressMsg(e.RawData);
        ws.OnError += (sender, e) => Debug.LogError("WebSocket error: " + e.Message);
        ws.ConnectAsync();

        /* disable all my children when the level is ready */
        for (int i = 0; i < transform.childCount; i++)
            transform.GetChild(i).gameObject.SetActive(false);
        headset = VRTK.VRTK_SharedMethods.AddCameraFade();
        playArea = VRTK.VRTK_DeviceFinder.PlayAreaTransform();
        playArea.position = worldObject.transform.TransformVector(level_info.start_pos);
    }

    void AsyncDecompressMsg(byte[] data)
    {
        SnapEntry[] msg = workUpdateMessage;
        int msgIndex = 0, srcIndex = 0;
        int header = 0;

        while (true)
        {
            if ((msgIndex & 7) == 0)
            {
                if (srcIndex == data.Length)
                    break;
                header = data[srcIndex++];

                if (msgIndex == msg.Length)
                {
                    Array.Resize<SnapEntry>(ref workUpdateMessage, msgIndex + 8);
                    msg = workUpdateMessage;
                }
            }

            if ((header & 1) != 0)
            {
                if (data[srcIndex] == 0xff && data[srcIndex + 1] == 0xc0)
                {
                    /* a NaN header, meaning we get a string */
                    int length = data[srcIndex + 2];
                    string txt = System.Text.Encoding.UTF8.GetString(
                        data, srcIndex + 3, length);
                    srcIndex += 3 + length;
                    msg[msgIndex] = new SnapEntry(0, txt);
                }
                else
                {
                    byte[] four_bytes = new byte[4];
                    Array.Copy(data, srcIndex, four_bytes, 0, 4);
                    srcIndex += 4;
                    if (System.BitConverter.IsLittleEndian)
                        Array.Reverse(four_bytes);
                    float f = System.BitConverter.ToSingle(four_bytes, 0);
                    msg[msgIndex] = new SnapEntry(f, null);
                }
            }
            header >>= 1;
            msgIndex++;
        }

        SnapEntry[] msg_copy = new SnapEntry[msg.Length];
        Array.Copy(msg, msg_copy, msg.Length);
        currentUpdateMessage = msg_copy;   /* volatile, grabbed in Update */
    }

    private void OnApplicationQuit()
    {
        if (ws != null)
        {
            ws.CloseAsync();
            ws = null;
        }
    }

    Texture2D ImportSingleTexture(Color32[] palette, byte[] input_data, int width, int height, 
                                  int scanline, int offset)
    {
        Color32[] colors = new Color32[width * height];
        for (int y = 0; y < height; y++)
        {
            int base_src = offset + y * scanline;
            int base_dst = y * width;
            for (int x = 0; x < width; x++)
                colors[base_dst + x] = palette[input_data[base_src + x]];
        }

        Texture2D tex2d = new Texture2D(width, height);
        tex2d.SetPixels32(colors);
        tex2d.filterMode = FilterMode.Bilinear;
        tex2d.Apply();
        return tex2d;
    }

    Material ImportTexture(QTexture texinfo)
    {
        byte[] input_data = Convert.FromBase64String(texinfo.data);
        Material mat;
        Color32[] palette = world.palette;

        if (texinfo.effect == "sky")
        {
            int w2 = texinfo.width / 2;

            /* the right half */
            Texture2D tex0 = ImportSingleTexture(palette, input_data, w2, texinfo.height, texinfo.width, w2);

            /* the left half */
            Color32[] palette_with_alpha = new Color32[256];
            palette_with_alpha[0] = new Color32(0, 0, 0, 0);
            for (int i = 1; i < 256; i++)
                palette_with_alpha[i] = palette[i];
            Texture2D tex1 = ImportSingleTexture(palette_with_alpha, input_data, w2, texinfo.height, texinfo.width, 0);

            mat = Instantiate(skyMaterial);
            mat.SetTexture("_MainTex", tex0);
            mat.SetTexture("_ExtraTex", tex1);
        }
        else
        {
            Texture2D tex2d = ImportSingleTexture(palette, input_data, texinfo.width, texinfo.height, texinfo.width, 0);
            if (texinfo.effect == "water")
                mat = Instantiate(waterMaterial);
            else
                mat = Instantiate(worldMaterial);

            mat.SetTexture("_MainTex", tex2d);
        }
        return mat;
    }

    IEnumerable ImportModel(string model_name)
    {
        QModel model = new QModel();
        foreach (var x in DownloadJson("/model/" + model_name, model))
            yield return x;

        Material[] mat = new Material[model.skins.Length];
        for (int i = 0; i < model.skins.Length; i++)
            mat[i] = ImportTexture(model.skins[i]);

        ImportMeshes(model, mat);
        models[model_name] = model;
    }

    void ImportMeshes(QModel model, Material[] materials)
    {
        int num_textures = materials.Length;

        int[] countTriangles = new int[num_textures];
        int[] submeshes = new int[num_textures];
        for (int i = 0; i < num_textures; i++)
            submeshes[i] = -1;

        int num_submeshes = 0;
        foreach (QFace face in model.faces)
        {
            if (submeshes[face.t] == -1)
                submeshes[face.t] = num_submeshes++;
            countTriangles[face.t] += face.v.Length - 2;
        }

        Material[] submaterials = new Material[num_submeshes];
        int[][] triangles = new int[num_submeshes][];
        for (int i = 0; i < num_textures; i++)
            if (submeshes[i] >= 0)
            {
                submaterials[submeshes[i]] = materials[i];
                triangles[submeshes[i]] = new int[countTriangles[i] * 3];
                Debug.Assert(countTriangles[i] > 0);
            }
        model.m_materials = submaterials;

        for (int i = 0; i < model.frames.Length; i++)
        {
            for (int j = 0; j < model.frames[i].a.Length; j++)
            {
                QFrame frame = model.frames[i].a[j];
                frame.m_mesh = ImportMesh(model, frame, triangles, submeshes);
            }
        }
    }

    Mesh ImportMesh(QModel model, QFrame frame, int[][] triangles, int[] submeshes)
    {
        /* note: this returns a new Mesh, computed independently, for each frame */

        int[] bb = new int[triangles.Length];
        foreach (QFace face in model.faces)
        {
            int submesh = submeshes[face.t];
            int b = bb[submesh];
            int[] tri = triangles[submesh];
            int n = face.v.Length;
            Debug.Assert(n >= 3);
            for (int i = 0; i < n - 2; i++)
            {
                tri[b + 0] = face.v[0];
                tri[b + 1] = face.v[i + 1];
                tri[b + 2] = face.v[i + 2];
                b += 3;
            }
            bb[submesh] = b;
        }

        Mesh mesh = new Mesh();
        mesh.subMeshCount = triangles.Length;
        mesh.vertices = frame.v;
        mesh.uv = model.uvs;
        mesh.normals = frame.n;
        for (int i = 0; i < triangles.Length; i++)
        {
            Debug.Assert(triangles[i].Length > 0);
            mesh.SetTriangles(triangles[i], i);
        }
        return mesh;
    }

    public static Quaternion AnglesToQuaternion(Vector3 angles)
    {
        /* the 'angles' is provided as a vector in degrees, [pitch yaw roll] */
        Quaternion pitch = Quaternion.AngleAxis(angles[0], Vector3.right);
        Quaternion yaw   = Quaternion.AngleAxis(angles[1], Vector3.down);
        Quaternion roll  = Quaternion.AngleAxis(angles[2], Vector3.forward);
        return yaw * pitch * roll;
    }

    void LoadRocketTrail(Transform tr, int particle_system_index)
    {
        ParticleSystem ps = particleSystems[particle_system_index];
        ParticleSystem.EmitParams emitParams = new ParticleSystem.EmitParams();
        emitParams.applyShapeToPosition = true;
        emitParams.position = tr.TransformVector(ps.transform.InverseTransformVector(tr.position));
        ps.Emit(emitParams, 10);
    }

    public bool LoadEntity(GameObject go, QModel model, int frameindex=0)
    {
        QFrame[] framegroup = model.frames[frameindex].a;
        int subindex = 0;
        bool is_dynamic = framegroup.Length > 1;
        if (is_dynamic)    /* uncommon case */
        {
            float timemod = Time.time % framegroup[framegroup.Length - 1].time;
            while (subindex < framegroup.Length - 1 && framegroup[subindex].time <= timemod)
                subindex++;
        }

        Mesh mesh = framegroup[subindex].m_mesh;
        MeshRenderer rend = go.GetComponent<MeshRenderer>();

        Material[] cur_mats = rend.sharedMaterials;
        bool diff = cur_mats.Length != model.m_materials.Length;
        if (!diff)
            for (int i = 0; i < cur_mats.Length; i++)
                diff = diff || (cur_mats[i] != model.m_materials[i]);
        if (diff)
            rend.sharedMaterials = model.m_materials;

        go.GetComponent<MeshFilter>().sharedMesh = mesh;
        go.GetComponent<MeshCollider>().sharedMesh = mesh;
        return is_dynamic;
    }

    void LoadWeapon(string weaponmodel, int weaponframe)
    {
        if (weaponmodel != current_weapon_model)
        {
            current_weapon_model = weaponmodel;
            if (weapon_entity == null)
            {
                weapon_entity = Instantiate<QuakeEntity>(entityPrefab, weaponController.transform, false);
                weapon_entity.Setup(this);
                weapon_entity.SetFlags(SnapEntry.SOLID_NOT);
                
                /* XXX custom scaling here */
                Transform tr = weapon_entity.transform;
                tr.localPosition = new Vector3(0, 0.25f, -0.4f);
                tr.localRotation = Quaternion.Euler(0, -90, 0);
                tr.localScale = Vector3.one * 0.04f;
            }

            weaponController.transform.Find("Model").gameObject.SetActive(weaponmodel == "");
        }
        weapon_entity.SetModel(GetQModel(weaponmodel), weaponframe);
    }

    QModel GetQModel(string m_model)
    {
        if (m_model == "")
            return null;
        if (!models.ContainsKey(m_model))
        {
            /* should not occur if precaching worked at 100% */
            Debug.LogWarning("NOT PRECACHED: " + m_model);
            models[m_model] = null;
            StartCoroutine(ImportModel(m_model).GetEnumerator());
        }
        return models[m_model];
    }

    void NetworkUpdateData(SnapEntry[] msg)
    {
        int num_lightstyles = msg[0].i;
        for (int i = 0; i < num_lightstyles; i++)
            lightstyles[32 + i] = msg[1 + i].s;
        int msgIndex = 1 + num_lightstyles;

        LoadWeapon(msg[msgIndex].s,
                   msg[msgIndex].i);
        msgIndex += 2;

        int screen_flash = msg[msgIndex++].i;
        if (screen_flash != 0)
            BonusFlash();

        int num_entities = (msg.Length - msgIndex) / 9;
        if (entities.Length < num_entities)
        {
            int j = entities.Length;
            Array.Resize<QuakeEntity>(ref entities, num_entities);
            while (j < num_entities)
            {
                QuakeEntity entity = Instantiate<QuakeEntity>(entityPrefab, worldObject.transform, false);
                entity.Setup(this);
                entities[j++] = entity;
            }
        }

        for (int i = 0; i < num_entities; i++, msgIndex += 9)
        {
            QuakeEntity entity = entities[i];

            string m_model = msg[msgIndex].s;
            int m_frame = msg[msgIndex + 1].i;

            QModel qmodel = GetQModel(m_model);
            entity.SetModel(qmodel, m_frame);

            if (qmodel != null)
            {
                int m_flags = msg[msgIndex + 2].i;
                entity.SetFlags(m_flags);

                Vector3 m_origin = new Vector3(msg[msgIndex + 3].f,
                                               msg[msgIndex + 4].f,
                                               msg[msgIndex + 5].f);
                Vector3 m_angles = new Vector3(msg[msgIndex + 6].f,
                                               msg[msgIndex + 7].f,
                                               msg[msgIndex + 8].f);

                entity.SetPositionAngles(m_origin, m_angles);

                if ((qmodel.flags & QModel.EF_ROCKET) != 0)
                    LoadRocketTrail(entity.transform, 0);
            }
        }
        worldReady = true;
    }

    void SendNetworkUpdates()
    {
        Vector3 pos = new Vector3(headset.position.x,
                                  playArea.position.y,
                                  headset.position.z);
        Vector3 origin = worldObject.transform.InverseTransformPoint(pos);
        ws.Send("tel " + origin.x + " " + origin.y + " " + origin.z);
    }

    public Light AddLight(Vector3 origin, float light, float light_factor, Transform parent=null)
    {
        Light result = Instantiate<Light>(lightPrefab, parent==null ? worldObject.transform : parent, false);

        float range_max = worldObject.transform.lossyScale.magnitude;
        result.transform.localPosition = origin;
        result.range = range_max * light;
        result.intensity *= light * light_factor;
        return result;
    }

    void LoadLights()
    {
        varying_lights.Clear();

        foreach (QLight light in world.lights)
        {
            float light_factor = GetLightFactor(light.style);
            Light component = AddLight(light.origin, light.light, light_factor);
            if (IsVaryingLightLevel(light.style))
            {
                DynamicLight varying_light = new DynamicLight(light);
                varying_light.component = component;
                varying_light.light_factor = light_factor;
                varying_lights.Add(varying_light);
            }
        }
    }

    float GetLightFactor(int style)
    {
        string map = level_info.lightstyles[style];
        float lvl;

        if (map.Length > 1)
        {
            float t10 = Time.time * 10;
            int ti = (int)t10;
            float tf = t10 - ti;

            float lvl1 = map[ti % map.Length];
            float lvl2 = map[(ti + 1) % map.Length];
            lvl = Mathf.Lerp(lvl1, lvl2, tf);
        }
        else
        {
            lvl = map[0];
        }
        return (lvl - 'a') / ('m' - 'a');
    }

    public bool IsVaryingLightLevel(int style)
    {
        return level_info.lightstyles[style].Length > 1 || style >= 32;
    }

    private void Update()
    {
        if (currentUpdateMessage != null)
        {
            SendNetworkUpdates();

            SnapEntry[] msg = Interlocked.Exchange<SnapEntry[]>(ref currentUpdateMessage, null);
            NetworkUpdateData(msg);
        }
        UpdateUniformFadingColor();
        if (!worldReady)
            return;

        Quaternion objrotate = AnglesToQuaternion(new Vector3(0, 100 * Time.time, 0));
        foreach (QuakeEntity entity in entities)
        {
            QModel qmodel = entity.GetQModel();
            if (qmodel != null && (qmodel.flags & QModel.EF_ROTATE) != 0)
                entity.transform.localRotation = objrotate;
        }

        foreach (DynamicLight light in varying_lights)
        {
            QLight qlight = light.qlight;
            float factor = GetLightFactor(qlight.style);
            if (factor != light.light_factor)
            {
                /* XXX figure out why: the light levels don't change if we don't
                   remove the old gameObject and make a new one */
                if (light.component != null)
                    Destroy(light.component.gameObject);
                light.component = AddLight(qlight.origin, qlight.light, factor);
                light.light_factor = factor;
            }
        }

        //DebugShowNormals();

        ShowBspTreeLeafType();
    }

    void DebugShowNormals()
    {
        foreach (QuakeEntity entity in entities)
        {
            Mesh mesh = entity.GetComponent<MeshFilter>().sharedMesh;
            Vector3[] v = mesh.vertices;
            Vector3[] n = mesh.normals;
            Transform tr = entity.transform;
            for (int i = 0; i < v.Length; i++)
            {
                Debug.DrawRay(tr.TransformPoint(v[i]), tr.TransformDirection(n[i] * 0.1f));
            }
        }
    }

    public QTreeLeaf locate_leaf(Vector3 p)
    {
        int search_index = -world.bspnodes.Length;

        while (search_index < 0)
        {
            QTreeNode node = world.bspnodes[~search_index];
            if (p.x * node.plane.x + p.y * node.plane.y + p.z * node.plane.z < node.plane.w)
                search_index = node.back;
            else
                search_index = node.front;
        }
        return world.bspleafs[search_index];
    }

    void ShowBspTreeLeafType()
    {
        Vector3 pos = headset.transform.position;
        Vector3 origin = worldObject.transform.InverseTransformPoint(pos);
        QTreeLeaf leaf = locate_leaf(origin);

        int type = (leaf == null) ? 0 : -leaf.type;
        if (type >= blurEffects.Length)
            type = blurEffects.Length - 1;
        /* careful, blurEffects can contain duplicate entries */
        var blur = blurEffects[type];
        for (int i = 0; i < blurEffects.Length; i++)
            if (blurEffects[i] != null && blurEffects[i] != blur)
                blurEffects[i].enabled = false;
        if (blur != null)
            blur.enabled = true;

        AddUniformScreenTint(blurColor[type]);
    }

    void BonusFlash()
    {
        uniformFadingColor.r += 215 / 256f;
        uniformFadingColor.g += 186 / 256f;
        uniformFadingColor.b += 69  / 256f;
        uniformFadingColor.a =  50  / 256f;
    }

    void UpdateUniformFadingColor()
    {
        uniformScreenTint.color = uniformFadingColor;
        uniformFadingColor.a = Mathf.Max(uniformFadingColor.a - Time.deltaTime, 0);
    }

    void AddUniformScreenTint(Color c2)
    {
        /* if the base screen color is (R,G,B), then:

           - after applying the first screen tint (R1,G1,B1,A1), it is:
                R*(1-A1) + R1*A1, ...

           - after applying the second screen tint on top, it is:
                (R*(1-A1) + R1*A1) * (1-A2) + R2*A2, ...
              = R*((1-A1)*(1-A2)) + R1*(A1*(1-A2)) + R2*A2, ...

           so it is equal to a single screen tinting with

                A_combined = 1 - (1-A1)*(1-A2)
                R_combined = (R1*(A1*(1-A2)) + R2*A2) / A_combined
        */
        if (c2.a < 0.001)
            return;    /* avoids the division by zero */

        Color c1 = uniformScreenTint.color;
        float A_combined = 1 - (1-c1.a)*(1-c2.a);
        float f1 = c1.a * (1 - c2.a) / A_combined;
        float f2 = c2.a / A_combined;
        uniformScreenTint.color = new Color(
            c1.r * f1 + c2.r * f2,
            c1.g * f1 + c2.g * f2,
            c1.b * f1 + c2.b * f2,
            A_combined);
    }
}

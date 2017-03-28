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
public class QMipTex
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
}

[Serializable]
public class QLight
{
    public Vector3 origin;
    public float light;
    public int style;

    public GameObject m_light;
    public float m_factor;
}

[Serializable]
public class QModel
{
    public QFrame[] frames;
    public Vector2[] uvs;
    public QFace[] faces;
    public string[] texturenames;
    public int autorotate;
    public Color32[] palette;    // only on world models
    public QLight[] lights;       // only on world models

    public Mesh[] m_meshes;
    public Material[] m_materials;
}

[Serializable]
public class QHello
{
    public int version;
    public string level;
    public Vector3 start_pos;
    public string[] lightstyles;
}

[Serializable]
public class QEdict
{
    public string model;
    public int frame;
    public Vector3 origin;
    public Vector3 angles;
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
}


public class NetworkImporter : MonoBehaviour {

    public string baseUrl = "192.168.0.10:8000";

    public GameObject worldObject;
    public Material worldMaterial;
    public Material skyMaterial;
    public Material waterMaterial;
    public GameObject meshPrefab;
    public GameObject lightPrefab;

    QHello level_info;
    Dictionary<string, QModel> models;
    Dictionary<string, Material> materials;
    Dictionary<string, bool> models_importing;
    WebSocket ws;
    volatile SnapEntry[] currentUpdateMessage;
    SnapEntry[] workUpdateMessage;
    List<GameObject> meshes, autorotating;
    List<QLight> varying_lights;
    string[] lightstyles;

    private void Start()
    {
        meshes = new List<GameObject>();
        autorotating = new List<GameObject>();
        varying_lights = new List<QLight>();

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
        Transform playArea = VRTK.VRTK_DeviceFinder.PlayAreaTransform();
        playArea.position = worldObject.transform.TransformVector(level_info.start_pos);

        models = new Dictionary<string, QModel>();
        models_importing = new Dictionary<string, bool>();
        materials = new Dictionary<string, Material>();

        lightstyles = level_info.lightstyles;
        foreach (var x in ImportModel(level_info.level, "/level/"))
            yield return x;

        LoadLights(GetWorldModel());
        LoadEntity(worldObject, GetWorldModel());

        workUpdateMessage = new SnapEntry[0];
        ws = new WebSocket("ws://" + baseUrl + "/websock/2");
        ws.OnMessage += (sender, e) => AsyncDecompressMsg(e.RawData);
        ws.OnError += (sender, e) => Debug.LogError("WebSocket error: " + e.Message);
        ws.ConnectAsync();
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

    QModel GetWorldModel()
    {
        return models[level_info.level];
    }

    private void OnApplicationQuit()
    {
        if (ws != null)
        {
            ws.CloseAsync();
            ws = null;
        }
    }

    IEnumerable ImportModel(string model_name, string baseurl="/model/")
    {
        if (!models.ContainsKey(model_name))
        {
            QModel model = new QModel();
            foreach (var x in DownloadJson(baseurl + model_name, model))
                yield return x;

            Color32[] palette = model.palette;
            if (palette == null || palette.Length == 0)
                palette = GetWorldModel().palette;

            for (int i = 0; i < model.texturenames.Length; i++)
                foreach (var x in ImportTexture(model.texturenames[i], palette))
                    yield return x;

            ImportMeshes(model);
            models[model_name] = model;
        }
        models_importing[model_name] = false;
    }

    Texture2D ImportSingleTexture(Color32[] palette, byte[] input_data, int width, int height, 
                                  int scanline, int offset, out Color32 mean_color)
    {
        int size = width * height;
        Color32[] colors = new Color32[size];
        int rr = 0, gg = 0, bb = 0;
        for (int y = 0; y < height; y++)
        {
            int base_src = offset + y * scanline;
            int base_dst = y * width;
            for (int x = 0; x < width; x++)
            {
                Color32 c = palette[input_data[base_src + x]];
                colors[base_dst + x] = c;
                rr += c.r;
                gg += c.g;
                bb += c.b;
            }
        }
        mean_color = new Color32((byte)(rr / size), (byte)(gg / size), (byte)(bb / size), 0);

        Texture2D tex2d = new Texture2D(width, height);
        tex2d.SetPixels32(colors);
        tex2d.filterMode = FilterMode.Bilinear;
        tex2d.Apply();
        return tex2d;
    }

    IEnumerable ImportTexture(string texture_name, Color32[] palette)
    {
        if (!materials.ContainsKey(texture_name))
        {
            QMipTex texinfo = new QMipTex();
            foreach (var x in DownloadJson("/texture/" + texture_name, texinfo))
                yield return x;
            Debug.Log("Texture " + texture_name + ": " + texinfo.width + "x" + texinfo.height);

            byte[] input_data = Convert.FromBase64String(texinfo.data);
            Material mat;
            Color32 mean_color;

            if (texinfo.effect == "sky")
            {
                int w2 = texinfo.width / 2;
                
                /* the right half */
                Texture2D tex0 = ImportSingleTexture(palette, input_data, w2, texinfo.height, texinfo.width, w2, out mean_color);

                /* the left half */
                Color32[] palette_with_alpha = new Color32[256];
                palette_with_alpha[0] = mean_color;
                for (int i = 1; i < 256; i++)
                    palette_with_alpha[i] = palette[i];
                Texture2D tex1 = ImportSingleTexture(palette_with_alpha, input_data, w2, texinfo.height, texinfo.width, 0, out mean_color);

                mat = Instantiate(skyMaterial);
                mat.SetTexture("_MainTex", tex0);
                mat.SetTexture("_ExtraTex", tex1);
            }
            else
            {
                Texture2D tex2d = ImportSingleTexture(palette, input_data, texinfo.width, texinfo.height, texinfo.width, 0, out mean_color);
                if (texinfo.effect == "water")
                    mat = Instantiate(waterMaterial);
                else
                    mat = Instantiate(worldMaterial);

                mat.SetTexture("_MainTex", tex2d);
            }

            materials[texture_name] = mat;
        }
    }

    void ImportMeshes(QModel model)
    {
        Mesh[] meshes = new Mesh[model.frames.Length];
        for (int i = 0; i < model.frames.Length; i++)
            meshes[i] = ImportMesh(model, i);
        model.m_meshes = meshes;

        Material[] mat = new Material[model.texturenames.Length];
        for (int i = 0; i < mat.Length; i++)
            mat[i] = materials[model.texturenames[i]];
        model.m_materials = mat;
    }

    Mesh ImportMesh(QModel model, int frameindex)
    {
        /* note: this returns a new Mesh, computed independently, for each frame */
        QFrame frame = model.frames[frameindex];

        int num_textures = model.texturenames.Length;
        int[][] triangles = new int[num_textures][];

        int[] countTriangles = new int[num_textures];
        foreach (QFace face in model.faces)
        {
            countTriangles[face.t] += face.v.Length - 2;
        }

        for (int i = 0; i < num_textures; i++)
            triangles[i] = new int[countTriangles[i] * 3];

        int[] bb = new int[num_textures];
        foreach (QFace face in model.faces)
        {
            int b = bb[face.t];
            int[] tri = triangles[face.t];
            int n = face.v.Length;
            Debug.Assert(n >= 3);
            for (int i = 0; i < n - 2; i++)
            {
                tri[b + 0] = face.v[0];
                tri[b + 1] = face.v[i + 1];
                tri[b + 2] = face.v[i + 2];
                b += 3;
            }
            bb[face.t] = b;
        }
        
        Mesh mesh = new Mesh();
        mesh.subMeshCount = num_textures;
        mesh.vertices = frame.v;
        mesh.uv = model.uvs;
        mesh.normals = frame.n;
        for (int i = 0; i < num_textures; i++)
            mesh.SetTriangles(triangles[i], i);
        return mesh;
    }

    Quaternion AnglesToQuaternion(Vector3 angles)
    {
        /* the 'angles' is provided as a vector in degrees, [pitch yaw roll] */
        Quaternion pitch = Quaternion.AngleAxis(angles[0], Vector3.right);
        Quaternion yaw   = Quaternion.AngleAxis(angles[1], Vector3.down);
        Quaternion roll  = Quaternion.AngleAxis(angles[2], Vector3.forward);
        return yaw * pitch * roll;
    }

    void SetPositionAngles(Transform transform, Vector3 position, Vector3 angles)
    {
        transform.localPosition = position;
        transform.localRotation = AnglesToQuaternion(angles);
    }

    void LoadEntity(GameObject go, QModel model, int frameindex=0)
    {
        Mesh mesh = model.m_meshes[frameindex];
        MeshRenderer rend = go.GetComponent<MeshRenderer>();
        if (rend.materials != model.m_materials)
            rend.materials = model.m_materials;
        go.GetComponent<MeshFilter>().mesh = mesh;
        go.GetComponent<MeshCollider>().sharedMesh = mesh;
   }

    void NetworkUpdateData(SnapEntry[] msg)
    {
        foreach (GameObject go in meshes)
            Destroy(go);
        meshes.Clear();
        autorotating.Clear();

        int num_lightstyles = msg[0].i;
        for (int i = 0; i < num_lightstyles; i++)
            lightstyles[32 + i] = msg[1 + i].s;

        for (int msgIndex = 1 + num_lightstyles; msgIndex < msg.Length; msgIndex += 8)
        {
            string m_model = msg[msgIndex].s;
            if (m_model == null || m_model.Length == 0)
                continue;

            if (!models_importing.ContainsKey(m_model))
            {
                models_importing[m_model] = true;
                StartCoroutine(ImportModel(m_model).GetEnumerator());
            }
            if (!models.ContainsKey(m_model))
                continue;

            int m_frame = msg[msgIndex + 1].i;
            Vector3 m_origin = new Vector3(msg[msgIndex + 2].f,
                                           msg[msgIndex + 3].f,
                                           msg[msgIndex + 4].f);
            Vector3 m_angles = new Vector3(msg[msgIndex + 5].f,
                                           msg[msgIndex + 6].f,
                                           msg[msgIndex + 7].f);

            GameObject go = Instantiate(meshPrefab, worldObject.transform, false);
            meshes.Add(go);
            QModel qmodel = models[m_model];
            SetPositionAngles(go.transform, m_origin, m_angles);
            LoadEntity(go, qmodel, m_frame);
            if (qmodel.autorotate != 0)
                autorotating.Add(go);
        }
    }

    void AddLight(QLight light, float light_factor)
    {
        float range_max = worldObject.transform.lossyScale.magnitude;

        GameObject go = Instantiate(lightPrefab, worldObject.transform, false);
        go.transform.localPosition = light.origin;

        Light component = go.GetComponent<Light>();
        component.range = range_max * light.light;
        component.intensity *= light.light * light_factor;

        light.m_light = go;
        light.m_factor = light_factor;
    }

    void LoadLights(QModel world)
    {
        varying_lights.Clear();

        foreach (QLight light in world.lights)
        {
            AddLight(light, GetLightFactor(light.style));
            if (IsVaryingLightLevel(light.style))
                varying_lights.Add(light);
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
            SnapEntry[] msg = Interlocked.Exchange<SnapEntry[]>(ref currentUpdateMessage, null);
            NetworkUpdateData(msg);
        }

        Quaternion q = AnglesToQuaternion(new Vector3(0, 100 * Time.time, 0));
        foreach (GameObject go in autorotating)
            go.transform.localRotation = q;

        foreach (QLight light in varying_lights)
        {
            float factor = GetLightFactor(light.style);
            if (factor != light.m_factor)
            {
                Destroy(light.m_light);
                AddLight(light, factor);
            }
        }

        //DebugShowNormals();
    }

    void DebugShowNormals()
    {
        foreach (GameObject go in meshes)
        {
            Mesh mesh = go.GetComponent<MeshFilter>().mesh;
            Vector3[] v = mesh.vertices;
            Vector3[] n = mesh.normals;
            Transform tr = go.transform;
            for (int i = 0; i < v.Length; i++)
            {
                Debug.DrawRay(tr.TransformPoint(v[i]), tr.TransformDirection(n[i] * 0.1f));
            }
        }
    }

}

using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;
using WebSocketSharp;


[Serializable]
public class Face
{
    public int[] v;
    public int t;               /* texture index */
}

[Serializable]
public class MipTex
{
    public int width, height;
    public string data;
}

[Serializable]
public class Frame
{
    public Vector3[] v;
}

[Serializable]
public class Model
{
    public Frame[] frames;
    public Vector2[] uvs;
    public Face[] faces;
    public string[] texturenames;
    public int autorotate;

    public Mesh[] m_meshes;
    public Material[] m_materials;
}

[Serializable]
public class Hello
{
    public string level;
    public Vector3 start_pos;
    public Color32[] palette;
}

[Serializable]
public class Edict
{
    public string model;
    public int frame;
    public Vector3 origin;
    public Vector3 angles;
}

[Serializable]
public class Snapshot
{
    public Edict[] edicts;
}


public class NetworkImporter : MonoBehaviour {

    public string baseUrl = "192.168.0.10:8000";

    public GameObject worldObject;
    public Shader worldShader;
    public GameObject meshPrefab;

    Hello level_info;
    Dictionary<string, Model> models;
    Dictionary<string, Material> materials;
    Dictionary<string, bool> models_importing;
    List<GameObject> autorotating;
    WebSocket ws;
    string lastUpdateMessage;

    private void Start()
    {
        StartCoroutine(GetHelloWorld().GetEnumerator());
    }

    IEnumerable DownloadJson(string path, object obj)
    {
        UnityWebRequest www = UnityWebRequest.Get("http://" + baseUrl + path);
        yield return www.Send();

        if (www.isError)
        {
            throw new ApplicationException(path + ": " + www.error);
        }
        else
        {
            string rawstring = www.downloadHandler.text;
            JsonUtility.FromJsonOverwrite(rawstring, obj);
        }
    }

    IEnumerable GetHelloWorld()
    {
        level_info = new Hello();
        foreach (var x in DownloadJson("/hello", level_info))
            yield return x;

        Debug.Log("Loading level " + level_info.level);
        Transform playArea = VRTK.VRTK_DeviceFinder.PlayAreaTransform();
        playArea.position = worldObject.transform.TransformVector(level_info.start_pos);

        models = new Dictionary<string, Model>();
        models_importing = new Dictionary<string, bool>();
        materials = new Dictionary<string, Material>();

        foreach (var x in ImportModel(level_info.level, "/level/"))
            yield return x;

        LoadEntity(worldObject, models[level_info.level]);

        ws = new WebSocket("ws://" + baseUrl + "/websock");
        ws.OnMessage += (sender, e) => lastUpdateMessage = e.Data;
        ws.OnError += (sender, e) => Debug.Log("WebSocket error: " + e.Message);
        ws.ConnectAsync();
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
            Model model = new Model();
            foreach (var x in DownloadJson(baseurl + model_name, model))
                yield return x;

            for (int i = 0; i < model.texturenames.Length; i++)
                foreach (var x in ImportTexture(model.texturenames[i]))
                    yield return x;

            ImportMeshes(model);
            models[model_name] = model;
        }
        models_importing[model_name] = false;
    }

    IEnumerable ImportTexture(string texture_name)
    {
        if (!materials.ContainsKey(texture_name))
        {
            MipTex texinfo = new MipTex();
            foreach (var x in DownloadJson("/texture/" + texture_name, texinfo))
                yield return x;

            Color32[] palette = level_info.palette;
            Texture2D tex2d = new Texture2D(texinfo.width, texinfo.height);
            byte[] input_data = Convert.FromBase64String(texinfo.data);
            int size = texinfo.width * texinfo.height;
            Color32[] colors = new Color32[size];
            for (int k = 0; k < size; k++)
            {
                colors[k] = palette[input_data[k]];
            }
            tex2d.SetPixels32(colors);
            tex2d.Apply();
            Debug.Log("Texture " + texture_name + ": " + tex2d.width + "x" + tex2d.height);

            Material mat = new Material(worldShader);
            mat.SetTexture("_MainTex", tex2d);
            materials[texture_name] = mat;
        }
    }

    void ImportMeshes(Model model)
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

    Mesh ImportMesh(Model model, int frameindex)
    {
        /* note: this returns a new Mesh, computed independently, for each frame */
        Frame frame = model.frames[frameindex];

        int num_textures = model.texturenames.Length;
        int[][] triangles = new int[num_textures][];

        int[] countTriangles = new int[num_textures];
        foreach (Face face in model.faces)
        {
            countTriangles[face.t] += face.v.Length - 2;
        }

        for (int i = 0; i < num_textures; i++)
            triangles[i] = new int[countTriangles[i] * 3];

        int[] bb = new int[num_textures];
        foreach (Face face in model.faces)
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
        for (int i = 0; i < num_textures; i++)
            mesh.SetTriangles(triangles[i], i);
        mesh.RecalculateNormals();
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

    void LoadEntity(GameObject go, Model model, int frameindex=0)
    {
        Mesh mesh = model.m_meshes[frameindex];
        MeshRenderer rend = go.GetComponent<MeshRenderer>();
        if (rend.materials != model.m_materials)
            rend.materials = model.m_materials;
        go.GetComponent<MeshFilter>().mesh = mesh;
        go.GetComponent<MeshCollider>().sharedMesh = mesh;
   }

    void NetworkUpdateData(string msg)
    {
        Snapshot snapshot = JsonUtility.FromJson<Snapshot>(msg);

        Component[] children = worldObject.GetComponentsInChildren(typeof(MeshFilter));
        foreach (Component child in children)
            if (child.gameObject != worldObject)
                Destroy(child.gameObject);

        autorotating = new List<GameObject>();
        foreach (Edict ed in snapshot.edicts)
        {
            if (!models_importing.ContainsKey(ed.model))
            {
                models_importing[ed.model] = true;
                StartCoroutine(ImportModel(ed.model).GetEnumerator());
            }
            if (!models.ContainsKey(ed.model))
                continue;

            GameObject go = Instantiate(meshPrefab, worldObject.transform, false);
            Model model = models[ed.model];
            SetPositionAngles(go.transform, ed.origin, ed.angles);
            LoadEntity(go, model, ed.frame);
            if (model.autorotate != 0)
                autorotating.Add(go);
        }
    }

    private void Update()
    {
        if (lastUpdateMessage != null)
        {
            string msg = lastUpdateMessage;
            lastUpdateMessage = null;
            NetworkUpdateData(msg);
        }

        if (autorotating != null)
        {
            Quaternion q = AnglesToQuaternion(new Vector3(0, 100 * Time.time, 0));
            foreach (GameObject go in autorotating)
                go.transform.localRotation = q;
        }
    }

}
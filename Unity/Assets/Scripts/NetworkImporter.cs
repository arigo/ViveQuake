using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Networking;


[Serializable]
public class Face
{
    public int[] v;
    public int t;               /* texture id */
}

[Serializable]
public class MipTex
{
    public int width, height;
    public string data;
}

[Serializable]
public class World
{
    public Vector3[] vertices;
    public Vector2[] uvs;
    public Face[] faces;
    public MipTex[] textures;
    public Color32[] palette;
}


public class NetworkImporter : MonoBehaviour {

    public GameObject worldObject;
    public Shader worldShader;

    private void Start()
    {
        StartCoroutine(GetText());
    }

    IEnumerator GetText()
    {
        UnityWebRequest www = UnityWebRequest.Get("http://192.168.0.10:8000/level/e1m1");
        yield return www.Send();

        if (www.isError)
        {
            Debug.Log(www.error);
        }
        else
        {
            // Retrieve results as binary data
            string rawstring = www.downloadHandler.text;
            World world = JsonUtility.FromJson<World>(rawstring);
            Debug.Log("got " + world.faces.Length + " faces!");
            Debug.Log("face 0 has " + world.faces[0].v.Length + " vertices!");

            ImportWorld(world);
        }
    }

    void ImportWorld(World world)
    {
        ImportTextures(world);
        ImportMesh(world);
    }

    void ImportTextures(World world)
    {
        Material[] result = new Material[world.textures.Length];
        Color32[] palette = world.palette;

        for (int i = 0; i < world.textures.Length; i++)
        {
            MipTex texinfo = world.textures[i];
            if (texinfo == null || texinfo.data == null)
                continue;

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

            Material mat = new Material(worldShader);
            mat.SetTexture("_MainTex", tex2d);
            result[i] = mat;

            Debug.Log("Texture dimension " + tex2d.width + "x" + tex2d.height + " (" + tex2d.mipmapCount + " mipmaps)");
        }

        worldObject.GetComponent<MeshRenderer>().materials = result;
    }

    void ImportMesh(World world)
    {
        MeshRenderer rend = worldObject.GetComponent<MeshRenderer>();
        int num_textures = rend.materials.Length;

        int[][] triangles = new int[num_textures][];

        int[] countTriangles = new int[num_textures];
        foreach (Face face in world.faces)
        {
            countTriangles[face.t] += face.v.Length - 2;
        }

        for (int i = 0; i < num_textures; i++)
            triangles[i] = new int[countTriangles[i] * 3];

        int[] bb = new int[num_textures];
        foreach (Face face in world.faces)
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
        mesh.subMeshCount = rend.materials.Length;
        mesh.vertices = world.vertices;
        mesh.uv = world.uvs;
        for (int i = 0; i < num_textures; i++)
            mesh.SetTriangles(triangles[i], i);
        mesh.RecalculateNormals();
        worldObject.GetComponent<MeshFilter>().mesh = mesh;
        worldObject.GetComponent<MeshCollider>().sharedMesh = mesh;
    }
}
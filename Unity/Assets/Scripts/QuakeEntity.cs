using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;


public class QuakeEntity : MonoBehaviour {
    const int LAYER_DEFAULT = 0;
    const int LAYER_NOBLOCK = 8;

    QModel qmodel = null;
    int qframeindex = -1;
    int qsolidflags = 0;
    NetworkImporter qmanager;
    Light dynamic_light;

    public void Setup(NetworkImporter manager)
    {
        qmanager = manager;
        gameObject.SetActive(false);
    }

    public QModel GetQModel()
    {
        return qmodel;
    }

    public void SetModel(QModel model, int frameindex=0)
    {
        if (model != qmodel || frameindex != qframeindex)
        {
            qmodel = model;
            qframeindex = frameindex;

            gameObject.SetActive(model != null);
            if (model != null)
            {
                bool is_dynamic = qmanager.LoadEntity(gameObject, model, frameindex);
                if (is_dynamic)
                    qframeindex = -1;

                if ((model.flags & QModel.EF_ROCKET) != 0)
                    SetDynamicLight(200);
                else
                    SetDynamicLight(0);
            }
        }
    }

    public void SetPositionAngles(Vector3 position, Vector3 angles)
    {
        transform.localPosition = position;
        transform.localRotation = NetworkImporter.AnglesToQuaternion(angles);
    }

    public void SetFlags(int m_flags)
    {
        int solidflags = m_flags & (SnapEntry.SOLID_NOT | SnapEntry.SOLID_TRIGGER);
        if (qmodel != null && (m_flags & QModel.STATIC_IMAGE) != 0)
        {
            solidflags = SnapEntry.SOLID_NOT;
            LoadWebImage();
        }

        if (solidflags != qsolidflags)
        {
            qsolidflags = solidflags;
            var coll = GetComponent<MeshCollider>();
            if (solidflags == SnapEntry.SOLID_NOT)
            {
                gameObject.layer = LAYER_NOBLOCK;
                coll.enabled = false;
            }
            else if (solidflags == SnapEntry.SOLID_TRIGGER)
            {
                gameObject.layer = LAYER_NOBLOCK;
                coll.convex = true;
                coll.isTrigger = true;
            }
            else
            {
                gameObject.layer = LAYER_DEFAULT;
                coll.isTrigger = false;
                coll.convex = false;
            }
        }
    }

    void SetDynamicLight(float lightlevel)
    {
        if (dynamic_light != null)
            Destroy(dynamic_light.gameObject);
        dynamic_light = null;

        if (lightlevel != 0)
            dynamic_light = qmanager.AddLight(Vector3.zero, lightlevel, 1.5f, transform);
    }


    static int nextImageID = 0;
    static int downloadingImage = 0;
    int image_id = -1;

    void LoadWebImage()
    {
        if (image_id >= 0)
            return;
        if (downloadingImage > 6)
            return;

        gameObject.SetActive(true);
        MeshRenderer rend = GetComponent<MeshRenderer>();
        rend.enabled = false;
        StartCoroutine(DownloadImage().GetEnumerator());
        downloadingImage++;
    }

    IEnumerable DownloadImage()
    {
        image_id = nextImageID++;
        string path = "/image/" + image_id;
        Debug.Log(path);
        WWW www = new WWW("http://" + qmanager.baseUrl + path);
        yield return www;
        downloadingImage--;

        MeshRenderer rend = GetComponent<MeshRenderer>();
        var texture = rend.material.mainTexture = www.texture;

        float width = texture.width * 0.15f;
        float height = texture.height * 0.15f;

        Mesh mesh = new Mesh();
        mesh.vertices = new Vector3[] 
        {
            new Vector3(0, 0, -0.5f*width),
            new Vector3(0, height, -0.5f*width),
            new Vector3(1, height, 0.5f*width),
            new Vector3(1, 0, 0.5f*width),

            new Vector3(1, 0, 0.5f*width),
            new Vector3(1, height, 0.5f*width),
            new Vector3(0, height, -0.5f*width),
            new Vector3(0, 0, -0.5f*width),
        };
        mesh.uv = new Vector2[]
        {
            new Vector2(0, 0),
            new Vector2(0, 1),
            new Vector2(1, 1),
            new Vector2(1, 0),

            new Vector2(1, 0),
            new Vector2(1, 1),
            new Vector2(0, 1),
            new Vector2(0, 0),
        };
        mesh.triangles = new int[]
        {
            0, 1, 2, 0, 2, 3,
            4, 5, 6, 4, 6, 7,
        };
        mesh.RecalculateBounds();
        mesh.RecalculateNormals();
        GetComponent<MeshFilter>().sharedMesh = mesh;
        rend.enabled = true;
    }
}

using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class QuakeEntity : MonoBehaviour {
    const int LAYER_DEFAULT = 0;
    const int LAYER_NOBLOCK = 8;

    public QModel qmodel = null;
    public int qframeindex = -1;
    public int qsolidflags = 0;
    public NetworkImporter qmanager;
    Light light = null;

    public void Setup(NetworkImporter manager)
    {
        qmanager = manager;
        gameObject.SetActive(false);
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
                qmanager.LoadEntity(gameObject, model, frameindex);

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
        if (light != null)
            Destroy(light.gameObject);
        light = null;

        if (lightlevel != 0)
            light = qmanager.AddLight(Vector3.zero, lightlevel, 1.5f, transform);
    }
}

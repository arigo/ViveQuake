using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class WaterScreenScript : MonoBehaviour {

    public Material material;
    public Color fogColor;

    Camera _camera;

    void Start()
    {
        _camera = GetComponent<Camera>();
    }

    Vector2 GetPDelta()
    {
        Debug.Assert(_camera.stereoEnabled);

        /* This is called one for each eye.  We do a lot of computations but the idea is to get
         * both eyes' matrix, consider a point far away, and apply each matrix to get screen
         * coordinates for each eye.  By construction, either p_left or p_right should be almost zero,
         * depending on whether we're currently rendering the left or right eye.  The other tells how
         * far from the center we're in the other eye.  We take the mean of the two vector2 positions
         * and get a delta that we apply to the current eye's shader.  In this way we should get the
         * transformation aligned for both eyes.
         */

        Matrix4x4[] currentStereoViewProjMat = new Matrix4x4[2];
        for (int eye = 0; eye < 2; ++eye)
        {
            Matrix4x4 stereoViewMat = _camera.GetStereoViewMatrix(eye == 0 ? Camera.StereoscopicEye.Left : Camera.StereoscopicEye.Right);
            Matrix4x4 stereoProjMat = _camera.GetStereoProjectionMatrix(eye == 0 ? Camera.StereoscopicEye.Left : Camera.StereoscopicEye.Right);
            stereoProjMat = GL.GetGPUProjectionMatrix(stereoProjMat, true);
            currentStereoViewProjMat[eye] = stereoProjMat * stereoViewMat;
        }

        Vector3 reference = _camera.ViewportToWorldPoint(new Vector3(0.5f, 0.5f, 1e9f));
        Vector4 ref4 = new Vector4(reference.x, reference.y, reference.z, 1);
        Vector4 p_left4 = currentStereoViewProjMat[0] * ref4;
        Vector4 p_right4 = currentStereoViewProjMat[1] * ref4;
        Vector2 p_left = new Vector3(p_left4.x / p_left4.w, p_left4.y / p_left4.w);
        Vector2 p_right = new Vector3(p_right4.x / p_right4.w, p_right4.y / p_right4.w);
        Vector2 p_delta = (p_left + p_right) * 0.5f;

        /* XXX doesn't work correctly.  Fix */
        p_delta *= 0.5f;

        return p_delta;
    }

    void FourTapCone(RenderTexture source, RenderTexture dest, Vector2 p_delta)
    {
        material.SetFloat("_Delta_x", p_delta.x);
        material.SetFloat("_Delta_y", p_delta.y);
        material.SetColor("_FogColor", fogColor);
        Graphics.Blit(source, dest, material, /*pass=*/0);
    }

    void OnRenderImage(RenderTexture source, RenderTexture destination)
    {
        FourTapCone(source, destination, GetPDelta());
    }
}

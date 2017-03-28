// Upgrade NOTE: replaced '_Object2World' with 'unity_ObjectToWorld'

// Upgrade NOTE: replaced '_Object2World' with 'unity_ObjectToWorld'

Shader "Quake/SkyShader"

{
	// https://docs.unity3d.com/Manual/SL-VertexFragmentShaderExamples.html

	Properties
	{
		[NoScaleOffset] _MainTex("Texture", 2D) = "white" {}
		[NoScaleOffset] _ExtraTex("Texture", 2D) = "white" {}
	}

	SubShader
	{
		Pass
		{
			CGPROGRAM
			// use "vert" function as the vertex shader
	#pragma vertex vert
			// use "frag" function as the pixel (fragment) shader
	#pragma fragment frag

			struct v2f
			{
				float4 pos : SV_POSITION;
				float2 uv0 : TEXCOORD0;
				float2 uv1 : TEXCOORD1;
	};

			// vertex shader
			v2f vert(float4 vertex : POSITION)
			{
				v2f o;
				o.pos = mul(UNITY_MATRIX_MVP, vertex);

				float3 S = mul(unity_ObjectToWorld, vertex) - _WorldSpaceCameraPos;
				S = normalize(S);
				S.y = 3 * S.y;
				S = normalize(S);
				o.uv0 = S.xz * 3.0;
				o.uv1 = o.uv0;

				float t = _Time.x * 1.0;
				o.uv0.x += t;
				o.uv0.y += t;

				t = _Time.x * 2.0;
				o.uv1.x += t;
				o.uv1.y += t;

				return o;
			}

			// texture we will sample
			sampler2D _MainTex;
			sampler2D _ExtraTex;

			// pixel shader; returns low precision ("fixed4" type)
			// color ("SV_Target" semantic)
			fixed4 frag(v2f i) : SV_Target
			{
				// To avoid bleeding the color of the transparent pixels,
				// we consider RGBA colors scaled by the A value.  That's
				// the case in input as long as we use 0,0,0,0 for the
				// transparent pixels.In output, we must un-scale by
				// dividing the RGB components by A.  Note that the final
				// value of A cannot be zero if the first input has A = 1
				// (in fact it is always >= 0.75).

				fixed4 col0 = tex2D(_MainTex, i.uv0);
				fixed4 col1 = tex2D(_ExtraTex, i.uv1);
				fixed4 col = lerp(col0, col1, col1.a);
				col /= col.a;
				return col;
			}

			ENDCG
		}
	}
}
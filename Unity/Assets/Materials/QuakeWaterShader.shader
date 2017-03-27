// Upgrade NOTE: replaced '_Object2World' with 'unity_ObjectToWorld'

// Upgrade NOTE: replaced '_Object2World' with 'unity_ObjectToWorld'

Shader "Quake/WaterShader"

{
	// https://docs.unity3d.com/Manual/SL-VertexFragmentShaderExamples.html

	Properties
	{
		[NoScaleOffset] _MainTex("MainTex", 2D) = "white" {}
	    _Amplitude("Amplitude", Float) = 0.05
		_Alpha("Alpha", Float) = 0.667
		_Resolution("Resolution", Float) = 0.25
	}

	SubShader
	{
		Blend SrcAlpha OneMinusSrcAlpha

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
				float2 uv : TEXCOORD0;
			};

			// vertex shader
			v2f vert(float4 vertex : POSITION, float2 uv : TEXCOORD0)
			{
				v2f o;
				o.pos = mul(UNITY_MATRIX_MVP, vertex);
				o.uv = uv;
				return o;
			}

			// texture we will sample
			sampler2D _MainTex;
			float _Amplitude;
			float _Alpha;
			float _Resolution;

			float2 shift(float2 p)
			{
				float d = _Time.y * 0.06;
				float2 f = 8.0 * (p + d);
				float2 q = cos(float2(cos(f.x - f.y)*cos(f.y),
					                  sin(f.x - f.y)*sin(f.y)));
				return q;
			}

			// pixel shader; returns low precision ("fixed4" type)
			// color ("SV_Target" semantic)
			fixed4 frag(v2f i) : SV_Target
			{
				float2 r = i.uv * _Resolution;
				float2 p = shift(r);
				float2 q = shift(r + 1);
				float2 s = r + _Amplitude * (p - q);
				fixed4 col = tex2D(_MainTex, s / _Resolution);
				col.w = _Alpha;
				return col;
			}

			ENDCG
		}
	}
}
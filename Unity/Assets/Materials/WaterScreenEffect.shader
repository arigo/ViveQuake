Shader "AR/WaterScreenEffect" {
	Properties{ _MainTex("", any) = "" {} }

	CGINCLUDE

	struct v2f
	{
		float4 pos : SV_POSITION;
		float2 uv : TEXCOORD0;
	};

	v2f vert(float4 vertex : POSITION, float2 uv : TEXCOORD0)
	{
		v2f o;
		o.pos = mul(UNITY_MATRIX_MVP, vertex);
		o.uv = uv;
		return o;
	}

	sampler2D _MainTex;
	float _Delta_x, _Delta_y;
	fixed4 _FogColor;

	float2 shift(float2 p)
	{
		float d = _Time.y * 0.11;
		float2 f = 8.0 * (p + d);
		float2 q = cos(float2(cos(f.x - f.y)*cos(f.y),
			sin(f.x - f.y)*sin(f.y)));
		return q;
	}

	fixed4 frag(v2f i) : SV_Target
	{
		const float amplitude = 0.0333;
		const float resolution = 0.7;

		float2 delta;
		delta.x = _Delta_x;
		delta.y = _Delta_y;
		float2 r = (i.uv + delta) * resolution;
		float2 p = shift(r);
		float2 q = shift(r + 1);
		float2 s = r + amplitude * (p - q);
		fixed4 pixel = tex2D(_MainTex, s / resolution - delta);
		fixed4 result = lerp(pixel, _FogColor, _FogColor.w);
		result.w = 1;
		return result;
	}

	ENDCG

	SubShader{
		Pass{
			ZTest Always Cull Off ZWrite Off

			CGPROGRAM
#pragma vertex vert
#pragma fragment frag
			ENDCG
		}
	}
	Fallback off
}
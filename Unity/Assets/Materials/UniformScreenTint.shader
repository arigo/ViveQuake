Shader "AR/UniformScreenTint" {

	Properties{
		_Color("Color", Color) = (1,1,1,.5)
	}

	SubShader{
		ZTest Always Cull Off ZWrite Off
		Blend SrcAlpha OneMinusSrcAlpha
		Color[_Color]
		Pass{}
	}
}
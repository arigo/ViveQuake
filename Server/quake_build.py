import sys, os
import cffi

# TESTED WITH: 'src' should be a copy or symlink to the WinQuake
# directory from git://github.com/id-Software/Quake/


ffibuilder = cffi.FFI()

ffibuilder.cdef("""
    void quake_main(int c, char **v);
""")

ffibuilder.set_source("_quake", """
    #define main  quake_main
    #include "src/sys_null.c"

    vec3_t vpn, vright, vup;
    vec3_t r_origin;

    qboolean isDedicated = 1;
    qboolean r_cache_thrash = 0;
    int sb_lines;
    int con_backscroll, con_totallines=30;
    qboolean scr_disabled_for_loading;
    qboolean con_forcedup = 0;
    beam_t cl_beams[MAX_BEAMS];
    entity_t cl_temp_entities[MAX_TEMP_ENTITIES];
    float scr_centertime_off;
    cvar_t chase_active = {"chase_active", "0"};
    int net_numdrivers = 0;
    net_driver_t net_drivers[MAX_NET_DRIVERS];
    unsigned short d_8to16table[256];
    int r_pixbytes = 1;
    texture_t *r_notexture_mip;

    viddef_t vid = {
        .width = 640,
        .height = 480
        };

    void Con_Printf (char *fmt, ...)
    {
        va_list argptr;
        va_start(argptr, fmt);
        vprintf(fmt, argptr);
        va_end(argptr);
    }
    void Con_DPrintf (char *fmt, ...)
    {
        va_list argptr;
        va_start(argptr, fmt);
        vprintf(fmt, argptr);
        va_end(argptr);
    }

    cvar_t	cl_rollspeed = {"cl_rollspeed", "200"};
    cvar_t	cl_rollangle = {"cl_rollangle", "2.0"};

    float V_CalcRoll (vec3_t angles, vec3_t velocity)
    {
        vec3_t	forward, right, up;
        float	sign;
        float	side;
        float	value;

        AngleVectors (angles, forward, right, up);
        side = DotProduct (velocity, right);
        sign = side < 0 ? -1 : 1;
        side = fabs(side);

        value = cl_rollangle.value;

        if (side < cl_rollspeed.value)
            side = side * value / cl_rollspeed.value;
        else
            side = value;

        return side*sign;
    }

    void M_Init(void) { }
    void M_ToggleMenu_f(void) { }
    void M_Keydown(int key) { }
    void M_Menu_Quit_f(int key) { }
    void D_FlushCaches(void) { /* XXX? */ }
    void Draw_BeginDisc(void) { }
    void Draw_EndDisc(void) { }
    void CL_InitTEnts(void) { }
    void CL_UpdateTEnts(void) { }
    void CL_EstablishConnection(char *host) { }
    void CL_DecayLights(void) { }
    int CL_ReadFromServer(void) { return 0; }
    void CL_NextDemo(void) { }
    void CL_Disconnect(void) { }
    void CL_Disconnect_f(void) { }
    void R_Init(void) { }
    void R_InitTextures(void) { }
    void R_InitSky(struct texture_s *mt) { }
    void R_EntityParticles(entity_t *ent) { }
    void R_RocketTrail(vec3_t start, vec3_t end, int type) { }
    void VID_Init(unsigned char *palette) { }
    void VID_Shutdown(void) { }
    void V_Init(void) { }
    void V_StartPitchDrift(void) { }
    void V_StopPitchDrift(void) { }
    void Sbar_Init(void) { }
    void SCR_Init(void) { }
    void SCR_UpdateScreen(void) { }
    void SCR_BeginLoadingPlaque(void) { }
    void SCR_EndLoadingPlaque(void) { }
    void Draw_Init(void) { }
    void Chase_Init(void) { }
    void Con_Init(void) { }

    cvar_t	cl_name = {"_cl_name", "player", true};
    cvar_t	cl_color = {"_cl_color", "0", true};
    client_static_t	cls;
    client_state_t	cl;

    void CL_Init(void) { }
    void CL_SendCmd(void) { }
    void CL_StopPlayback(void) { }
""",
    sources='''
        src/common.c
        src/net_main.c
        src/net_vcr.c
        src/sv_main.c
        src/sv_move.c
        src/sv_phys.c
        src/sv_user.c
        src/pr_cmds.c
        src/pr_edict.c
        src/pr_exec.c
        src/cmd.c
        src/host.c
        src/host_cmd.c
        src/keys.c
        src/mathlib.c
        src/model.c
        src/zone.c
        src/cvar.c
        src/in_null.c
        src/cd_null.c
        src/snd_null.c
        src/world.c
        src/crc.c
        src/wad.c
    '''.split())

if len(sys.argv) > 1:
    os.system("grep -w %s %s" % (sys.argv[1], ' '.join(ffibuilder._assigned_source[3]['sources']))); sys.exit(0)


if __name__ == '__main__':
    ffibuilder.compile(verbose=True)

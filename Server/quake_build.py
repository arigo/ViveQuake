import sys, os
import cffi

# TESTED WITH: 'src' should be a copy or symlink to the WinQuake
# directory from git://github.com/id-Software/Quake/


ffibuilder = cffi.FFI()

ffibuilder.cdef("""
    void PQuake_Ready(int c, char **v);
    void PQuake_Host_Frame(float frame_time);

    typedef float vec_t;
    typedef vec_t vec3_t[3];
    typedef enum {false, true} qboolean;

    #define DEF_SAVEGLOBAL ...
    enum {ev_void, ev_string, ev_float, ev_vector, ev_entity, ev_field,
          ev_function, ev_pointer, ...};

    typedef struct {
        int numfielddefs, numglobaldefs;
        ...;
    } dprograms_t;

    typedef struct {
        unsigned short type;
        unsigned short ofs;
        int s_name;
    } ddef_t;

    typedef struct {
        int num_edicts;
        char *lightstyles[...];
        char *model_precache[...];
        ...;
    } server_t;

    dprograms_t *progs;
    ddef_t *pr_fielddefs, *pr_globaldefs;
    char *pr_strings;
    server_t sv;

    typedef int string_t;
    typedef int func_t;

    typedef union {
        string_t		string;
        float			_float;
        float			vector[3];
        func_t			function;
        int				_int;
        int				edict;
    } eval_t;

    eval_t *get_edict_field(int eindex, int fieldindex);
    void exit(int);

    #define SOLID_NOT		...		// no interaction with other objects
    #define SOLID_TRIGGER	...		// touch on edge, but not blocking

    struct pquake_staticentity_s {
        char *model;
        int modelindex, frame, colormap, skin;
        vec3_t origin, angles;
    };
    struct pquake_staticentity_s pquake_staticentities[];
    int pquake_count_staticentities(void);

    typedef enum {
        src_client,		// came in over a net connection as a clc_stringcmd
                        // host_client will be valid during this state.
        src_command		// from the command buffer
    } cmd_source_t;
    void Cmd_ExecuteString(char *text, cmd_source_t src);

    typedef struct qsocket_s { ...; } qsocket_t;

    typedef struct client_s
    {
        struct qsocket_s *netconnection;	// communications handle
        char			name[32];			// for printing to other people
        ...;
    } client_t;
    client_t *host_client;

    typedef struct
    {
        int			maxclients;
        struct client_s	*clients;		// [maxclients]
        ...;
    } server_static_t;
    server_static_t	svs;

    void SV_ConnectClient (int clientnum);
""")

ffibuilder.set_source("_quake", r"""
    #define main  PQuake_main   /* never actually called */
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
    void SCR_UpdateScreen(void) { }

    eval_t *get_edict_field(int eindex, int fieldindex)
    {
        edict_t *ed = EDICT_NUM(eindex);
        return (eval_t *)((int *)&ed->v + fieldindex);
    }

    static void hack_makestatic(void);

    void PQuake_Ready(int argc, char **argv)
    {
        static quakeparms_t    parms;

        hack_makestatic();

        parms.memsize = 8*1024*1024;
        parms.membase = malloc (parms.memsize);
        parms.basedir = ".";

        COM_InitArgv (argc, argv);

        parms.argc = com_argc;
        parms.argv = com_argv;

        printf ("Host_Init\n");
        Host_Init (&parms);
    }

    static long host_frame_time = 0;    /* a random, strictly increasing num */

    void PQuake_Host_Frame(float frame_time)
    {
        host_frame_time++;
        Host_Frame(frame_time);
    }

    typedef void (*builtin_t) (void);
    extern	builtin_t *pr_builtins;
    extern int pr_numbuiltins;
    extern void PF_makestatic(void);

    struct pquake_staticentity_s {
        char *model;
        int modelindex, frame, colormap, skin;
        vec3_t origin, angles;
    };
    struct pquake_staticentity_s pquake_staticentities[MAX_STATIC_ENTITIES];
    int pquake_num_staticentities;
    float last_server_time = 1e100;

    static void maybe_server_load(void)
    {
        if (sv.time < last_server_time)
        {
            /* we are in the initial frame of a new server loading */
            pquake_num_staticentities = 0;
        }
        last_server_time = sv.time;
    }

    int pquake_count_staticentities(void)
    {
        maybe_server_load();
        return pquake_num_staticentities;
    }

    static void PQuake_PF_makestatic (void)
    {
        edict_t *ent;
        int i;
        struct pquake_staticentity_s *se;

        maybe_server_load();
        ent = G_EDICT(OFS_PARM0);

        if (pquake_num_staticentities < MAX_STATIC_ENTITIES)
        {
            se = &pquake_staticentities[pquake_num_staticentities++];
            se->model = pr_strings + ent->v.model;
            se->modelindex = SV_ModelIndex(se->model);
            se->frame = ent->v.frame;
            se->colormap = ent->v.colormap;
            se->skin = ent->v.skin;
            for (i = 0; i < 3; i++) {
                se->origin[i] = ent->v.origin[i];
                se->angles[i] = ent->v.angles[i];
            }
        }
        else {
            fprintf(stderr, "quake_build.py: too many static entities!\n");
        }
        PF_makestatic();
    }

    static void hack_makestatic(void)
    {
        int i;
        for (i = 0; i < pr_numbuiltins; i++)
        {
            if (pr_builtins[i] == &PF_makestatic)
                pr_builtins[i] = &PQuake_PF_makestatic;
        }
    }

    static int net_dummy0(void) { return 0; }
    static void net_dummy1(qboolean x) { }
    static qsocket_t *net_dummy2(char *name) { return NULL; }
    static qsocket_t *net_dummy3(void) { return NULL; }
    static int net_dummy4(qsocket_t *sock) { return 0; }
    static int net_dummy5(qsocket_t *sock, sizebuf_t *data) { return 1; }
    static qboolean net_dummy6(qsocket_t *sock) { return true; }
    static void net_dummy7(qsocket_t *sock) { }
    static void net_dummy8(void) { }

    int net_numdrivers = 1;
    net_driver_t net_drivers[MAX_NET_DRIVERS] = {
        {
        "Unused",
        false,
        net_dummy0,
        net_dummy1,
        net_dummy1,
        net_dummy2,
        net_dummy3,
        net_dummy4,
        net_dummy5,
        net_dummy5,
        net_dummy6,
        net_dummy6,
        net_dummy7,
        net_dummy8
        }
    };

    extern void SV_ConnectClient (int clientnum);  /* sv_main.c */
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
    '''.split(),
    extra_compile_args=['-g'])

if len(sys.argv) > 1:
    os.system("grep -w %s %s" % (sys.argv[1], ' '.join(ffibuilder._assigned_source[3]['sources']))); sys.exit(0)


if __name__ == '__main__':
    ffibuilder.compile(verbose=True)

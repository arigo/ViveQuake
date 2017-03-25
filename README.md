A Quake 1 renderer for VR
-------------------------

Tested with HTC Vive.  Based on Unity.


After loading the Unity project, you need to manually import the VRTK toolkit and SteamVR.
Copy them to these paths:

    Unity\Assets\Lib\SteamVR
    Unity\Assets\Lib\VRTK


The Unity project works like a client.  It connects to a Python server which you must
launch first.  The first step is to copy or make a symlink to your Quake standard "id1"
directory inside Server\id1.  Then run the server.py program:

    cd Server
    python server.py


Finally, the address that the Unity client connects to is hard-wired for now inside this
script (it is not 127.0.0.1 because I run the server on another Linux machine):

    Asserts\Scripts\NetworkImporter.cs

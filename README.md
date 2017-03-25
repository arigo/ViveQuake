A Quake 1 renderer for VR
-------------------------

Tested with HTC Vive.  Based on Unity.


After loading the Unity project, you need to manually import the VRTK toolkit and SteamVR.
Copy them to these paths:

    Unity\Assets\Lib\SteamVR
    Unity\Assets\Lib\VRTK


The Unity project works like a client.  It connects to a Python server
which you must launch first, on a possibly different machine, not
necessarily running Windows.  See the instructions in Server/README.


Finally, the address that the Unity client connects to is hard-wired for now inside this
script (it is not 127.0.0.1 because I run the server on another Linux machine):

    Asserts\Scripts\NetworkImporter.cs

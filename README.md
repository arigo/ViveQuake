A Quake 1 renderer for VR
-------------------------

Tested with HTC Vive.  Based on Unity.


After loading the Unity project, you need to manually import the SteamVR
asset.  Select the Asset Store and import SteamVR from there.


The Unity project works like a client.  It connects to a Python server
which you must launch first, on a possibly different machine, not
necessarily running Windows.  See the instructions in Server/README.


Finally, the address that the Unity client connects to is hard-wired for
now in the "Main Object" in the scene (fix Base Url, the first property
in the inspector).  It is not 127.0.0.1 because I run the server on another
Linux machine.


License
-------

Files in Server/ contain a bit of code directly copied from the Quake source
code, which is available as GPL.  So all the code in Server/ is also covered
by the GPL license.  Files in Unity/ should be free of such code and is thus
covered by the more permissive MIT license.

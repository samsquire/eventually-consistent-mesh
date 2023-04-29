# eventually-consistent-mesh

an attempt to create an asynchronously replicated append only performant split brain resistant mesh

I am a beginner at distributed systems.

I thought:

* if we had an append only system, that could accept writes as fast as it could
* but also replicated the data asynchonously behind the scenes 
* resolve conflicts with a GUI

CAP theorem means that we sacrifice certain things for certain requirements.

# node_lww

`node_lww.py` uses timestamps to resolve conflicts, received broadcasted data is sorted when retrieving a value, so all servers that are synchronized shall agree on a value.

If there is a split brain, then a server shall report a different value for that split.

# node_history

Creates a `hash` of the data and creates a trail of the data that originated from.

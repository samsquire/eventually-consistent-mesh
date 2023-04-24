# consistent-mesh

an attempt to create an asynchronously replicated append only performant split brain resistant mesh

I am a beginner at distributed systems.

I thought:

* if we had an append only system, that could accept writes as fast as it could
* but also replicated the data asynchonously behind the scenes 
* resolve conflicts with a GUI

CAP theorem means that we sacrifice certain things for certain requirements.

# conflict resolution



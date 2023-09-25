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

# node_history.py

Creates a `hash` of the data and creates a trail of the data that originated from. I am yet to create a visualization of the trail of data.

# node_bank.py

Generates random `withdraw`als and `deposit` events and applies them to a balance. Every node in the cluster should agree on the final balance.

The problem is that any decision based on a balance could be cancellable.



# node_cluster.py

This is used by the Jepsen tests.

# Jepsen tests

The Jepsen tests test s for linearizability and the eventually consistent mesh fails the linearizability test.

## old notes

I am working on Jepsen tests for the mesh. Currently the jepsen tests spin up 5 servers in AWS and deploy the mesh to them, then creates a connection to each server to prepare for streaming instructions.

The linearizability test in Jepsen fails, because this software is not linerarizable.

# LICENCE

BSD Zero Clause License

Copyright (C) 2023 by Samuel Michael Squire sam@samsquire.com

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

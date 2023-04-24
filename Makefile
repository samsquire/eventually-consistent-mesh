run: 
	for index in $$(seq 0 5) ; do python3 node_index.py run --index $$index & done


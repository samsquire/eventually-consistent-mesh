run: 
	for index in $$(seq 0 5) ; do python3 node_lww.py run --index $$index & done


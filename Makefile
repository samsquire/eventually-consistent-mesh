run: 
	for index in $$(seq 0 5) ; do python3 node.py run --index $$index & done


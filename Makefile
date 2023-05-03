run: 
	for index in $$(seq 0 5) ; do python3 node_bank.py run --index $$index & done


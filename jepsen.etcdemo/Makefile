
default:
	ansible-playbook -i inventory machines.playbook.yml

jepsen:
	lein run test --nodes-file nodes --username ubuntu --ssh-private-key ~/.ssh/jepsen2.pem --password ubuntu

destroy:
	ansible-playbook -i inventory machines-destroy.playbook.yml


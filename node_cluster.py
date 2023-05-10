import socket
import select
from threading import Thread, Lock
from argparse import ArgumentParser
import queue
import uuid
import heapq


from collections import defaultdict
parser = ArgumentParser()
parser.add_argument("run", help="One of init, daemon, add-host")
parser.add_argument("--index", help="index")
parser.add_argument("--nodes-file", help="nodes file")
args = parser.parse_args()
def lookup_node_port(name):
  for server in range(len(node_data)):
    if name == node_data[server]:
      return server
  return -1
node_data = open(args.nodes_file).read().split("\n")
node_index = lookup_node_port(args.index)

class Value:
  def __init__(self, identifier, kind, key, value):
    self.identifier = identifier
    self.kind = kind
    self.key = key
    self.value = value
    self.hash = ""
    self.time = ""
    self.direction = ""
    self.cancelled = False
    self.reason = ""
    self.cause = None
    self.children = []

  def __str__(self):
    return "val {} {} {} {} {} {} {} {} {}".format(self.kind, \
      self.direction, \
      self.key, \
      self.value, \
      self.hash, \
      self.time,
      self.cancelled,
      self.reason,
      self.cause)

  def __lt__(self, other):
    return float(self.time) > float(other.time)

  def descend(self):
    pass

class Database:

  def __init__(self, server):
    self.database = {}
    self.server = server
    self.index = 0
    self.cached = 0
    self.hashes = {}
    self.counter = 0

  def sortfunc(left, right):
    return int(left[5]) - int(right[5])

  def persist(self, splitted):
    if splitted[2] not in self.database:
      self.database[splitted[2]] = {}
    saved = self.database[splitted[2]] 
    # print(self.server, saved)
    if "value" not in self.database[splitted[2]]:
      newitem = {}
      self.counter = self.counter + 1
      if len(splitted) == 6:
        self.hashes[splitted[4]] = splitted
      else:
        new_hash = self.counter
        splitted.append(new_hash)
        temp = splitted[4]
        splitted[4] = new_hash
        splitted[5] = temp
      val = Value(self.counter, splitted[0], splitted[2], int(splitted[3]))
      val.hash = splitted[4]
      val.time = splitted[5]
      val.direction = splitted[1]
      self.hashes[splitted[4]] = val
      newitem["value"] = [val]
      self.database[splitted[2]] = newitem
      return val
    else:
      topmost = heapq.heappop(self.database[splitted[2]]["value"])
      if len(splitted) == 6:
        self.hashes[splitted[4]] = splitted
      else:
        previous_version = topmost
        new_hash = previous_version.hash
        splitted.append(new_hash)
        temp = splitted[4]
        splitted[4] = new_hash
        splitted[5] = temp
        self.hashes[splitted[3]] = splitted
      heapq.heappush(self.database[splitted[2]]["value"], topmost)
      self.counter = self.counter + 1
      val = Value(self.counter, splitted[0], splitted[2], int(splitted[3]))
      val.hash = splitted[4]
      val.time = splitted[5]
      val.direction = splitted[1]
      if topmost:
        topmost.children.append(val)
      heapq.heappush(self.database[splitted[2]]["value"], val)
      return val
      # self.database[splitted[1]]["value"].sort(key=lambda x: float(x[4]))
      # self.database[splitted[1]]["value"].sort(self.sortfunc)
    # print(self.server, self.getvalue(splitted[1]))

  def getvalue(self, name):
    balance = 0
    items = []
    clone = list(self.database[name]["value"])
    for item in range(0, len(self.database[name]["value"])):
      items.append(heapq.heappop(clone))
    self.sorted = clone
    postbalances = []
    for item_index in range(len(items)):
      item = items[item_index]
      
      if item.direction == "withdraw":
        if balance >= item.value:
          balance -= item.value
        elif balance <= 0:
          item.reason = "balance was below 0"
          item.cancelled = True
        elif balance < item.value:
          item.cancelled = True
          item.reason = "balance not large enough"
          for backwards_index in range(item_index - 1, 0, -1):
            if postbalances[backwards_index] < item.value:
              item.cause = items[backwards_index]
              break
              
      if item.direction == "deposit":
        balance += item.value

      postbalances.append(balance)
    # print(postbalances)
    self.cached = balance
    return balance 

class Server(Thread):
  def __init__(self, index, port, database, clients):
    super(Server, self).__init__()
    self.index = index
    self.port = port
    self.database = database
    self.clients = clients
    self.running = True

  def shutdown(self):
    self.running = False

  def run(self):

    HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
    PORT = self.port        # Port to listen on (non-privileged ports are > 1023)
    print("Server listening on port {}".format(self.port))
    connections = {}
    filenos = {}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.bind((HOST, int(PORT)))

        s.listen()

        e = select.epoll()
        e.register(s.fileno(), select.EPOLLIN)

        while self.running:
            events = e.poll()
            for fileno, event in events:
                if fileno == s.fileno():
                  print("Connection to {}".format(self.port))
                  conn, addr = s.accept()
                  conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                  print('Connection', addr)
                  conn.setblocking(0)
                  fd = conn.fileno()
                  e.register(fd, select.EPOLLIN | select.EPOLLOUT)
                  connections[fd] = {
                      "connection": conn,
                      "fd": fd,
                      "pending_send": [],
                      "phase": "wait",
                      "size": bytes(),
                      "message": bytes(),
                      "remaining_size": 8
                  }

                if fileno != s.fileno() and event & select.EPOLLOUT:
                    for data in connections[fileno]["pending_send"]:
                        print("Sending {} to connection ".format(data, fileno))
                        connections[fileno]["connection"].send(data.encode())
                    connections[fileno]["pending_send"].clear()

                if fileno != s.fileno() and event & select.EPOLLIN:
                    if connections[fileno]["phase"] == "wait":
                      connections[fileno]["current_size"] = connections[fileno]["connection"].recv(connections[fileno]["remaining_size"])
                      connections[fileno]["remaining_size"] -= len(connections[fileno]["current_size"])
                      if len(connections[fileno]["current_size"]) == 0:
                          print("Removing connection")
                          connections[fileno]["connection"].close()
                          print("{} fileno".format(fileno))
                          e.unregister(fileno)
                          del connections[fileno]
                          continue
                      connections[fileno]["size"] = connections[fileno]["size"] + connections[fileno]["current_size"]
                      if len(connections[fileno]["size"]) < 8:
                        print("incomplete length message")

                      if len(connections[fileno]["size"]) == 8:
                        length = int.from_bytes(connections[fileno]["size"], "little")
                        connections[fileno]["length"] = length
                        connections[fileno]["remaining_length"] = length
                        if length > 100:
                          import sys
                          print("extremely long message {}".format(connections[fileno]["size"]))
                          sys.exit(1)
                        connections[fileno]["size"] = bytes()
                        connections[fileno]["phase"] = "message"
                        connections[fileno]["remaining_size"] = 8
    
                        continue
                    if connections[fileno]["phase"] == "message":
                      # print(length)
                      # print("length of message is ", length)
                      connections[fileno]["current_message"] = connections[fileno]["connection"].recv(connections[fileno]["remaining_length"])
                      connections[fileno]["remaining_length"] = connections[fileno]["remaining_length"] - len(connections[fileno]["current_message"])
                      connections[fileno]["message"] = connections[fileno]["message"] + connections[fileno]["current_message"]
                      

                      if len(connections[fileno]["message"]) == connections[fileno]["length"]:
                        
                        connections[fileno]["phase"] = "wait"
                        data = connections[fileno]["message"] 
                        # print("received a full message {}".format(data.decode('utf8')))
                        connections[fileno]["message"] = bytes()
                        # print(data)
                        lines = data.decode('utf8').split("\t")
                        lines.pop()
                        for data in lines: 
                          if data == "":
                            import sys
                            print("error")
                            sys.exit(1)
                        for data in lines:
                            if not data: continue
                            splitted = data.split(" ")
                            # print(splitted)
                            if splitted[0] == "server" and len(splitted) == 2:
                              print("received server name")
                              server_index = int(lookup_node_port(splitted[1]))
                              connections[fileno]["server_index"] = server_index
                              connections[fileno]["initialized"] = True
                            if splitted[0] == "get" and len(splitted) == 3:
                              server_value = self.database.getvalue(splitted[1])
                              print("server value", server_value)
                              print("length of items", len(self.database.database[splitted[1]]["value"]))
                              # print("second to last value", self.database.database[splitted[1]]["value"][-2])
                              # for sp in self.database.database[splitted[1]]["value"]:
                              #   if sp.kind == "sync" and sp.value == server_value.value:
                              #     for sp2 in self.database.database[splitted[2]]["value"]:
                              #       if sp2.kind == "set" and sp2.value == sp.value and sp2.time == sp.time:
                              #         print("ERROR {} {}".format(sp, sp2))
                              # for item in self.database.database[splitted[1]]["value"]:
                              #  if item.cancelled:
                              #    print(item, "was cancelled")
                               
                              clone = list(self.database.database[splitted[1]]["value"])
                              f = open("./logs/{}.dot".format(args.index), "w")
                              f.write("digraph G {\n")
                              f.write("rankdir=LR;\n")
                              for index in range(0, len(clone)):
                                val = heapq.heappop(clone)
                                val.descend()
                                for child in val.children:
                                  f.write("\"{}\" -> \"{}\";\n".format(val.identifier, child.identifier))
                              f.write("}")
                              f.close()
                              from subprocess import Popen
                              render = Popen(["dot", "-Tpng", "-o", "diagrams/{}.png".format(args.index), "logs/{}.dot".format(args.index)])
                              render.communicate() 
                            if splitted[0] == "sync" and len(splitted) == 6:
                              self.database.persist(splitted)
                            elif "initialized" in connections[fileno] and splitted[0] == "set" and len(splitted) == 5:
                              val = self.database.persist(splitted)
                              my_server_index = connections[fileno]["server_index"]
                              for their_fileno, client in connections.items():
                                server_index = client["server_index"]
                                if "initialized" in client:
                                  connection_to_client = self.clients[server_index]
                                  sender = connection_to_client.sender
                                  if not connection_to_client.me:
                                    synced = "sync {} {} {} {}".format(splitted[1], splitted[2], splitted[3], splitted[4])
                                    sender.queue.put((synced, val.time))
                                
                        continue

        e.unregister(s.fileno())
        e.close()

class Client(Thread):

  def __init__(self, port, i, sender):
      super(Client, self).__init__()
      self.HOST = '127.0.0.1'  # The server's hostname or IP address
      self.PORT = port        # The port used by the server
      self.i = i
      self.sender = sender

  def run(self):
      self.running = True
      while self.running:
        try:
          # print("Trying to connect to server")
          self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.s.connect((self.HOST, self.PORT))
          self.s.settimeout(20)
          message = "server {}\t".format(self.i).encode('utf8')
          bytesl = int.to_bytes(len(message), length=8, byteorder="little")
          success = self.s.send(bytesl)
          success = self.s.send(message)
          self.running = not success
        except:
          pass # print("Waiting for server {}".format(self.PORT))

class ClientReceiver(Thread):
  def __init__(self, client, port, database):
     super(ClientReceiver, self).__init__()
     self.client = client
     self.packets = []
     self.running = True

  def run(self):

      while self.running:
        try:
          # data = self.client.s.recv(11)
           
          if not data:
              self.running = False
          
          # splitted = data.decode('utf8').split(" ")
          # print(splitted)
          # database.persist(splitted) 

        except:
          pass


class ClientSender(Thread):
  def __init__(self, port):
     super(ClientSender, self).__init__()
     self.packets = []
     self.running = True
     self.port = port
     self.queue = queue.Queue()
     self.current_message = None
  def run(self):
    while self.running:
      try:
        item = self.queue.get()
        if len(item) == 1:
          timev = time.time()
        else:
          timev = item[1]
        # print("Sending {} to port {}".format(item, self.port))
        message = "{} {}\t".format(item[0], timev).encode('utf8')
        # print(message)
        e = select.epoll()
        e.register(self.client.s.fileno(), select.EPOLLOUT)
        running = True
        queue = [message, int.to_bytes(len(message), length=8, byteorder="little")]
        while running:
            events = e.poll()
            for fileno, event in events:
                if event & select.EPOLLOUT:
                  message_sent = self.client.s.send(queue.pop())
                  if len(queue) == 0:
                    e.unregister(self.client.s.fileno())
                    self.queue.task_done() 
                    running = False
      except Exception as e:
        print(e)
        import sys
        self.running = False
        print("Aborting")

import time
servers = [

]
clients = []
database = Database(args.index)

server = Server(args.index, 65432 + node_index, database, clients)
server.start()
time.sleep(2)
for i in range(0, len(node_data)):
  print(i)
  port = 65432 + i
  me = False
  
  if i == int(node_index):
    me = True
  sender = ClientSender(i)
  client = Client(port, args.index, sender)
  client.me = me
  sender.client = client
  clients.append(client) 
  
  receiver = ClientReceiver(client, i, database) 
  client.receiver = receiver
  client.sender = sender
  servers.append({
    "client": client,
    "receiver": receiver,
    "sender": sender,
  })
    # sender.packets.append("set 0 1")

for c_server in servers:
    c_server["client"].start() 
    time.sleep(1)
    c_server["sender"].start()
    # c_server["receiver"].start()

import time
time.sleep(3)
import random
print("###########################~")
counter = 1
last_time = time.time()
increment = 1
test_amount = 50
while counter <= test_amount:
  for client in clients:
    amount = (1 + 7 * int(node_index)) * counter 
    direction = ["withdraw", "deposit"][random.randrange(0, 2)]
    # print(direction)
    message = "set {} balance {}".format(direction, amount)
    client.sender.queue.put((message,)) 
    counter = counter + 1

client.running = False
server.running = False
receiver.running = False

time.sleep(5)
print("Total counter", counter)
print("Total clients", len(clients))
print("Value should be {} * {} * {} + {} * {} * {} * {}= {}".format(\
  test_amount, increment, len(clients), \
  test_amount, increment, len(clients), len(clients), \
  len(clients) * test_amount * increment + len(clients) * test_amount * increment * len(clients)))
print("Test simulation finished, getting final answers")
for client in clients:
  client.sender.queue.put(("get balance".format(counter),)) 

server.shutdown()

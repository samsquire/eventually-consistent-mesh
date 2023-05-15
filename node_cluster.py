import socket
import select
from threading import Thread, Lock
from argparse import ArgumentParser
import queue
import uuid
import heapq

import sys
def shutdown():
  print("SHUT DOWN")

import atexit

atexit.register(shutdown)

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

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
    return int(self.time) > int(other.time)

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
    # eprint(self.server, saved)
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
      topmost = None
      if len(self.database[splitted[2]]["value"]) > 0:
        topmost = heapq.heappop(self.database[splitted[2]]["value"])
      if len(splitted) == 6:
        self.hashes[splitted[4]] = splitted
      else:
        previous_version = topmost
        if previous_version:
          new_hash = previous_version.hash
        else:
          new_hash = -1
        splitted.append(new_hash)
        temp = splitted[4]
        splitted[4] = new_hash
        splitted[5] = temp
        self.hashes[splitted[3]] = splitted
      if topmost: 
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
    # eprint(self.server, self.getvalue(splitted[1]))

  def getlatest(self, name):
    balance = 0
    if len(self.database[name]["value"]) == 0:
      return 999999999999
    items = []
    clone = list(self.database[name]["value"])
    return heapq.heappop(clone).value

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
    # eprint(postbalances)
    self.cached = balance
    return balance 

class Server(Thread):
  def __init__(self, address, index, port, database, clients):
    super(Server, self).__init__()
    self.index = index
    self.port = port
    self.database = database
    self.clients = clients
    self.running = True
    self.address = address

  def shutdown(self):
    self.running = False

  def run(self):
    HOST = self.address  # Standard loopback interface address (localhost)
    PORT = self.port        # Port to listen on (non-privileged ports are > 1023)
    eprint("Server listening {} on port {}".format(self.address, self.port))
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
              try:
                if fileno == s.fileno():
                  # eprint("Connection to {}".format(self.port))
                  conn, addr = s.accept()
                  conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                  #eprint('Connection', addr)
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
                      "remaining_size": 8,
                      "messages": []
                 } 

                if fileno != s.fileno() and event & select.EPOLLOUT:
                    for data in connections[fileno]["pending_send"]:
                        eprint("Sending {} to connection ".format(data, fileno))
                        connections[fileno]["connection"].send(data.encode())
                    connections[fileno]["pending_send"].clear()
                if fileno != s.fileno() and event & select.EPOLLIN:
                    if connections[fileno]["phase"] == "wait":
                      if connections[fileno]["remaining_size"] > 0:
                        connections[fileno]["current_size"] = connections[fileno]["connection"].recv(connections[fileno]["remaining_size"])
                        connections[fileno]["messages"].append(connections[fileno]["current_size"])
                        # eprint("RECEIVED", connections[fileno]["current_size"])
                        connections[fileno]["remaining_size"] -= len(connections[fileno]["current_size"])
                        connections[fileno]["size"] = connections[fileno]["size"] + connections[fileno]["current_size"]
                        # eprint("size is {}".format(int.from_bytes(connections[fileno]["size"], byteorder="big")))
                        if len(connections[fileno]["current_size"]) == 0:
                            # eprint("Received empty length")
                            # connections[fileno]["connection"].close()
                            # eprint("{} fileno".format(fileno))
                            # e.unregister(fileno)
                            # del connections[fileno]
                            continue
                        if len(connections[fileno]["size"]) < 8:
                          # eprint("incomplete length message")
                          pass

                        if len(connections[fileno]["size"]) == 8:
                          length = int.from_bytes(connections[fileno]["size"], "big")
                          # eprint("received", length, "bytes")
                          connections[fileno]["length"] = length
                          connections[fileno]["remaining_length"] = length
                          if length > 100:
                            eprint("extremely long message {} out of sync".format(connections[fileno]["size"]))
                            connections[fileno]["size"] = bytes()
                            connections[fileno]["phase"] = "wait"
                            connections[fileno]["remaining_size"] = 8
                            connections[fileno]["connection"].close()
                            # eprint("{} fileno".format(fileno))
                            # e.unregister(fileno)
                            eprint(connections[fileno]["messages"])
                            del connections[fileno]
                            continue
                            # sys.exit(1)
                          else:
                            connections[fileno]["size"] = bytes()
                            connections[fileno]["current_size"] = bytes()
                            connections[fileno]["phase"] = "message"
                            connections[fileno]["remaining_size"] = 0
    
                        continue
                    if connections[fileno]["phase"] == "message":
                      # eprint(length)
                      # eprint("length of message is ", length)
                      connections[fileno]["current_message"] = connections[fileno]["connection"].recv(connections[fileno]["remaining_length"])
                      connections[fileno]["messages"].append(connections[fileno]["current_message"])
                      connections[fileno]["remaining_length"] = connections[fileno]["remaining_length"] - len(connections[fileno]["current_message"])
                      connections[fileno]["message"] = connections[fileno]["message"] + connections[fileno]["current_message"]
                      
                      eprint("received message {}".format(connections[fileno]["message"]))
                      if len(connections[fileno]["message"]) == connections[fileno]["length"] and connections[fileno]["remaining_size"] == 0:
                        
                        connections[fileno]["remaining_size"] = 8
                        connections[fileno]["phase"] = "wait"
                        data = connections[fileno]["message"] 
                        # eprint("received a full message {}".format(data.decode('utf8')))
                        connections[fileno]["message"] = bytes()
                        # eprint(data)
                        lines = data.decode('utf8').split("\t")
                        lines.pop()
                        for data in lines: 
                          if data == "":
                            import sys
                            eprint("error")
                            sys.exit(1)
                        for data in lines:
                            if not data: continue
                            splitted = data.split(" ")
                            # eprint(splitted)
                            if splitted[0] == "server" and len(splitted) == 2:
                              # eprint("received server name {}".format(splitted[1]))
                              if splitted[1] == "clientonly":
                                server_index = -1
                                connections[fileno]["server_index"] = server_index
                                connections[fileno]["initialized"] = True
                              else:
                                server_index = int(lookup_node_port(splitted[1]))
                                connections[fileno]["server_index"] = server_index
                                connections[fileno]["initialized"] = True
                            if splitted[0] == "get" and len(splitted) == 3:
                              server_value = self.database.getlatest(splitted[1])
                              eprint("Server value is {}".format(server_value))
                              server_value_bytes = int.to_bytes(server_value, length=8, byteorder="big")
                              connections[fileno]["connection"].send(server_value_bytes)
                              # eprint("server value", server_value)
                              # eprint("length of items", len(self.database.database[splitted[1]]["value"]))
                              # eprint("second to last value", self.database.database[splitted[1]]["value"][-2])
                              # for sp in self.database.database[splitted[1]]["value"]:
                              #   if sp.kind == "sync" and sp.value == server_value.value:
                              #     for sp2 in self.database.database[splitted[2]]["value"]:
                              #       if sp2.kind == "set" and sp2.value == sp.value and sp2.time == sp.time:
                              #         eprint("ERROR {} {}".format(sp, sp2))
                              # for item in self.database.database[splitted[1]]["value"]:
                              #  if item.cancelled:
                              #    eprint(item, "was cancelled")
                               
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
                              eprint("persisted {}".format(val.value))
                              my_server_index = connections[fileno]["server_index"]
                              for their_fileno, client in connections.items():
                                if "initialized" in client:
                                  server_index = client["server_index"]
                                  if server_index == -1:
                                    continue 
                                  connection_to_client = self.clients[server_index]
                                  sender = connection_to_client.sender
                                  if not connection_to_client.me:
                                    synced = "sync {} {} {} {}".format(splitted[1], splitted[2], splitted[3], splitted[4])
                                    sender.queue.put((synced, val.time))
                                
                        continue
              except Exception as er:
                eprint("Server error {}".format(er))
        e.unregister(s.fileno())
        e.close()
        eprint("SERVER SHUT DOWN")

class Client(Thread):

  def __init__(self, address, port, i, sender):
      super(Client, self).__init__()
      self.HOST = address  # The server's hostname or IP address
      self.PORT = port        # The port used by the server
      self.i = i
      self.sender = sender

  def run(self):
      self.running = True
      while self.running:
        try:
          # eprint("Trying to connect to server")
          self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.s.connect((self.HOST, self.PORT))
          self.s.settimeout(20)
          message = "server {}\t".format(self.i).encode('utf8')
          bytesl = int.to_bytes(len(message), length=8, byteorder="big")
          success = self.s.send(bytesl)
          success = self.s.send(message)
          self.running = not success
        except:
          pass # eprint("Waiting for server {}".format(self.PORT))

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
          # eprint(splitted)
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
        item = self.queue.get()
        if len(item) == 1:
          timev = time.time()
        else:
          timev = item[1]
        # eprint("Sending {} to port {}".format(item, self.port))
        message = "{} {}\t".format(item[0], timev).encode('utf8')
        # eprint(message)
        e = select.epoll()
        e.register(self.client.s.fileno(), select.EPOLLOUT)
        sending = True
        queue = [message, int.to_bytes(len(message), length=8, byteorder="big")]
        while sending:
            events = e.poll()
            for fileno, event in events:
                if event & select.EPOLLOUT:
                  try:
                    current = queue[-1]
                    message_sent = self.client.s.send(current)
                    eprint(message_sent)
                    if message_sent == len(current):
                      queue.pop()
                    if message_sent == -1:
                      eprint("message failed to be sent")
                      queue[-1] = queue[-1][message_sent:]
                    if len(queue) == 0:
                      e.unregister(self.client.s.fileno())
                      self.queue.task_done() 
                      sending = False
                  except Exception as er:
                    eprint(er)
                    # e.unregister(self.client.s.fileno())
                    # self.queue.task_done() 
                    # sending = False
                    # self.running = False

import time
servers = [

]
clients = []
database = Database(args.index)
database.database["balance"] = {"value": []}
server = Server(node_data[node_index], args.index, 65432 + node_index, database, clients)
server.start()
time.sleep(2)
for i in range(0, len(node_data)):
  # eprint(i)
  port = 65432 + i
  me = False
  
  if i == int(node_index):
    me = True
  sender = ClientSender(i)
  client = Client(node_data[i], port, args.index, sender)
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
# eprint("###########################~")
counter = 1
last_time = time.time()
increment = 1
test_amount = 50
while counter <= test_amount:
  for client in clients:
    amount = (1 + 7 * int(node_index)) * counter 
    direction = ["withdraw", "deposit"][random.randrange(0, 2)]
    # eprint(direction)
    message = "set {} balance {}".format(direction, amount)
    # client.sender.queue.put((message,)) 
    counter = counter + 1


time.sleep(5)
#eprint("Total counter", counter)
#eprint("Total clients", len(clients))
#eprint("Value should be {} * {} * {} + {} * {} * {} * {}= {}".format(\
#  test_amount, increment, len(clients), \
#  test_amount, increment, len(clients), len(clients), \
#  len(clients) * test_amount * increment + len(clients) * test_amount * increment * len(clients)))
#eprint("Test simulation finished, getting final answers")
for client in clients:
  # client.sender.queue.put(("get balance".format(counter),)) 
  pass

# client.running = False
# server.running = False
# receiver.running = False
# server.shutdown()

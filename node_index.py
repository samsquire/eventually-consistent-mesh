import socket
import select
from threading import Thread, Lock
from argparse import ArgumentParser
import queue


from collections import defaultdict
parser = ArgumentParser()
parser.add_argument("run", help="One of init, daemon, add-host")
parser.add_argument("--index", help="index")
args = parser.parse_args()

class Database:

  def __init__(self, server):
    self.database = {}
    self.server = server
    self.index = 0
    self.cached = 0


  def persist(self, splitted):
    if splitted[1] not in self.database:
      self.database[splitted[1]] = {}
    saved = self.database[splitted[1]] 
    # print(self.server, saved)
    if "value" not in self.database[splitted[1]]:
      newitem = {}
      newitem["value"] = [int(splitted[2])]
      self.database[splitted[1]] = newitem
    else:
      self.database[splitted[1]]["value"].append(int(splitted[2]))
    # print(self.server, self.getvalue(splitted[1]))

  def getvalue(self, name):
    # print(self.database[name])
    
    for i in range(self.index, len(self.database[name]["value"])):
      self.index = i
      self.cached += int(self.database[name]["value"][i])
    self.index = self.index + 1
    return self.cached 

class Server(Thread):
  def __init__(self, index, port, database, clients):
    super(Server, self).__init__()
    self.index = index
    self.port = port
    self.database = database
    self.clients = clients

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
        running = True

        while running:
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
                      "pending_send": []
                  }

                if fileno != s.fileno() and event & select.EPOLLOUT:
                    for data in connections[fileno]["pending_send"]:
                        print("Sending {} to connection ".format(data, fileno))
                        connections[fileno]["connection"].send(data.encode())
                    connections[fileno]["pending_send"].clear()

                if fileno != s.fileno() and event & select.EPOLLIN:
                    size = connections[fileno]["connection"].recv(8)
                    if len(size) < 8:
                        print("Removing connection")
                        connections[fileno]["connection"].close()
                        print("{} fileno".format(fileno))
                        e.unregister(fileno)
                        del connections[fileno]
                        continue
                    length = int.from_bytes(size, "little")
                    # print("length of message is ", length)
                    data = connections[fileno]["connection"].recv(length)
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
                          server_index = int(splitted[1])
                          connections[fileno]["server_index"] = server_index
                          connections[fileno]["initialized"] = True
                        if splitted[0] == "get" and len(splitted) == 2:
                          print("server value")
                          print(self.database.getvalue(splitted[1]))
                          print("length of items", len(self.database.database[splitted[1]]["value"]))
                        if splitted[0] == "sync" and len(splitted) == 3:
                          self.database.persist(splitted)
                        elif "initialized" in connections[fileno] and splitted[0] == "set" and len(splitted) == 3:
                          self.database.persist(splitted)
                          my_server_index = connections[fileno]["server_index"]
                          for client in connections.values():
                            if "initialized" in client:
                              server_index = client["server_index"]
                              if self.index != server_index:
                                sender = self.clients[server_index].sender
                                synced = "sync {} {}\t".format(splitted[1], splitted[2])
                                sender.queue.put(synced)


        e.unregister(args[0])
        e.close()

class Client(Thread):

  def __init__(self, port, index, sender):
      super(Client, self).__init__()
      self.HOST = '127.0.0.1'  # The server's hostname or IP address
      self.PORT = port        # The port used by the server
      self.index = index
      self.sender = sender

  def run(self):
      self.running = True
      while self.running:
        try:
          # print("Trying to connect to server")
          self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.s.connect((self.HOST, self.PORT))
          message = "server {}\t".format(self.index).encode('utf8')
          bytesl = int.to_bytes(len(message), length=8, byteorder="little")
          success = self.s.send(bytesl)
          success = self.s.send(message)
          print(success)
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
          data = self.client.s.recv(11)
           
          if not data:
              self.running = False
          
          splitted = data.decode('utf8').split(" ")
          # print(splitted)
          database.persist(splitted) 

        except:
          pass


class ClientSender(Thread):
  def __init__(self, port):
     super(ClientSender, self).__init__()
     self.packets = []
     self.running = True
     self.port = port
     self.queue = queue.Queue()

  def run(self):
    while self.running:
      try:
        item = self.queue.get()
        # print("Sending {} to port {}".format(item, self.port))
        message = item.encode('utf8')
        error = self.client.s.send(int.to_bytes(len(message), length=8, byteorder="little"))
        error = self.client.s.send(message)
        self.queue.task_done() 
        if not error:
          print("send failure")
          sys.exit(1)
          return
      except:
        pass

servers = [

]
clients = []
database = Database(args.index)
server = Server(args.index, 65432 + int(args.index), database, clients)
server.start()
for i in range(0, 6):
  port = 65432 + i
  sender = ClientSender(i)
  client = Client(port, args.index, sender)
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
    c_server["sender"].start()
    c_server["receiver"].start()

import time
time.sleep(10)

print("###########################~")
counter = 0
last_time = time.time()
increment = 1
test_amount = 1000
while counter < test_amount:
  for client in clients:
    message = "set item {}\t".format(increment)
    client.sender.queue.put(message) 
  counter = counter + 1

client.running = False
server.running = False
receiver.running = False

time.sleep(10)
print("Total counter", counter)
print("Total clients", len(clients))
print("Value should be {} * {} * {} + {} * {} * {} * {}= {}".format(\
  test_amount, increment, len(clients), \
  test_amount, increment, len(clients), len(clients), \
  len(clients) * test_amount * increment + len(clients) * test_amount * increment * len(clients)))
print("Test simulation finished, getting final answers")
for client in clients:
  client.sender.queue.put("get item\t".format(counter)) 


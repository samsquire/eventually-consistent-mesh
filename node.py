import socket
import select
from threading import Thread
from argparse import ArgumentParser

from collections import defaultdict
parser = ArgumentParser()
parser.add_argument("run", help="One of init, daemon, add-host")
parser.add_argument("--index", help="index")
args = parser.parse_args()

class Server(Thread):
  def __init__(self, port):
    super(Server, self).__init__()
    self.port = port
    self.database = {}

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
                elif event & select.EPOLLIN:
                    data = connections[fileno]["connection"].recv(1024)
                    if not data:
                        print("Removing connection")
                        connections[fileno]["connection"].close()
                        e.unregister(fileno)
                        del connections[fileno]
                        continue
                    lines = data.decode('utf8').split("\t")
                    for data in lines:
                        if not data: continue
                        splitted = data.split(" ")
                        if splitted[0] == "set" and len(splitted) == 3:
                          if splitted[1] not in self.database:
                            self.database[splitted[1]] = {}
                          saved = self.database[splitted[1]] 
                          print(self.port, saved)
                          if "value" not in self.database[splitted[1]]:
                            newitem = {}
                            newitem["value"] = [int(splitted[2])]
                            self.database[splitted[1]] = newitem
                          else:
                            self.database[splitted[1]]["value"].append(splitted[2])

                elif fileno != s.fileno() and event & select.EPOLLOUT:
                    for data in connections[fileno]["pending_send"]:
                        print("Sending {} to connection ".format(data, fileno))
                        connections[fileno]["connection"].sendall(data.encode())
                    connections[fileno]["pending_send"].clear()
        e.unregister(args[0])
        e.close()

class Client(Thread):

  def __init__(self, port, index):
      super(Client, self).__init__()
      self.HOST = '127.0.0.1'  # The server's hostname or IP address
      self.PORT = port        # The port used by the server
      self.index = index

  def run(self):
      self.running = True
      while self.running:
        try:
          self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          self.s.connect((self.HOST, self.PORT))
          self.s.send(str(self.index).encode('utf8'))
          self.running = False
        except:
          pass # print("Waiting for server {}".format(self.PORT))

class ClientReceiver(Thread):
  def __init__(self, client, port):
     super(ClientReceiver, self).__init__()
     self.client = client
     self.packets = []
     self.running = True

  def run(self):

      while self.running:
        try:
          data = self.client.s.recv(1024)
          if not data:
              self.running = False
          datas = data.decode('utf8').split("\n")
          for line in datas:
            print("Received " + line) 
        except:
          pass


class ClientSender(Thread):
  def __init__(self, client, port):
     super(ClientSender, self).__init__()
     self.client = client
     self.packets = []
     self.running = True
  def run(self):

      while self.running:
        for item in self.packets:
          try:
            # print("Sending packet")
            error = self.client.s.send(item.encode('utf8'))
            if not error:
              self.running = False
          except:
            pass
        self.packets.clear() 


server = Server(65432 + int(args.index))
server.start()
clients = []
for i in range(0, 5):
  port = 65432 + i
  if int(args.index) != port:
    client = Client(port, args.index)
    clients.append(client) 
    client.start() 
    
    while client.running:
      pass
    receiver = ClientReceiver(client, i) 
    receiver.start()
    sender = ClientSender(client, i)
    sender.start()
    client.receiver = receiver
    client.sender = sender
    # sender.packets.append("set 0 1")

print("###########################~")
counter = 0
while True:
  for client in clients:
    client.sender.packets.append("set item {}\t".format(counter)) 
    counter = counter + 1

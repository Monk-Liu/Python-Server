#coding:utf8
import socket
import signal
import errno
import pyev
import greenlet
import weakref

NOBLOCKING = (errno.EAGAIN, errno.EWOULDBLOCK)
STOPSIGNAL = (signal.SIGINT,)
WORKERCOUNT = socket.SOMAXCONN
FILEDESC = '../pyevtest/test.file'
HTTPHEADER = 'HTTP/1.0 200 OK\r\nContent-Type:text/html\r\n\r\n'

class HttpServer(object):

    def __init__(self,address):
        self.address = address
        self.sock = socket.socket()
        self.sock.bind(address)
        self.sock.setblocking(0)
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEPORT,1)
        #self.address = self.sock.getsockname()
        self.loop = pyev.default_loop()
        self.watchers = [pyev.Signal(sig, self.loop, self.signal_cb)\
                    for sig in STOPSIGNAL]
        self.watchers.append(pyev.Io(self.sock,pyev.EV_READ,self.loop, self.io_cb))
        #self.conns = weakref.WeakValueDictionary() #没必要维持长连接

    def io_cb(self, watcher, revents):
        try:
            while True:
                try:
                    sock, address = self.sock.accept()
                except socket.error as err:
                    if err.args[0] in NOBLOCKING:
                        break
                    else:
                        raise
                else:
                    conn = Connection(sock, address, self.loop)
                    #self.conns[address] = conn
        except Exception as e:
            print('error',e)
            self.handle_error('error accepting connnection')

    def signal_cb(self, watcher, revents):
        self.stop()

    def handle_error(self,msg):
        print(msg)
        self.stop()

    def stop(self):
        self.loop.stop(pyev.EVBREAK_ALL)
        self.sock.close()
        while self.watchers:
            self.watchers.pop().stop() #这里用pop操作不用 for循环！！
        print('Server stop')

    def start(self):
        self.sock.listen(WORKERCOUNT)
        #for conn in self.conns.values():
            #conn.close()
        for watcher in self.watchers:
            watcher.start()
        self.loop.start()



class Connection(object):
    
    def __init__(self, sock, address, loop):
        self.sock = sock 
        self.address = address
        self.sock.setblocking(0)
        self.watcher = pyev.Io(self.sock,pyev.EV_READ,loop,self.io_cb)
        self.watcher.start()

    def io_cb(self, watcher, revents):
        if revents & pyev.EV_READ:
            self.handle_read()
        else:
            self.handle_write()

    def handle_write(self):
        try:
            body = self.getfile(FILEDESC)
            self.sock.send(HTTPHEADER+body)
            #self.sock.send(HTTPHEADER+'OK')
        except socket.error as err:
            if err.args[0] not in NOBLOCKING:
                raise err
        else:
            self.close()

    def reset(self, flag):
        self.watcher.stop()
        self.watcher.set(self.sock, flag)
        self.watcher.start()

    def handle_read(self):
        try:
            buf = self.sock.recv(1024)
            #print buf
        except socket.error as err:
            if err.args[0] not in NOBLOCKING:
                raise errno
        else:
            self.reset(pyev.EV_READ | pyev.EV_WRITE)

    def close(self):
        self.sock.close()
        self.watcher.stop()
        self.watcher = None
        
    def getfile(self,fd):
        g1 = greenlet.greenlet(self.gr1)
        body = g1.switch(fd)
        return body


    def gr1(self,fd):
        f = open(fd,'r')
        body = f.read()
        g_self = greenlet.getcurrent()
        g_self.parent.switch(body)

if __name__ == "__main__":
    address = ('127.0.0.1',8001)
    server = HttpServer(address)
    server.start()


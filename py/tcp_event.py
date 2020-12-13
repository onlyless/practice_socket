# -*- coding: utf-8 -*-
import logging
import socket

import common
from common import parse_header
from event_loop import EventLoop, POLL_ERR, POLL_IN, POLL_OUT
from utils import create_remote_socket, create_server_socket

BUF_SIZE = 4 * 1024
STAGE_INIT = 0
STAGE_ADDR = 1
STAGE_UDP_ASSOC = 2
STAGE_DNS = 3
STAGE_CONNECTING = 4
STAGE_STREAM = 5
STAGE_DESTROYED = -1


class TCPEvent(object):

    def __init__(self, local_sock, loop):
        # type: (socket.socket,EventLoop) -> None
        local_sock.setblocking(False)
        local_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self._local_sock = local_sock
        self._remote_sock = None  # type: socket.socket
        self.loop = loop
        self.loop.add(local_sock, POLL_IN | POLL_ERR, self)
        self._client_address = local_sock.getpeername()[:2]
        self.req_data = bytes()
        self.recv_data = bytes()
        self._stage = STAGE_INIT

    def destroy(self):
        if self._remote_sock:
            self.loop.remove(self._remote_sock)
            self._remote_sock.close()
            self._remote_sock = None
        if self._local_sock:
            self.loop.remove(self._local_sock)
            self._local_sock.close()
            self._local_sock = None

    def _local_read(self):
        sock = self._local_sock
        try:
            data = sock.recv(BUF_SIZE)
        except (OSError, IOError) as e:
            logging.exception(e)
            return
        if not data:
            self.destroy()
            return
        logging.info("recv local read len: %s", len(data))
        if data == b'\x05\x01\x00':
            self.write_to_sock(b'\x05\00', self._local_sock)
            return
        if b'\x05\x01\x00' == data[:3]:
            data = data[3:]
        if self._stage == STAGE_INIT:
            self.req_data += data
            logging.info("POLL_IN event fd:%s", sock.fileno())
            header_result = parse_header(self.req_data)
            if not header_result:
                logging.error("[parse_header] error res:%s data:%s", header_result, self.req_data)
                return
            self._stage = STAGE_STREAM
            addrtype, remote_addr, remote_port, header_length = header_result
            logging.info('connecting %s:%d from %s:%d header_len:%s' %
                         (common.to_str(remote_addr), remote_port,
                          self._client_address[0], self._client_address[1], header_length))
            self.req_data = self.req_data[header_length:]
            remote_sock = create_remote_socket(remote_addr, remote_port)
            self._remote_sock = remote_sock
            self.write_to_sock(b'\x05\x00\x00\x01\x00\x00\x00\x00\x10\x10', self._local_sock)
            logging.info("connecting %s:%s from :%s", remote_addr, remote_port, self._client_address)
            logging.info("remote_sock:%s local_sock:%s", self._remote_sock.fileno(), self._local_sock.fileno())
            self.loop.add(remote_sock, POLL_OUT | POLL_ERR, self)
        elif self._stage == STAGE_STREAM:
            data = self.req_data + data
            self.req_data = bytes()
            self.write_to_sock(data, self._remote_sock)

    def _remote_read(self):
        sock = self._remote_sock
        logging.info("remote_sock: remote:%s local:%s", self._remote_sock.getpeername(),
                     self._remote_sock.getsockname())
        data = sock.recv(BUF_SIZE)
        logging.info("POLL_IN event fd:%s  len:%s", sock.fileno(), len(data))
        if not data:
            self.destroy()
            return
        self.write_to_sock(data, self._local_sock)
        logging.info("recv_len:%s", len(data))

    def _remote_write(self):
        sock = self._remote_sock
        if self.req_data:
            data = self.req_data
            self.req_data = bytes()
            self.write_to_sock(data, sock)
        else:
            self.loop.modify(sock, POLL_IN | POLL_ERR)

    def _local_write(self):
        sock = self._local_sock
        data = self.recv_data
        self.recv_data = bytes()
        logging.info("data:%s recv_data:%s", len(data), len(self.req_data))
        self.write_to_sock(data, sock)

    def handle_event(self, sock, fd, mode):
        # type: (socket.socket,int,int) -> None
        if mode & POLL_IN:
            if sock == self._local_sock:
                self._local_read()
            elif sock == self._remote_sock:
                self._remote_read()

        if mode & POLL_OUT:
            if sock == self._remote_sock:
                self._remote_write()
            elif sock == self._local_sock:
                self._local_write()

    def write_to_sock(self, data, sock):
        if not data:
            return False
        l = len(data)
        s = sock.send(data)
        uncomplete = False
        if s < l:
            data = data[s:]
            uncomplete = True
            self.loop.modify(sock, POLL_OUT | POLL_ERR)
        logging.info("write_to_sock event fd:%s l:%s s:%s", sock.fileno(), l, s)

        if uncomplete:
            if sock == self._local_sock:
                self.recv_data += data
            else:
                self.req_data += data
        else:
            if sock == self._local_sock:
                logging.info("send to local complete: %s", len(data))
            elif sock == self._remote_sock:
                logging.info("send to remote complete: %s", len(data))
        return uncomplete


class TCPServerEvent(object):
    def __init__(self, port):
        self.server_sock = create_server_socket('0.0.0.0', port)
        logging.info("src fd:%s listing server port:%s", self.server_sock.fileno(), port)
        self.loop = None  # type: EventLoop

    def handle_event(self, sock, fd, mode):
        # type: (socket.socket,int,int) -> None
        if sock == self.server_sock:
            local_sock, addr = sock.accept()
            logging.info("receive event fd:%s addr:%s", local_sock.fileno(), addr)
            TCPEvent(local_sock, self.loop)
        else:
            raise Exception("no this socket")

    def add_loop(self, loop):
        # type: (EventLoop) -> None
        self.loop = loop
        loop.add(self.server_sock, POLL_IN | POLL_ERR, self)


if __name__ == '__main__':
    server_port = 1082
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s')
    loop = EventLoop()
    TCPServerEvent(server_port).add_loop(loop)
    loop.run()

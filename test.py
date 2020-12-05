# -*- coding: utf-8 -*-
import logging
import select
import socket


def srv_socket(listen_addr, listen_port):
    addrs = socket.getaddrinfo(listen_addr, listen_port, 0,
                               socket.SOCK_STREAM, socket.SOL_TCP)
    if len(addrs) == 0:
        raise Exception("can't get addrinfo for %s:%d" %
                        (listen_addr, listen_port))
    af, socktype, proto, canonname, sa = addrs[0]
    server_socket = socket.socket(af, socktype, proto)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(sa)
    server_socket.listen(1024)
    return server_socket


buf_size = 32 * 1024

sock = srv_socket('0.0.0.0', '1081')

r_inputs = set()
w_inputs = set()
e_inputs = set()
r_inputs.add(sock.fileno())
w_inputs.add(sock.fileno())
e_inputs.add(sock.fileno())

fd_map = {sock.fileno(): sock}


def non_blocking_read():
    sock.setblocking(False)

    while True:
        try:
            r_list, w_list, e_list = select.select(r_inputs, w_inputs, e_inputs, 1)
            print("r", fd_map)  # 产生了可读事件，即服务端发送信息
            logging.info("r:%s w:%s e:%s", r_list, w_list, e_list)
            for fd in r_list:
                try:
                    event = fd_map[fd]
                    print(event.fileno())
                    ac_socket, addr = event.accept()
                    print(ac_socket.fileno())
                    fd_map[ac_socket.fileno()] = ac_socket
                    data = ac_socket.recv(buf_size)
                except Exception as e:
                    logging.exception(e)
                    continue
                if data:
                    print(data)
                    w_inputs.add(ac_socket.fileno())
                else:
                    print("远程断开连接")
                    r_inputs.clear()
            if len(w_list) > 0:  # 产生了可写的事件，即连接完成
                for fd in w_list:
                    one = fd_map[fd]
                    one.send(b'hello')
                    one.close()
                w_inputs.clear()  # 当连接完成之后，清除掉完成连接的socket
            if len(e_list) > 0:  # 产生了错误的事件，即连接错误
                print(e_list)
                for one in e_list:
                    one.close()
                logging.error('error:%s', e_list)
                e_inputs.clear()  # 当连接有错误发生时，清除掉发生错误的socket
        except OSError as e:
            logging.exception(e)


remote_server = ("202.114.177.93", 80)


def _create_remote_socket(ip, port):
    addrs = socket.getaddrinfo(ip, port, 0, socket.SOCK_STREAM,
                               socket.SOL_TCP)
    if len(addrs) == 0:
        raise Exception("getaddrinfo failed for %s:%d" % (ip, port))
    af, socktype, proto, canonname, sa = addrs[0]

    remote_sock = socket.socket(af, socktype, proto)
    _remote_sock = remote_sock
    remote_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
    return remote_sock


def block_read():
    while True:
        fd, addr = sock.accept()
        print(fd.fileno())
        data = fd.recv(buf_size)

        print('remote req:', data)
        rs = _create_remote_socket(remote_server[0], remote_server[1])
        rs.connect(remote_server)
        rs.send(data)
        rsp = rs.recv(buf_size)
        print('remote resp:', rsp)
        fd.send(rsp)
        fd.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-s: %(message)s')
    logging.info("socket:%d", sock.fileno())
    non_blocking_read()

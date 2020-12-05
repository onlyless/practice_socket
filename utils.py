# -*- coding: utf-8 -*-

import re
import socket


def parse_host_from_req_data(req_data):
    # type: (bytes) -> (str,int)
    s = str(req_data)
    print(s)
    r = re.findall(r'https?://([^ /]+)', s)
    if r and len(r) > 0:
        url = r[0]
        r2 = re.findall(r'([^:]+):?(\d+)?', url)
        if r2 and len(r2) > 0:
            r2 = r2[0]
            host = r2[0]
            port = 80
            if r2[1]:
                port = int(r2[1])
            return host, port


def errno_from_exception(e):
    """Provides the errno from an Exception object.

    There are cases that the errno attribute was not set so we pull
    the errno out of the args but if someone instatiates an Exception
    without any args you will get a tuple error. So this function
    abstracts all that behavior to give you a safe way to get the
    errno.
    """

    if hasattr(e, 'errno'):
        return e.errno
    elif e.args:
        return e.args[0]
    else:
        return None


def create_remote_socket(ip, port):
    # type: (str,int) -> socket.socket
    addrs = socket.getaddrinfo(ip, port, 0, socket.SOCK_STREAM,
                               socket.SOL_TCP)
    if len(addrs) == 0:
        raise Exception("getaddrinfo failed for %s:%d" % (ip, port))
    af, socktype, proto, canonname, sa = addrs[0]

    remote_sock = socket.socket(af, socktype, proto)
    remote_sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
    remote_sock.setblocking(False)
    try:
        remote_sock.connect((ip, port))
    except IOError as e:
        errno = errno_from_exception(e)
        if errno == 36:
            pass

    return remote_sock


def create_server_socket(listen_addr, listen_port):
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
    server_socket.setblocking(False)
    return server_socket

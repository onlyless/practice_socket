# -*- coding: utf-8 -*-
import logging
import select
from collections import defaultdict

POLL_NULL = 0x00
POLL_IN = 0x01
POLL_OUT = 0x04
POLL_ERR = 0x08
POLL_HUP = 0x10
POLL_NVAL = 0x20

EVENT_NAMES = {
    POLL_NULL: 'POLL_NULL',
    POLL_IN: 'POLL_IN',
    POLL_OUT: 'POLL_OUT',
    POLL_ERR: 'POLL_ERR',
    POLL_HUP: 'POLL_HUP',
    POLL_NVAL: 'POLL_NVAL',
}

# we check timeouts every TIMEOUT_PRECISION seconds
TIMEOUT_PRECISION = 10


class _KqueueLoop(object):
    MAX_EVENTS = 1024

    def __init__(self):
        self._kqueue = select.kqueue()
        self._fds = {}

    def _control(self, fd, mode, flags):
        events = []
        if mode & POLL_IN:
            events.append(select.kevent(fd, select.KQ_FILTER_READ, flags))
        if mode & POLL_OUT:
            events.append(select.kevent(fd, select.KQ_FILTER_WRITE, flags))
        for e in events:
            self._kqueue.control([e], 0)

    def poll(self, timeout):
        if timeout < 0:
            timeout = None  # kqueue behaviour
        events = self._kqueue.control(None, _KqueueLoop.MAX_EVENTS, timeout)
        results = defaultdict(lambda: POLL_NULL)
        for e in events:
            fd = e.ident
            if e.filter == select.KQ_FILTER_READ:
                results[fd] |= POLL_IN
            elif e.filter == select.KQ_FILTER_WRITE:
                results[fd] |= POLL_OUT
        return results.items()

    def register(self, fd, mode):
        self._fds[fd] = mode
        self._control(fd, mode, select.KQ_EV_ADD)

    def unregister(self, fd):
        self._control(fd, self._fds[fd], select.KQ_EV_DELETE)
        del self._fds[fd]

    def modify(self, fd, mode):
        self.unregister(fd)
        self.register(fd, mode)

    def close(self):
        self._kqueue.close()


class _SelectLoop(object):
    def __init__(self):
        self.r_inputs = set()
        self.w_inputs = set()
        self.e_inputs = set()

    def poll(self, timeout=TIMEOUT_PRECISION):
        r, w, e = select.select(self.r_inputs, self.w_inputs, self.e_inputs, timeout)
        logging.info("r_inputs:%s, w_inputs:%s, e_inputs:%s, timeout:%s", self.r_inputs, self.w_inputs, self.e_inputs,
                     timeout)
        logging.info("res r:%s,w:%s,e:%s", r, w, e)
        result = defaultdict(lambda: POLL_NULL)
        for p in [(r, POLL_IN), (w, POLL_OUT), (e, POLL_ERR)]:
            for fd in p[0]:
                result[fd] |= p[1]
        return result.items()

    def register(self, fd, mode):
        if mode & POLL_IN:
            self.r_inputs.add(fd)
        if mode & POLL_OUT:
            self.w_inputs.add(fd)
        if mode & POLL_ERR:
            self.e_inputs.add(fd)

    def unregister(self, fd):
        if fd in self.r_inputs:
            self.r_inputs.remove(fd)
        if fd in self.w_inputs:
            self.w_inputs.remove(fd)
        if fd in self.e_inputs:
            self.e_inputs.remove(fd)

    def modify(self, fd, mode):
        self.unregister(fd)
        self.register(fd, mode)


class EventLoop(object):
    def __init__(self):
        if hasattr(select, 'kqueue'):
            self._impl = _KqueueLoop()
            model = 'kqueue'
        elif hasattr(select, 'select'):
            self._impl = _SelectLoop()
            model = 'select'
        else:
            raise Exception('error')
        self._fdmap = {}  # (f, handler)
        logging.debug('using event model: %s', model)

    def poll(self, timeout=TIMEOUT_PRECISION):
        events = self._impl.poll(timeout)
        # logging.info("event:%s", events)
        return [(self._fdmap[fd][0], fd, event) for fd, event in events]

    def add(self, f, mode, handler):
        fd = f.fileno()
        logging.info("add event fd:%d", fd)
        self._fdmap[fd] = (f, handler)
        self._impl.register(fd, mode)

    def remove(self, f):
        fd = f.fileno()
        del self._fdmap[fd]
        logging.info("remove event fd:%d", fd)
        self._impl.unregister(fd)

    def modify(self, f, mode):
        fd = f.fileno()
        logging.info("modify event fd:%d", fd)
        self._impl.modify(fd, mode)

    def run(self):
        while True:
            try:
                events = self.poll()
            except (OSError, IOError) as e:
                logging.exception(e)
                continue

            for sock, fd, event in events:
                h = self._fdmap[fd][1]
                try:
                    h.handle_event(sock, fd, event)
                except Exception as e:
                    logging.exception(e)

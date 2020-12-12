# A simple Socks5 Proxy by io multiplexing

- implementation by python

todo:
   - support udp
   - implementation by golang

learn from [shadowsocks](https://github.com/shadowsocks/shadowsocks)

how to use:

   server:
   ```
   sudo python tcp_event.py
   ```

   client:
   ```
   macOS:
        brew install polipo
        polipo  socksParentProxy=$server_host:$server_port
   ```

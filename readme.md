# A simple Socks5 Proxy has no encryption  

- implementation by python and io multiplexing
- implementation by golang

todo:
   - support udp

learn from [shadowsocks](https://github.com/shadowsocks/shadowsocks)

how to use:

   server:
   ```
   python tcp_event.py
   go build -o socks_proxy main.go && ./socks_proxy 
   ```

   client:
   ```
   macOS:
        brew install polipo
        polipo  socksParentProxy=$server_host:$server_port
        export http_proxy=http://127.0.0.1:8123 https_proxy=http://127.0.0.1:8123
   ```

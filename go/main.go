package main

import (
	"./ss"
	"fmt"
	"log"
	"net"
)

func HandleConnection(conn net.Conn) {
	var err error = nil
	if err = ss.HandShake(conn); err != nil {
		log.Println("socks handshake:", err)
		return
	}
	closed := false
	defer func() {
		if !closed {
			conn.Close()
		}
	}()
	_, addr, err := ss.GetRequest(conn)
	if err != nil {
		log.Println("error getting request:", err)
		return
	}
	_, err = conn.Write([]byte{0x05, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x08, 0x43})
	if err != nil {
		fmt.Println(err)
		return
	}
	remote, err := net.Dial("tcp", addr)
	if err != nil {
		panic(err)
	}
	defer func() {
		if !closed {
			remote.Close()
		}
	}()
	go ss.PipeThenClose(conn, remote)
	ss.PipeThenClose(remote, conn)
	closed = true
	fmt.Printf("connecting to %s\n", addr)
}

func main() {
	ln, err := net.Listen("tcp", ":1082")
	if err != nil {
		panic(err)
	}
	for {
		conn, err := ln.Accept()
		if err != nil {
			fmt.Println(err)
			continue
		}
		go HandleConnection(conn)
	}
}

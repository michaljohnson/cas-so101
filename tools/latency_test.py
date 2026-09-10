#!/usr/bin/env python3
"""Network latency and throughput between the robot side and a cluster pod.

No ROS needed: it measures the network path that robot data will take.

  pod:     python3 latency_test.py server               # listens on port 9000
  laptop:  python3 latency_test.py client HOST:PORT     # RAP: localhost:9000 via port-forward

Round trip: 500 small messages (64 bytes, like joint states) at 50 Hz.
Throughput: 20 MB sent one way (camera-sized traffic).
"""
import socket
import statistics
import struct
import sys
import time

PORT = 9000
MSG = 64


def recv_exact(conn, n):
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed")
        buf += chunk
    return buf


def server():
    srv = socket.create_server(("0.0.0.0", PORT))
    print(f"listening on port {PORT}")
    while True:
        conn, addr = srv.accept()
        print("client", addr)
        with conn:
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            try:
                while True:
                    kind = recv_exact(conn, 1)
                    if kind == b"P":  # ping: echo the rest back
                        conn.sendall(b"P" + recv_exact(conn, MSG - 1))
                    else:  # bulk: read the announced number of bytes, then confirm
                        size = struct.unpack("!Q", recv_exact(conn, 8))[0]
                        while size:
                            size -= len(conn.recv(min(size, 1 << 16)))
                        conn.sendall(b"K")
            except ConnectionError:
                pass


def client(target, count=500, rate=50):
    host, port = target.rsplit(":", 1)
    conn = socket.create_connection((host, int(port)))
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    rtts = []
    for _ in range(count):
        start = time.perf_counter()
        conn.sendall(b"P" + bytes(MSG - 1))
        recv_exact(conn, MSG)
        rtts.append((time.perf_counter() - start) * 1000)
        time.sleep(1 / rate)
    rtts.sort()
    print(f"round trip, {count} x {MSG} B at {rate} Hz:  min {rtts[0]:.1f}  "
          f"median {statistics.median(rtts):.1f}  p95 {rtts[int(0.95 * count)]:.1f}  "
          f"max {rtts[-1]:.1f} ms")

    size = 20 * 1024 * 1024
    start = time.perf_counter()
    conn.sendall(b"B" + struct.pack("!Q", size))
    chunk = bytes(1 << 16)
    for _ in range(size // len(chunk)):
        conn.sendall(chunk)
    recv_exact(conn, 1)
    seconds = time.perf_counter() - start
    print(f"throughput, {size >> 20} MB one way:  {size * 8 / seconds / 1e6:.1f} Mbit/s")


if __name__ == "__main__":
    if sys.argv[1:2] == ["server"]:
        server()
    elif sys.argv[1:2] == ["client"] and len(sys.argv) == 3:
        client(sys.argv[2])
    else:
        sys.exit(__doc__)

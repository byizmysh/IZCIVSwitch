#!/usr/bin/env python3
"""probe_9026.py - 检查 CivSwitch Remote JS Loader (TCP 9026) 是否可达。

用法:
  python probe_9026.py 192.168.1.50            # 探测单台主机
  python probe_9026.py --scan                  # 扫本机所在 /24
  python probe_9026.py --scan 192.168.1.0/24   # 扫指定网段
  python probe_9026.py --banner 192.168.1.50   # 连上并读 1.5 秒（看有无欢迎数据）

只做 TCP 连接，不发送任何数据，不会干扰 loader。
"""
import ipaddress
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

PORT = 9026
CONNECT_TIMEOUT = 0.35


def try_host(ip, read_banner=False):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(CONNECT_TIMEOUT)
    try:
        s.connect((ip, PORT))
        banner = b""
        if read_banner:
            s.settimeout(1.5)
            try:
                banner = s.recv(1024)
            except socket.timeout:
                pass
        return True, banner
    except OSError:
        return False, b""
    finally:
        s.close()


def local_ipv4():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.1.1", 9))
        return s.getsockname()[0]
    except OSError:
        pass
    finally:
        s.close()
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return None


def scan(net):
    hosts = [str(h) for h in net.hosts()]
    print("scanning %d hosts on %s port %d ..." % (len(hosts), net, PORT))
    found = []
    with ThreadPoolExecutor(max_workers=min(64, len(hosts))) as pool:
        for ip, ok in zip(hosts, pool.map(lambda h: try_host(h)[0], hosts)):
            if ok:
                print("OPEN", ip)
                found.append(ip)
    if not found:
        print("no host with TCP %d open" % PORT)
    return found


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    if args[0] in ("--scan", "-s"):
        if len(args) > 1:
            net = ipaddress.ip_network(args[1], strict=False)
        else:
            ip = local_ipv4()
            if not ip:
                print("cannot determine local IP; pass a CIDR, e.g. 192.168.1.0/24")
                return 1
            print("local IP:", ip)
            net = ipaddress.ip_network(ip + "/24", strict=False)
        scan(net)
        return 0

    if args[0] in ("--banner", "-b"):
        ip = args[1]
        ok, banner = try_host(ip, read_banner=True)
        print(ip, "OPEN" if ok else "closed")
        if banner:
            print("first bytes:", banner[:200])
        return 0

    ip = args[0]
    ok, _ = try_host(ip)
    print(ip, "OPEN" if ok else "closed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

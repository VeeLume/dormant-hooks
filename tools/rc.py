"""Run RCON commands on the VPS server: ssh host python3 - cmd [cmd ...] < rc.py"""
import os
import re
import socket
import sys

d = os.path.expanduser("~/minecraft-warden")
sys.path.insert(0, d)
import rcon  # noqa: E402

s = socket.create_connection(("127.0.0.1", 25575), timeout=30)
s.sendall(rcon.packet(1, rcon.LOGIN, open(os.path.join(d, "rcon.secret")).read().strip()))
rcon.read_packet(s)
for n, c in enumerate(sys.argv[1:], start=2):
    s.sendall(rcon.packet(n, rcon.COMMAND, c))
    print(f"> {c}\n" + re.sub(r"§.", "", rcon.read_packet(s)[2]))

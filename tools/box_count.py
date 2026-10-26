"""Count entities in horizontal boxes around each player (all heights): ssh host python3 - r [r ...] < box_count.py"""
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
n = 1


def cmd(c):
    global n
    n += 1
    s.sendall(rcon.packet(n, rcon.COMMAND, c))
    return re.sub(r"§.", "", rcon.read_packet(s)[2])


total = re.search(r"Total: (\d+)", cmd("neoforge entity list"))
print("loaded:", total.group(1) if total else "?")
for r in map(int, sys.argv[1:]):
    # Every player's box, counted once per entity: tag them, count the tag, untag.
    cmd("tag @e remove boxc")
    print("  ", cmd(f"execute as @a at @s positioned ~-{r} -64 ~-{r} run tag @e[dx={2 * r},dy=500,dz={2 * r}] add boxc").strip())
    m = re.search(r"count: (\d+)", cmd("execute if entity @e[tag=boxc]"))
    print(f"within {r:3d} blocks (box, any height): {m.group(1) if m else 0}")
cmd("tag @e remove boxc")

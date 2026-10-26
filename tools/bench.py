"""Entity-tick bench on a local test server (server/mc.ps1), no players needed.

usage: bench.py setup            # force-load three far-apart areas, fill them with mobs
       bench.py measure [secs]   # sample Overworld ms/tick and print median/p90
       bench.py cmd <command>    # one RCON command

Three regions 2000 blocks apart, 5x5 chunks each, ~200 mobs each: the shape of
three players in three places. Night is frozen so the undead do not burn; natural
spawning is off so the count stays fixed. Without players nobody despawns, and with
no player near, ServerCore treats every mob as inactive: the worst case for the hooks.

RCON port: env BENCH_RCON_PORT (an mc.ps1 instance listens on its game port + 100;
`./mc.ps1 -List` shows them). Written 2026-10-25 for the instance "tess" (25691).
To run elsewhere (e.g. on the VPS), BENCH_RCON_DIR points at a directory with rcon.py
and BENCH_RCON_SECRET at the password file.
"""
import os
import random
import re
import socket
import statistics
import sys
import time

sys.path.insert(0, os.environ.get("BENCH_RCON_DIR", r"E:\vscode\minecraft\packs\sep2026\tools"))
import rcon  # noqa: E402

PORT = int(os.environ.get("BENCH_RCON_PORT", "25691"))
SECRET = open(os.environ.get("BENCH_RCON_SECRET", r"E:\vscode\minecraft\packs\sep2026\server\rcon.secret")).read().strip()
CENTERS = [(0, 0), (2000, 0), (0, 2000)]
MOBS = {"zombie": 45, "skeleton": 45, "creeper": 30, "spider": 20, "cow": 20, "sheep": 20, "chicken": 20}


class Rcon:
    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", PORT), timeout=120)
        self.n = 1
        self.s.sendall(rcon.packet(1, rcon.LOGIN, SECRET))
        rcon.read_packet(self.s)

    def __call__(self, c):
        self.n += 1
        self.s.sendall(rcon.packet(self.n, rcon.COMMAND, c))
        return re.sub(r"\u00a7.", "", rcon.read_packet(self.s)[2])


def setup(r):
    for c in ["gamerule doDaylightCycle false", "gamerule doWeatherCycle false", "gamerule doMobSpawning false",
              "time set midnight", "weather clear", "difficulty normal"]:
        print(c, "->", r(c))
    for x, z in CENTERS:
        print("forceload", x, z, "->", r(f"forceload add {x - 40} {z - 40} {x + 40} {z + 40}"))
    # Wait until every centre answers a block test, i.e. its chunks are generated and loaded.
    for x, z in CENTERS:
        for _ in range(120):
            if "passed" in r(f"execute if loaded {x + 40} 64 {z + 40}"):
                break
            time.sleep(5)
        print("loaded", x, z)
    rnd = random.Random(1)
    for x, z in CENTERS:
        for mob, k in MOBS.items():
            for _ in range(k):
                px, pz = x + rnd.randint(-32, 32), z + rnd.randint(-32, 32)
                r(f"execute positioned {px} 0 {pz} positioned over motion_blocking_no_leaves "
                  f"run summon minecraft:{mob} ~ ~ ~")
        print("summoned at", x, z)
    print(r("neoforge entity list"))


def measure(r, secs):
    samples = []
    end = time.time() + secs
    while time.time() < end:
        m = re.search(r"Overworld: [\d.]+ TPS \(([\d.]+) ms/tick\)", r("neoforge tps overworld"))
        if m:
            samples.append(float(m.group(1)))
        time.sleep(3)
    samples.sort()
    print(f"{len(samples)} samples, ms/tick median {statistics.median(samples):.1f}, "
          f"p90 {samples[int(0.9 * (len(samples) - 1))]:.1f}, min {samples[0]:.1f}, max {samples[-1]:.1f}")
    print(r("neoforge entity list").splitlines()[0])


r = Rcon()
if sys.argv[1] == "setup":
    setup(r)
elif sys.argv[1] == "measure":
    measure(r, int(sys.argv[2]) if len(sys.argv) > 2 else 90)
else:
    print(r(" ".join(sys.argv[2:])))

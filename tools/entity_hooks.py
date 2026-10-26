# /// script
# dependencies = ["grpcio-tools", "protobuf"]
# ///
"""Which mods run inside entity ticking, and how much of the server thread they cost.

usage: uv run entity_hooks.py <proto dir> <file.sparkprofile>

Inside ServerLevel.tickNonPassenger/tickPassenger, the first frame on each stack that
belongs to a mod is charged with its inclusive time. A frame belongs to a mod if spark
knows the class's source, or if its name is a mixin handler carrying a mod id
(handler$abc000$modid$name, wrapMethod$..., redirect$..., ...). Vanilla frames below a
mod frame are charged to that mod; mod frames below another mod frame are not counted
twice.
"""
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

proto_dir, profile = Path(sys.argv[1]), Path(sys.argv[2])
out = Path(tempfile.mkdtemp())
subprocess.run([sys.executable, "-m", "grpc_tools.protoc", f"-I{proto_dir}", f"--python_out={out}",
                "spark/spark.proto", "spark/spark_sampler.proto"], check=True)
sys.path.insert(0, str(out))
from spark import spark_sampler_pb2  # noqa: E402

data = spark_sampler_pb2.SamplerData()
data.ParseFromString(profile.read_bytes())
src = dict(data.class_sources)
thread = next(t for t in data.threads if "Server thread" in t.name)
nodes = thread.children
total = sum(thread.times)

MIXIN = re.compile(r"^(?:handler|wrapMethod|redirect|modify\w*|localvar|wrapOperation|wrapWithCondition)"
                   r"\$[a-z0-9]+\$([a-z0-9_]+)\$(.*)$", re.I)
ENTRY = {"tickNonPassenger", "tickPassenger"}
# Frames that are plumbing, not the mod doing work.
PLUMBING = ("neoforge", "minecraft")


def mod_of(n):
    m = MIXIN.match(n.method_name)
    if m:
        return m.group(1), f"{n.class_name.rsplit('.', 1)[-1]}.{m.group(2)} (mixin)"
    s = src.get(n.class_name) or src.get(n.class_name.split("$")[0])
    if s and s not in PLUMBING:
        return s, f"{n.class_name.rsplit('.', 1)[-1]}.{n.method_name}"
    return None


entity_total = 0.0
by_mod = Counter()
by_site = defaultdict(Counter)


def walk(i, inside):
    global entity_total
    n = nodes[i]
    t = sum(n.times)
    if not inside and n.class_name.endswith("ServerLevel") and n.method_name in ENTRY:
        entity_total += t
        inside = True
        # nested tickPassenger under tickNonPassenger is counted once by the outer frame
    elif inside:
        owner = mod_of(n)
        if owner:
            by_mod[owner[0]] += t
            by_site[owner[0]][owner[1]] += t
            return
    for c in n.children_refs:
        walk(c, inside)


sys.setrecursionlimit(100000)
for r in thread.children_refs:
    walk(r, False)

print(f"entity ticking: {100 * entity_total / total:.1f} % of the server thread")
print(f"charged to mods: {100 * sum(by_mod.values()) / total:.1f} %; the rest is vanilla entity code\n")
for mod, t in by_mod.most_common(30):
    print(f"{100 * t / total:5.2f} %  {mod}")
    for site, st in by_site[mod].most_common(4):
        if st >= 0.001 * total:
            print(f"           {100 * st / total:5.2f} %  {site}")

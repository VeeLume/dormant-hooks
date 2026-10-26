# /// script
# dependencies = ["grpcio-tools", "protobuf"]
# ///
"""Split entity ticking into NeoForge's EntityTickEvent hooks and the tick itself.

usage: uv run hook_split.py <proto dir> <file.sparkprofile>

Inside ServerLevel.tickNonPassenger/tickPassenger, every direct child is bucketed by
frame name; the EntityTickEvent subtrees (EventHooks.fireEntityTickPre/Post, also
behind MixinExtras wrappers such as dormant-hooks' own) are further charged to the
first mod frame below them, as in entity_hooks.py.
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
PLUMBING = ("neoforge", "minecraft")


def short(n):
    return f"{n.class_name.rsplit('.', 1)[-1]}.{n.method_name}"


def mod_of(n):
    m = MIXIN.match(n.method_name)
    if m:
        return m.group(1), f"{n.class_name.rsplit('.', 1)[-1]}.{m.group(2)} (mixin)"
    s = src.get(n.class_name) or src.get(n.class_name.split("$")[0])
    if s and s not in PLUMBING:
        return s, short(n)
    return None


entity_total = 0.0
children = Counter()           # direct children of the entry frames, by name
grand = defaultdict(Counter)   # one level further for the interesting children
hooks = {"Pre": Counter(), "Post": Counter()}
hook_sites = {"Pre": defaultdict(Counter), "Post": defaultdict(Counter)}
hook_total = Counter()


def charge(i, phase):
    n = nodes[i]
    owner = mod_of(n)
    if owner:
        t = sum(n.times)
        hooks[phase][owner[0]] += t
        hook_sites[phase][owner[0]][owner[1]] += t
        return
    for c in n.children_refs:
        charge(c, phase)


def walk(i, inside):
    global entity_total
    n = nodes[i]
    t = sum(n.times)
    entry = n.class_name.endswith("ServerLevel") and n.method_name in ENTRY
    if entry and not inside:
        entity_total += t
    if entry:
        for c in n.children_refs:
            cn = nodes[c]
            ct = sum(cn.times)
            name = short(cn)
            if cn.class_name.endswith("ServerLevel") and cn.method_name in ENTRY:
                walk(c, True)  # passengers: counted inside the outer frame already
                continue
            children[name] += ct
            for g in cn.children_refs:
                grand[name][short(nodes[g])] += sum(nodes[g].times)
            find_hooks(c)
        return
    for c in n.children_refs:
        walk(c, inside)


WRAPPER = re.compile(r"^(?:wrapOperation|wrapWithCondition)\$|^mixinextras\$bridge\$|^call$")


def find_hooks(i, depth=4):
    """A hook frame, directly or behind MixinExtras wrappers (dormant-hooks wraps Pre in a WrapOperation)."""
    n = nodes[i]
    m = re.match(r"fireEntityTick(Pre|Post)", n.method_name)
    if m:
        hook_total[m.group(1)] += sum(n.times)
        for g in n.children_refs:
            charge(g, m.group(1))
    elif depth > 0 and WRAPPER.match(n.method_name):
        for c in n.children_refs:
            find_hooks(c, depth - 1)


sys.setrecursionlimit(100000)
for r in thread.children_refs:
    walk(r, False)


def pct(t):
    return f"{100 * t / total:5.2f} %"


print(f"server thread samples: {total:.0f}; entity ticking {pct(entity_total)}\n")
print("direct children of tickNonPassenger/tickPassenger:")
for name, t in children.most_common(15):
    print(f"  {pct(t)}  {name}")
    for g, gt in grand[name].most_common(4):
        if gt >= 0.002 * total:
            print(f"             {pct(gt)}  {g}")
for phase in ("Pre", "Post"):
    print(f"\nEntityTickEvent.{phase}: {pct(hook_total[phase])}")
    for mod, t in hooks[phase].most_common(20):
        if t >= 0.001 * total:
            print(f"  {pct(t)}  {mod}")
            for site, st in hook_sites[phase][mod].most_common(3):
                if st >= 0.001 * total:
                    print(f"             {pct(st)}  {site}")

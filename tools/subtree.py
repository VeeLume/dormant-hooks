# /// script
# dependencies = ["grpcio-tools", "protobuf"]
# ///
"""Merged subtree under every frame whose method name contains a pattern: uv run subtree.py <proto> <profile> <pattern> [depth]"""
import subprocess, sys, tempfile
from collections import defaultdict
from pathlib import Path
proto_dir, profile, pat = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
depth = int(sys.argv[4]) if len(sys.argv) > 4 else 3
out = Path(tempfile.mkdtemp())
subprocess.run([sys.executable, "-m", "grpc_tools.protoc", f"-I{proto_dir}", f"--python_out={out}", "spark/spark.proto", "spark/spark_sampler.proto"], check=True)
sys.path.insert(0, str(out))
from spark import spark_sampler_pb2
d = spark_sampler_pb2.SamplerData(); d.ParseFromString(profile.read_bytes())
th = next(t for t in d.threads if "Server thread" in t.name); nodes = th.children; total = sum(th.times)
lab = lambda n: f"{n.class_name.rsplit('.',1)[-1]}.{n.method_name}"
agg = defaultdict(float)
def collect(i, path, lvl):
    n = nodes[i]; p = path + (lab(n),); agg[p] += sum(n.times)
    if lvl < depth:
        for c in n.children_refs: collect(c, p, lvl + 1)
def find(i, inside):
    n = nodes[i]
    if pat in f"{n.class_name}.{n.method_name}" and not inside:
        collect(i, (), 0); return
    for c in n.children_refs: find(c, inside)
sys.setrecursionlimit(100000)
for r in th.children_refs: find(r, False)
for p, t in sorted(agg.items()):
    if t >= 0.002 * total: print(f"{'  '*(len(p)-1)}{100*t/total:5.2f} %  {p[-1]}")

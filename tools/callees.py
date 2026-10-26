# /// script
# dependencies = ["grpcio-tools", "protobuf"]
# ///
"""Self time and direct callees of every frame named Class.method: uv run callees.py <proto> <profile> <Class.method> ..."""
import subprocess, sys, tempfile
from collections import Counter
from pathlib import Path
proto_dir, profile = Path(sys.argv[1]), Path(sys.argv[2])
out = Path(tempfile.mkdtemp())
subprocess.run([sys.executable, "-m", "grpc_tools.protoc", f"-I{proto_dir}", f"--python_out={out}", "spark/spark.proto", "spark/spark_sampler.proto"], check=True)
sys.path.insert(0, str(out))
from spark import spark_sampler_pb2
d = spark_sampler_pb2.SamplerData(); d.ParseFromString(profile.read_bytes())
th = next(t for t in d.threads if "Server thread" in t.name); nodes = th.children; total = sum(th.times)
lab = lambda n: f"{n.class_name.rsplit('.', 1)[-1]}.{n.method_name}"
for want in sys.argv[3:]:
    incl, kids = 0.0, Counter()
    for n in nodes:
        if lab(n) != want:
            continue
        incl += sum(n.times)
        for c in n.children_refs:
            kids[lab(nodes[c]) + (f":{nodes[c].parent_line_number}" if nodes[c].parent_line_number else "")] += sum(nodes[c].times)
    print(f"{100 * incl / total:6.3f} %  {want}  (self {100 * (incl - sum(kids.values())) / total:.3f} %)")
    for k, t in kids.most_common(12):
        print(f"   {100 * t / total:6.3f} %  {k}")

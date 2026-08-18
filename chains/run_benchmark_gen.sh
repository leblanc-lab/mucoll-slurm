#!/bin/bash
# Generate the immutable particle-gun inputs used by the physics benchmarks.
# This script runs inside the mucoll-sim container; submit_benchmark_gen.py is
# the NERSC/Slurm entry point.
set -euo pipefail

OUTPUT_DIR="${1:?usage: run_benchmark_gen.sh OUTPUT_DIR [EVENTS] [VERSION] [SEED] [IMAGE_REF] [IMAGE_DIGEST] [BENCHMARK_SHA]}"
EVENTS="${2:-10000}"
DATASET_VERSION="${3:-v1}"
SEED="${4:-12345}"
IMAGE_REF="${5:-unknown}"
IMAGE_DIGEST="${6:-unknown}"
BENCHMARK_SHA="${7:-unknown}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BENCHMARKS_DIR="${WORK_DIR}/mucoll-benchmarks"
PGUN="${BENCHMARKS_DIR}/generation/pgun/pgun_edm4hep.py"

if [[ ! -f "${PGUN}" ]]; then
    echo "ERROR: particle-gun script not found: ${PGUN}" >&2
    exit 1
fi

# The image setup references optional environment variables and is not written
# for nounset/pipefail. Restore strict mode immediately after sourcing it.
set +euo pipefail
# shellcheck disable=SC1091
source /opt/setup_mucoll.sh
set -euo pipefail

mkdir -p "${OUTPUT_DIR}"

labels=(muon electron pion photon)
pdgs=(13 11 211 22)

echo "Generating benchmark GEN inputs"
echo "  output     : ${OUTPUT_DIR}"
echo "  events/file: ${EVENTS}"
echo "  version    : ${DATASET_VERSION}"
echo "  seed       : ${SEED}"

for i in "${!labels[@]}"; do
    label="${labels[$i]}"
    pdg="${pdgs[$i]}"
    output="${OUTPUT_DIR}/gen-${label}-${DATASET_VERSION}.edm4hep.root"
    comment="MuColl benchmark input ${DATASET_VERSION}: ${label}, PDG ${pdg}, seed ${SEED}"

    echo "--- ${label} (PDG ${pdg}) ---"
    python3 "${PGUN}" \
        --events "${EVENTS}" \
        --particles 1 \
        --seed "${SEED}" \
        --pdg "${pdg}" \
        --pt 1 100 \
        --theta 10 170 \
        --phi 0 360 \
        --comment "${comment}" \
        -- "${output}"
done

python3 - \
    "${OUTPUT_DIR}" "${DATASET_VERSION}" "${EVENTS}" "${SEED}" \
    "${IMAGE_REF}" "${IMAGE_DIGEST}" "${BENCHMARK_SHA}" "${PGUN}" <<'PY'
import datetime
import hashlib
import json
import pathlib
import sys

(
    output_dir,
    dataset_version,
    events,
    seed,
    image_ref,
    image_digest,
    benchmark_sha,
    pgun_path,
) = sys.argv[1:]
output_dir = pathlib.Path(output_dir)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


particles = [
    ("muon", 13),
    ("electron", 11),
    ("pion", 211),
    ("photon", 22),
]
files = []
for label, pdg in particles:
    path = output_dir / f"gen-{label}-{dataset_version}.edm4hep.root"
    files.append(
        {
            "label": label,
            "pdg": pdg,
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    )

manifest = {
    "schema_version": 1,
    "dataset_version": dataset_version,
    "stage": "GEN",
    "format": "EDM4hep ROOT",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "events_per_file": int(events),
    "particles_per_event": 1,
    "seed": int(seed),
    "kinematics": {
        "pt_gev": {"distribution": "uniform", "min": 1.0, "max": 100.0},
        "theta_deg": {"distribution": "uniform", "min": 10.0, "max": 170.0},
        "phi_deg": {"distribution": "uniform", "min": 0.0, "max": 360.0},
    },
    "generator": {
        "script": "generation/pgun/pgun_edm4hep.py",
        "script_sha256": sha256(pathlib.Path(pgun_path)),
        "mucoll_benchmarks_commit": benchmark_sha,
    },
    "container": {"reference": image_ref, "digest": image_digest},
    "files": files,
}

manifest_path = output_dir / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {manifest_path}")
for entry in files:
    print(f"{entry['sha256']}  {entry['name']}")
PY

echo "Benchmark GEN input generation complete."

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONTROL_ENV="${CONTROL_ENV:-uav-control}"
YOLO_ENV="${YOLO_ENV:-yolo}"
CONTROL_PYTHON="${CONTROL_PYTHON:-3.10}"
YOLO_PYTHON="${YOLO_PYTHON:-3.11}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda was not found. Install Miniconda or Anaconda first." >&2
  exit 1
fi

env_exists() {
  conda env list | awk '{print $1}' | grep -Fxq "$1"
}

create_env_if_missing() {
  local env_name="$1"
  local python_version="$2"

  if env_exists "${env_name}"; then
    echo "Conda env '${env_name}' already exists; skipping create."
  else
    echo "Creating conda env '${env_name}' with Python ${python_version}..."
    conda create -n "${env_name}" "python=${python_version}" -y
  fi
}

install_requirements() {
  local env_name="$1"
  local req_file="$2"

  echo "Installing ${req_file} into '${env_name}'..."
  conda run -n "${env_name}" python -m pip install --upgrade pip
  conda run -n "${env_name}" python -m pip install -r "${REPO_ROOT}/${req_file}"
}

create_env_if_missing "${CONTROL_ENV}" "${CONTROL_PYTHON}"
install_requirements "${CONTROL_ENV}" "requirements-control.txt"

create_env_if_missing "${YOLO_ENV}" "${YOLO_PYTHON}"
install_requirements "${YOLO_ENV}" "requirements-yolo.txt"

echo
echo "Control environment:"
conda run -n "${CONTROL_ENV}" python --version

echo
echo "YOLO environment:"
conda run -n "${YOLO_ENV}" python --version
conda run -n "${YOLO_ENV}" python - <<'PY'
try:
    import torch
    print("torch", torch.__version__)
    print("cuda_available", torch.cuda.is_available())
except Exception as exc:
    print("torch check skipped:", exc)
PY

echo
echo "Done."
echo "Next:"
echo "  conda activate ${CONTROL_ENV}"
echo "  cd ${REPO_ROOT}"
echo "  python -m app.main --no-yolo-udp --run-seconds 1 --send-commands false --no-ui"

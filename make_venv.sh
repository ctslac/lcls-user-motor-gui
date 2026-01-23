#!/usr/bin/bash
# set -e
cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
if [ -d .venv ]; then
    echo ".venv folder already exists, exiting."
    exit 1
fi

PYVER="$(python3 --version | cut -f 2 -d ' ')"
MINOR="$(echo "${PYVER}" | cut -f 2 -d '.')"

if [ "${MINOR}" -lt "6" ]; then
    echo "This requires python 3.12.10 or greater. You are using ${PYVER}"
    exit 1
fi

echo "Creating venv using your active site-packages"
source /cds/group/pcds/engineering_tools/latest-released/scripts/pcds_conda
echo "pcds conda sourced"
python3 -m venv --system-site-packages .venv
echo "Activating venv"
# shellcheck disable=SC1091
source .venv/bin/activate
# TODO package-ize lcls-scan-gui and install it directly
echo "Using $(which pip) to install requirements"
pip install -r requirements.txt

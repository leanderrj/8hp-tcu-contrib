#!/usr/bin/env bash
# Regenerate zf8hp_tcu.{h,c} from the canonical DBC.
# Run from the repo root, in a venv with `cantools` installed.
#
#   python3 -m venv venv && source venv/bin/activate
#   pip install cantools
#   bash proposals/firmware/can_codegen/generate.sh
#
# The output overwrites zf8hp_tcu.{h,c} in this directory. Hand edits to
# the generated files will be lost — anything custom belongs in the C++
# wrapper (Can_ZF8HP.{h,cpp}), not in the codegen output.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
DBC="$DIR/../../dbc/zf8hp-tcu.dbc"

cd "$DIR"
python3 -m cantools generate_c_source "$DBC" --output-directory .
echo "Generated: $(ls -1 zf8hp_tcu.{h,c})"

#!/bin/sh
# Snapshot the current GOLIAT working tree + validation driver into build/goliat_bundle.zip
set -e
V=$(cd "$(dirname "$0")/.." && pwd)
B=$V/build
mkdir -p $B/stage
cd "$V/.."
rsync -a --delete --exclude __pycache__ --exclude '*.pyc' goliat $B/stage/
cp pyproject.toml $B/stage/
rsync -a --delete --exclude __pycache__ $V/runner/valdriver $B/stage/
{ echo "git_head=$(git rev-parse HEAD)"; echo "goliat_tree_sha256=$(cd $B/stage && find goliat -type f | sort | xargs sha256sum | sha256sum | cut -d' ' -f1)"; echo "dirty_files:"; git status --short goliat; } > $B/stage/BUNDLE_MANIFEST.txt
cd $B/stage && zip -qr $B/goliat_bundle.new.zip . && mv -f $B/goliat_bundle.new.zip $B/goliat_bundle.zip
cd $V/tools/wheels && zip -qr $B/wheels.new.zip *.whl && mv -f $B/wheels.new.zip $B/wheels.zip
cp $V/runner/main.py $B/main.py
ls -la $B
cat $B/stage/BUNDLE_MANIFEST.txt

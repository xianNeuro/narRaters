#!/bin/bash
# segcausal branch - START HERE
# Double-click to open the rater task (story segmentation + causal rating).
# On this branch every launcher (this file, narRater.app, install.sh) goes
# through install.sh, which starts `narraters serve --task segment-causal`.
# (On main, this file opened the pipeline app at /pipeline-config.)
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$PROJECT_ROOT/install.sh"

#!/usr/bin/env bash
# Copy the Geist font files from the pinned `geist` package into public/fonts (gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p public/fonts
cp node_modules/geist/dist/fonts/geist-sans/Geist-Variable.woff2 public/fonts/
cp node_modules/geist/dist/fonts/geist-mono/GeistMono-Variable.woff2 public/fonts/
ls public/fonts

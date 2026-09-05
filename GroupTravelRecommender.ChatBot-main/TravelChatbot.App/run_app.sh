#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec python -m streamlit run app.py

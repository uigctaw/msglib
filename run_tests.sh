#!/bin/bash

set -euo pipefail

echo -e "\nPytest:"
poetry run pytest tests ; echo Success!
echo -e "\nBandit:"
poetry run bandit -c pyproject.toml -r . ; echo Success!
echo -e "\nMypy:"
poetry run mypy . --show-error-codes --check-untyped-defs ; echo Success!

echo -e "\nFlake8:"
poetry run flake8 --per-file-ignores="msglib/__init__.py:F401" .
echo Success!

echo -e "\nPylint msglib:"
poetry run pylint msglib ; echo Success!
echo -e "\nPylint tests:"
poetry run pylint tests --disable=unbalanced-tuple-unpacking ; echo Success!

echo -e "\nSUCCESS!"


#!/bin/bash
set -e
set -x

poetry config repositories.testpypi https://test.pypi.org/legacy/
poetry config pypi-token.testpypi ${PYPI_TEST_TOKEN}
poetry publish --repository testpypi

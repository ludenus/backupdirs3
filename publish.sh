#!/bin/bash
set -e
set -x

PACKAGE_NAME=backupdirs3
VERSION=$(poetry version -s)
EXISTS=$(curl -fs https://test.pypi.org/pypi/$PACKAGE_NAME/$VERSION/json || echo "not found")
if [[ $EXISTS == "not found" ]]; then
    echo "Version $VERSION does not exist, proceeding with upload."
    poetry config repositories.testpypi https://test.pypi.org/legacy/
    poetry config pypi-token.testpypi ${PYPI_TEST_TOKEN}
    poetry publish --repository testpypi

else
    echo "Version $VERSION already exists, skipping upload."
    exit 0
fi


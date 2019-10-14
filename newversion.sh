#!/bin/bash

set -e

version="$1"

if [[ -z "$version" ]]; then
    echo "Usage: $0 <version>" >&2
    echo "No version set" >&2
    exit 1
fi

sed -i -e "s/^Version.*/Version: \\t${version}/" python-varlink.spec
curl -L -O https://github.com/varlink/python-varlink/archive/${version}/python-varlink-${version}.tar.gz
rm -fr docs/build
python3 setup.py build_sphinx --source-dir=docs/ --build-dir=docs/build --all-files
GIT_DEPLOY_DIR=$(pwd)/docs/build/html GIT_DEPLOY_BRANCH=gh-pages ./git-deploy-branch.sh -m "doc update"

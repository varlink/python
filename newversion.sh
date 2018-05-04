#!/bin/bash

set -e

version="$1"

sed -i -e "s/^Version.*/Version: \t${version}/" python-varlink.spec
sed -i -e "s/^[ \t]*version.*=.*/    version = \"${version}\",/" setup.py
git commit -m "version ${version}" python-varlink.spec setup.py
git tag --sign "${version}"
git push
git push --tags
rm -fr dist
python3 setup.py bdist_wheel --universal
python3 setup.py sdist
twine upload --skip-existing --sign-with gpg2 -s dist/*
wget https://github.com/varlink/python-varlink/archive/${version}/python-varlink-${version}.tar.gz
rm -fr docs/build
python3 setup.py build_sphinx --source-dir=docs/ --build-dir=docs/build --all-files
GIT_DEPLOY_DIR=$(pwd)/docs/build/html GIT_DEPLOY_BRANCH=gh-pages ./git-deploy-branch.sh -m "doc update"

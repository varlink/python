PYTHON := $(shell python -c 'import platform;print(platform.python_version().split(".")[0])')
PYTHON2 := $(shell if which python2 &>/dev/null;then which python2; elif [ "$(PYTHON)" == 2 ]; then which python; fi)
PYTHON3 := $(shell if which python3 &>/dev/null;then which python3; elif [ "$(PYTHON)" == 3 ]; then which python; fi)

all: build
.PHONY: all

build:
	rm -fr build
	python3 setup.py bdist_wheel --universal
.PHONY: build

clean:
	rm -rf dist build
.PHONY: clean

check:
	if [ -x "$(PYTHON2)" ]; then $(PYTHON2) -m unittest varlink;fi
	if [ -x "$(PYTHON3)" ]; then $(PYTHON3) -m unittest varlink;fi
.PHONY: check

docs:
	python3 setup.py build_sphinx --source-dir=docs/ --build-dir=docs/build --all-files
.PHONY: docs

docsdeploy: docs
	GIT_DEPLOY_DIR=$(PWD)/docs/build/html GIT_DEPLOY_BRANCH=gh-pages ./git-deploy-branch.sh -m "doc update"
.PHONY: docsdeploy

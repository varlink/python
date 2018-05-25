all: build
.PHONY: all

build:
	python3 setup.py bdist_wheel --universal
.PHONY: build

clean:
	rm -rf dist build
.PHONY: clean

check:
	python2 -m unittest discover
	python3 -m unittest discover
.PHONY: check

docs:
	python3 setup.py build_sphinx --source-dir=docs/ --build-dir=docs/build --all-files
.PHONY: docs

docsdeploy: docs
	GIT_DEPLOY_DIR=$(PWD)/docs/build/html GIT_DEPLOY_BRANCH=gh-pages ./git-deploy-branch.sh -m "doc update"
.PHONY: docsdeploy

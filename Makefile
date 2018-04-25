test:
	python -m unittest discover -s ./varlink -t ./
	python3 -m unittest discover -s ./varlink -t ./

all: test


.PHONY: test lint build check

test:
	python -m unittest discover -s tests -v

lint:
	python -m compileall -q core models strategies execution backtests historical server
	python -m pyflakes core models strategies execution backtests historical server

build:
	cd frontend && npm ci && npm run build

check: lint test build

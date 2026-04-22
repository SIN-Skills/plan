.PHONY: install lint test build clean

install:
	pip install -e .[dev]

lint:
	ruff check src tests

test:
	pytest -q

build:
	python -m build

clean:
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .plan

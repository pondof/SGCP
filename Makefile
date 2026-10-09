# The venv lives in .venv.nosync/ so iCloud Drive does not try to sync it.
VENV   := .venv.nosync
PYTHON := $(VENV)/bin/python

.PHONY: venv test clean

venv: $(VENV)/.installed

$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	touch $@

test: venv
	$(PYTHON) -m pytest -q

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache

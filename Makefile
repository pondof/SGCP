# The venv lives in .venv.nosync/ so iCloud Drive does not try to sync it.
VENV   := .venv.nosync
PYTHON := $(VENV)/bin/python

.PHONY: venv test instances literature literature-big clean

venv: $(VENV)/.installed

$(VENV)/.installed: requirements.txt
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	touch $@

test: venv
	$(PYTHON) -m pytest -q

# Perfect-graph suite (Şeker et al., 2021): small, medium and large tiers.
# Deterministic: regenerating yields byte-identical files (see instances/manifest.csv).
instances: venv
	$(PYTHON) -m src.generator suite

# Literature benchmark (Furini, Malaguti & Santini, 2018), pinned to a commit.
literature: venv
	$(PYTHON) -m src.literature --sets random nsfnet ring

# n = 1000 instances (~200 MB); kept out of git.
literature-big: venv
	$(PYTHON) -m src.literature --sets big-random

clean:
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache

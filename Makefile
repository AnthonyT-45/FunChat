# Run `make setup` once, then `make format` to format your code
# Configure formatting rules in pyproject.toml

ifeq ($(OS),Windows_NT)
VENV_PY = .venv/Scripts/python.exe
else
VENV_PY = .venv/bin/python
endif

.PHONY: setup format

setup: $(VENV_PY)

$(VENV_PY):
	python -m venv .venv
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev]"

format: $(VENV_PY)
	$(VENV_PY) -m isort .
	$(VENV_PY) -m black .
	$(VENV_PY) -m flake8 .
PYTHON ?= python
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: install daily optimize backtest test clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -r requirements.txt

daily:
	$(VENV_PYTHON) examples/run_enhanced_daily.py

optimize:
	$(VENV_PYTHON) examples/run_parameter_optimization.py

backtest:
	$(VENV_PYTHON) examples/run_batch_backtest.py

test:
	$(VENV_PYTHON) -m unittest discover -s tests -p "test_*.py"

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -f logs/app.log

PYTHON ?= python
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_PIP := $(VENV)/bin/pip

.PHONY: install daily daily-premarket daily-midday daily-close email-premarket email-midday email-close optimize backtest test clean

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -r requirements.txt

daily:
	$(VENV_PYTHON) examples/run_enhanced_daily.py

daily-premarket:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot premarket

daily-midday:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot midday

daily-close:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot close

email-premarket:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot premarket --send-email --attach-excel --require-trading-day

email-midday:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot midday --send-email --attach-excel --require-trading-day

email-close:
	$(VENV_PYTHON) examples/run_enhanced_daily.py --slot close --send-email --attach-excel --require-trading-day

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

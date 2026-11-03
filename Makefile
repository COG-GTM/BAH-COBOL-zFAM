# Unit tests for the zFAM COBOL programs (GnuCOBOL + mocked CICS).
PYTHON ?= python3

.PHONY: test clean

test:
	$(PYTHON) -m pytest

clean:
	rm -rf build/tests .pytest_cache

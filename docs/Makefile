# Documentation build helper for HSX

DOXYGEN ?= doxygen
PYTHON ?= python

.PHONY: docs clean

docs:
	$(PYTHON) -c "import os, subprocess, sys; config='Doxyfile';\nif not os.path.exists(config):\n    print('Doxyfile missing; unable to build docs.', file=sys.stderr); sys.exit(1);\nraise SystemExit(subprocess.call([sys.argv[1], config]))" $(DOXYGEN)

clean:
	$(PYTHON) -c "import shutil; shutil.rmtree('html', ignore_errors=True); shutil.rmtree('latex', ignore_errors=True)"
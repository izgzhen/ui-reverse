PYFILES := $(shell find . -maxdepth 3 -name "*.py")

check: $(PYFILES)
	ck $(PYFILES)

link-venv:
	ln -s $(shell poetry env info --path) .venv
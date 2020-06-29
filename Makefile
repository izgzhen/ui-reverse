PYFILES := $(shell find . -maxdepth 3 -name "*.py")

check: $(PYFILES)
	ck $(PYFILES)
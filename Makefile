PYFILES := $(shell find . -maxdepth 3 -name "*.py")

check: $(PYFILES)
	ck $(PYFILES)

link-venv:
	ln -s $(shell poetry env info --path) .venv

TEST01_APK := tests/test01/app/build/outputs/apk/debug/app-debug.apk
TEST02_APK := tests/test02/app/build/outputs/apk/debug/app-debug.apk

build-test01:
	cd tests/test01; ./gradlew assembleDebug

build-test02:
	cd tests/test02; ./gradlew assembleDebug

test-test01: build-test01
	python3 scripts/search-res-xml.py --apk $(TEST01_APK) --src_path tests/test01/ --uix_path tests/test01.xml > test1_result.txt

test-test02: build-test02
	python3 scripts/search-res-xml.py --apk $(TEST02_APK) --src_path tests/test02/ --uix_path tests/test02.xml > test2_result.txt

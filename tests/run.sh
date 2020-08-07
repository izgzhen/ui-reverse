set -e
set -x

cd tests/test01
./gradlew assembleDebug
cd -

cd tests/test02
./gradlew assembleDebug
cd -


python scripts/search-res-xml.py --apk tests/test01/app/build/outputs/apk/debug/app-debug.apk --src_path tests/test01 --run_markii T --run_jadx T

python scripts/search-res-xml.py --apk tests/test02/app/build/outputs/apk/debug/app-debug.apk --src_path tests/test02 --run_markii T --run_jadx T

set -e
set -x

cd tests/test01
./gradlew assembleDebug
cd -

jadx_dir/bin/jadx tests/test01/app/build/outputs/apk/debug/app-debug.apk -d /tmp/jadx_apk_dir

python scripts/search-res-xml.py /tmp/jadx_apk_dir tests/test01.xml
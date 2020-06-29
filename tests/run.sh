set -e
set -x

jadx_dir/bin/jadx tests/test01/app/build/outputs/apk/debug/app-debug.apk -d /tmp/jadx_apk_dir

scripts/adb-uidump /tmp/uix.xml

python scripts/search-res-xml.py /tmp/jadx_apk_dir /tmp/uix.xml
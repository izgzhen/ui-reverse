set -e
set -x

cd tests/test01
./gradlew assembleDebug
cd -


cd tests/test02
./gradlew assembleDebug
cd -

# cd ..

test01apk="tests/test01/app/build/outputs/apk/debug/app-debug.apk"
test02apk="tests/test02/app/build/outputs/apk/debug/app-debug.apk"

# jadx_dir/bin/jadx tests/test01/app/build/outputs/apk/debug/app-debug.apk -d /tmp/jadx_apk_dir

# python scripts/search-res-xml.py /tmp/jadx_apk_dir tests/test01.xml

python scripts/search-res-xml.py --apk $test01apk --src_path tests/test01 --markii_file_loc test01markii --jadx_file_dir /tmp/jadx_apk_dir1 --uix_path tests/test01.xml --run_markii F --run_jadx T

python scripts/search-res-xml.py --apk $test02apk --src_path tests/test01 --markii_file_loc test02markii --jadx_file_dir /tmp/jadx_apk_dir2 --uix_path tests/test02.xml --run_markii F --run_jadx T

# --jadx_file_dir /tmp/jadx_apk_dir
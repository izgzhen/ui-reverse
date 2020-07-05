import os
from msbase.subprocess_ import try_call_std
from msbase.utils import getenv

MARKII_DIR = getenv("MARKII_DIR")

def run_markii(apk: str, facts_dir: str):
    """
    Depends on Scala SBT by default
    """
    os.system("mkdir -p " + facts_dir)
    # Run markii
    try_call_std(["bash", MARKII_DIR + "/build-run-markii.sh", apk, facts_dir], output=False, timeout_s=1200)

# Echo command line and fail on any error
set -e
set -x

wget --quiet https://github.com/skylot/jadx/releases/download/v1.1.0/jadx-1.1.0.zip
unzip jadx-1.1.0.zip -d jadx_dir

# Move the /tmp to avoid `make check` work on it
wget --quiet -O /tmp/get-poetry.py https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py
pip3 install --upgrade pip
python3 /tmp/get-poetry.py --version 1.0.2
~/.poetry/bin/poetry install
ln -s $(~/.poetry/bin/poetry env info --path) .venv
~/.poetry/bin/poetry add mypy pylint
# Code Reviewer on GitLab CI

## セットアップ

- Python 3.12.5 on Windows11

```powershell
# Pythonをインストール
winget install --id Python.Python.3.12 --version 3.12.5
python --version
python -m pip install --upgrade setuptools
python -m pip install --upgrade pip

# 仮想環境を作成
python -m venv .venv
./.venv/Scripts/activate
pip install flake8 black python-dotenv unidiff PyGithub python-gitlab openai ollama langchain langchain-core langchain-community faiss-cpu

# 終了
deactivate
Remove-Item –path ./.venv –recurse
```

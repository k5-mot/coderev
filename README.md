# Code Reviewer on GitLab CI

## 概要図

### MR Summary Chain
```mermaid
flowchart TD
    GLS[(GitLab API\nMerge Request)]
    GLE[(GitLab API\nUpdate title & desc of MR)]
    GL1[Changed files\n- filepath\n- language\n- diff]
    GL2[Merge Request\n- title\n- description]
    CSS[Code Summaries]

    GLS-->|GET| GL1
    GLS-->|GET| GL2

    GL1-->|Context| CSC
    CSC-->|Union| CSS

    GL2-->|Context| MSC
    CSS-->|Context| MSC

    MSC-->|POST| GLE

subgraph CSC[Code Summary Chain]
    direction LR
    CS3[Prompt\nCode Summary]
    CS3-->|Input| CS4[LLM\nOllama]
    CS4-->|Output| CS5[Output\nCode Summary]
end

subgraph MSC[MR Summary Chain]
    direction LR
    MRS3[Prompt\nMR Summary]-->|Input| MRS4[LLM\nOllama]
    MRS4-->|Output| MRS5[Output\nCode Summary]
end
```

### Code Summary & Review Chain

```mermaid
flowchart TD
    GLS[(GitLab API\nA commit of MR)]
    GL1[Changed files\n- filepath\n- language\n- diff]
    GLE[(GitLab API\nComment code summary & review into MR)]
    COMMENT(Union)

    GLS-->|GET| GL1

    GL1-->|Context| CSC
    GL1-->|Context| CRC

    CSC--> COMMENT
    CRC--> COMMENT

    COMMENT-->|POST| GLE

subgraph CSC[Code Summary Chain]
    direction TB
    CS3[Prompt\nCode Summary]
    CS3-->|Input| CS4[LLM\nOllama]
    CS4-->|Output| CS5[Output\nCode Summary]
end

subgraph CRC[Code Review Chain]
    direction TB
    CR3[Prompt\nCode Review]
    CR3-->|Input| CR4[LLM\nOllama]
    CR4-->|Output| CR5[Output\nCode Review]
end
```

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
pip install .
pip install flake8 black isort python-dotenv unidiff PyGithub python-gitlab openai ollama langchain langchain-core langchain-community faiss-cpu

# 整形
python -m flake8 coderev examples test
python -m black  coderev examples test
python -m isort  coderev examples test

# 終了
deactivate
Remove-Item –path ./.venv –recurse
```

## TODO

- GitLab CIに、対応させたい
- GitHub Actionsに、対応させたい
- 作成したやつをpydanticに対応させたい

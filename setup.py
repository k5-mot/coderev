from setuptools import setup


def get_requirements_from_file():
    with open("./requirements.txt") as f_in:
        requirements = f_in.read().splitlines()
    return requirements


setup(
    name="langchain-motex",
    version="0.0.1",
    author="k5-mot",
    author_email="34744243+k5-mot@users.noreply.github.com",
    description="LangChain Extensions for me",
    package_dir={"": "langchain_motex"},
    install_requires=get_requirements_from_file(),
)

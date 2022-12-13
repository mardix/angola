import setuptools


def long_description():
    with open('README.md', 'r') as file:
        return file.read()

VERSION = "0.2.0"
setuptools.setup(
    name='angola',
    version=VERSION,
    author='Mardix',
    author_email='mardix@blackdevhub.io',
    description='angola ',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/mardix/angola',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Topic :: Database',
    ],
    python_requires='>=3.8.0',
    install_requires = [
        "Jinja2 >= 3.0",
        "python-slugify",
        "arrow",
        "ulid-py",
        "python-arango"
    ],
    packages=['angola'],
    package_dir={'':'src'}
)

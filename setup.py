# -*- coding: utf-8 -*-

# Learn more: https://github.com/kennethreitz/setup.py

from setuptools import setup, find_packages


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='python-commons',
    version='0.1.0',
    description='',
    long_description=readme,
    author='Szilard Nemeth',
    author_email='szilard.nemeth88@gmail.com',
    url='',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'humanize',
        'gspread',
        'bs4',
        'requests',
        'gitpython',
        'tabulate',
        'docker',
        'sh'
    ]
)


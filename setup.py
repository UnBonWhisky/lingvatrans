#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os.path
import re

from setuptools import setup, find_packages


def get_file(*paths):
    path = os.path.join(*paths)
    try:
        with open(path, 'rb') as f:
            return f.read().decode('utf8')
    except IOError:
        pass


def get_version():
    init_py = get_file(os.path.dirname(__file__), 'lingvatrans', '__init__.py')
    pattern = r"{0}\W*=\W*'([^']+)'".format('__version__')
    version, = re.findall(pattern, init_py)
    return version


def install():
    setup(
        name='lingvatrans',
        version=get_version(),
        description='Lingvanex Translation API wrapper for Python',
        license='MIT',
        packages=find_packages(),
        author='UnBonWhisky',
        author_email='contact' '@' 'unbonwhisky.fr',
        install_requires=[
            'aiohttp>=3.8.0',
            'aiohttp-socks',
            'aiorwlock>=1.5.0',
        ],
        python_requires='>=3.7',
        classifiers=[
            'Development Status :: 4 - Beta',
            'Intended Audience :: Developers',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3',
        ],
        entry_points={
            'console_scripts': [
                'translate=lingvatrans.translate:main',
            ],
        }
    )


if __name__ == '__main__':
    install()

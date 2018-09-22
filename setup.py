from setuptools import setup

with open("README.md") as f:
    DESCRIPTION = f.read()

setup(
    name='Klippy',
    version='0.6.0',
    packages=['klippy'],
    url='https://github.com/KevinOConnor/klipper',
    author='Kevin O\'Connor',
    author_email='kevin@koconnor.net',
    description='Klippy - Klipper 3D printer firmware host software',
    long_description=DESCRIPTION,
    long_description_content_type='text/markdown',
    license='GPLv3',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    keywords='klipper 3d-printing reprap',
    install_requires=["cffi", "pyserial", "greenlet"],
    entry_points={
        'console_scripts': ['klippy=klippy.klippy:main'],
    }
)

from setuptools import setup

setup(
    name='gisquick-cli',
    version='0.1',
    description='',
    author='Marcel Dancak',
    author_email='dancakm@gmail.com',
    packages=['gisquickcli'],
    include_package_data=True,
    install_requires=[
        'click',
        'python-dotenv',
        'ruamel.yaml==0.16.5'
    ],
    url='https://github.com/gisquick-npo/gisquick-cli',
    download_url='',
    entry_points={
        "console_scripts": [
            "gisquick-cli = gisquickcli.cli:cli"
        ]
    }
)

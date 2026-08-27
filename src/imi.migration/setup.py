from setuptools import find_packages
from setuptools import setup

setup(
    name='imi.migration',
    version='0.1.0',
    description='Dexterity content models and migration tooling for the IMI Plone 4.3 to 5.2 migration',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['imi'],
    include_package_data=True,
    package_data={
        'imi.migration': [
            'configure.zcml',
            'browser/*.zcml',
            'browser/*.pt',
            'static/*.css',
            'static/*.js',
            'profiles/default/*.xml',
            'profiles/default/types/*.xml',
        ],
    },
    zip_safe=False,
    install_requires=[
        'setuptools',
        'Plone',
        'plone.api',
        'plone.app.dexterity',
        'collective.easyform==3.2.1',
        'openpyxl==3.0.10',
    ],
)

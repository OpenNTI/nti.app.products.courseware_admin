import codecs
from setuptools import setup, find_packages

entry_points = {
    'console_scripts': [
        "nti_course_exporter = nti.app.products.courseware_admin.scripts.nti_course_exporter:main",
        "nti_course_importer = nti.app.products.courseware_admin.scripts.nti_course_importer:main",
    ],
    "z3c.autoinclude.plugin": [
        'target = nti.app.products',
    ],
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.dottedname',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.products.courseware_admin',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="NTI Course Administration",
    long_description=(_read('README.rst') + '\n\n' + _read("CHANGES.rst")),
    license='Apache',
    keywords='pyramid courseware admin',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython'
    ],
    url="https://github.com/NextThought/nti.app.products.courseware_admin",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app', 'nti.app.products'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'nti.app.products.courseware',
        'nti.contenttypes.courses',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
    entry_points=entry_points
)

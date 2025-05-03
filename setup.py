from setuptools import setup, find_packages

setup(
    name='dcinside-post-cleaner',
    version='1.0.0',
    description='Automated DCInside post cleaner using Playwright',
    author='whatcanido4u',
    author_email='your@email.com',
    url='https://github.com/yourname/dcinside-post-cleaner',
    packages=find_packages(),
    py_modules=[
        'dc_cleaner', 'dc_auth', 'dc_cookie', 'dc_post', 'dc_logger', 'dc_delete_strategy'
    ],
    install_requires=[
        'playwright==1.40.0',
        'python-dotenv==1.0.0',
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'dcinside-post-cleaner=dc_cleaner:main',
        ],
    },
    include_package_data=True,
    license='MIT',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
)

import os
from setuptools import setup
from setuptools import find_packages

this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

resources_dir = "resources"

cbm_defaults_db = [
    os.path.join(resources_dir, "cbm_defaults_db", x)
    for x in ["cbm_defaults_2018.db", "cbm_defaults_2019.db"]]

win_x86_64_bin = [
    os.path.join(resources_dir, "libcbm_bin", "win_x86_64", x)
    for x in [
        "cbm.lib", "core.lib", "libcbm.dll", "libcbm.exp", "libcbm.lib",
        "volume_to_biomass.lib"]
]

ubuntu_18_04_x86_64_bin = [
    os.path.join(resources_dir, "libcbm_bin", "ubuntu_18_04_x86_64", x)
    for x in ["cbm.a", "core.a", "libcbm.so", "volume_to_biomass.a"]
]

setup(
    name="libcbm",
    version=0.1,
    description="Carbon budget model library based on CBM-CFS3",
    keywords=["cbm-cfs3"],
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Carbon Accounting Team - Canadian Forest Service',
    author_email='scott.morken@canada.ca',
    maintainer='Scott Morken',
    maintainer_email='scott.morken@canada.ca',
    license="MPL-2.0",
    url="",
    download_url="",
    packages=find_packages(),
    package_data={
        "libcbm": cbm_defaults_db + win_x86_64_bin + ubuntu_18_04_x86_64_bin
    },
    install_requires=["numpy", "pandas", "scipy"]
)
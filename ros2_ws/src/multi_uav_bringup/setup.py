from glob import glob
import os

from setuptools import find_packages, setup


package_name = "multi_uav_bringup"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            [f"resource/{package_name}"],
        ),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="multi-uav-perception",
    maintainer_email="maintainer@example.com",
    description="Gate 7 ROS nodes for the multi-UAV perception prototype.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "perception_source = multi_uav_bringup.perception_source:main",
            "assignment_relay = multi_uav_bringup.assignment_relay:main",
            "mission_relay = multi_uav_bringup.mission_relay:main",
        ],
    },
)

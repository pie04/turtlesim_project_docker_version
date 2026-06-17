# syntax=docker/dockerfile:1
FROM ros:jazzy

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-colcon-common-extensions \
    ros-jazzy-turtlesim \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /ros2_ws

COPY src ./src

RUN source /opt/ros/jazzy/setup.bash \
    && colcon build --symlink-install

COPY docker/ros_entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["ros2", "launch", "my_robot_bringup", "turtlesim_catch_them_all.launch.xml"]

# Turtlesim Catch Them All

ROS2 Jazzy workspace for a turtlesim game where turtles are spawned and the master turtle catches them.

## Run With Docker

This image is intended for Linux desktop use with X11 forwarding so the `turtlesim_node` GUI window can open.

Allow local Docker containers to access your X server:

```bash
xhost +local:docker
```

Pull the image from GitHub Container Registry:

```bash
docker pull ghcr.io/pie04/turtlesim-catch-them-all:latest
```

Run the launch file:

```bash
docker run --rm -it \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  ghcr.io/pie04/turtlesim-catch-them-all:latest
```

In a second terminal, run the controller:

```bash
docker run --rm -it \
  --net=host \
  -e ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-0} \
  ghcr.io/pie04/turtlesim-catch-them-all:latest \
  ros2 run turtlesim_catch_them_all Turtle_ctrl_node
```

Use `w`, `a`, `s`, `d` in the controller terminal to move the master turtle.

When finished, restore normal X server access:

```bash
xhost -local:docker
```

## Development With Docker Compose

Build the local development image:

```bash
docker compose build
```

Start the turtlesim launch file:

```bash
xhost +local:docker
docker compose up turtlesim
```

In a second terminal, start the controller:

```bash
docker compose --profile tools run --rm controller
```

## Local ROS2 Build

If you are developing without Docker:

```bash
source /opt/ros/jazzy/setup.bash
colcon build --allow-overriding my_robot_interfaces
source install/setup.bash
ros2 launch my_robot_bringup turtlesim_catch_them_all.launch.xml
```

Controller:

```bash
source install/setup.bash
ros2 run turtlesim_catch_them_all Turtle_ctrl_node
```

## Publishing

This repository includes a GitHub Actions workflow at `.github/workflows/docker-image.yml`.

On every push to `main`, GitHub Actions builds the Docker image and publishes it to:

```text
ghcr.io/pie04/turtlesim-catch-them-all:latest
```

Pull requests build the image but do not publish it.

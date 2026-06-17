#!/usr/bin/env python3
import sys
import select
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from turtlesim.msg import Pose
from my_robot_interfaces.msg import TurtleArray
from my_robot_interfaces.srv import CatchTurtle

try:
    import termios
    import tty
    TERMINAL_CONTROL_AVAILABLE = True
except ImportError:
    TERMINAL_CONTROL_AVAILABLE = False

def clamp(x: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(x, maximum))

class MasterController(Node): 
    def __init__(self):
        super().__init__('master_controller') 
        # subscriber to know the current pose of master turtle
        self.master_turtle_pose_subscriber = self.create_subscription(
        Pose,
        '/turtle1/pose',            
        self.master_turtle_pose_callback,
        10)

        # subscriber to know the name and coordinates of alive turtles
        self.alive_turtles_subscriber = self.create_subscription(
        TurtleArray,
        '/alive',            
        self.alive_turtles_callback,
        10)

        self.cmd_pub = self.create_publisher(Twist, 'turtle1/cmd_vel', 10)

        # declaring parameters
        self.declare_parameter('v_step', 5.2)          # how much W/S changes target linear speed
        self.declare_parameter('w_step', 2.5)          # how much A/D changes target angular speed
        self.declare_parameter('v_max', 2.0)           # max forward/back speed
        self.declare_parameter('w_max', 30.0)           # max turn rate
        self.declare_parameter('publish_hz', 50.0)     # control loop rate
        self.declare_parameter('catch_distance', 0.8)  # distance to consider turtle caught
        self.declare_parameter('p_gain', 3.8)          # P-controller gain for distance-based speed control
   
        # States
        self.master_pose = None
        self.alive_turtle_names = []  # array for names
        self.alive_turtle_x = []     # array for x coordinates
        self.alive_turtle_y = []     # array for y coordinates
        self.catch_requests_in_progress = set()

        # Service client to request turtle killing
        self.catch_turtle_client = self.create_client(CatchTurtle, '/catch_turtle')

        # Terminal settings for non-blocking key capture
        self.old_term_settings = None
        if TERMINAL_CONTROL_AVAILABLE:
            self.old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        else:
            self.get_logger().warn('Terminal control not available on this platform')

        # Timer for control loop
        publish_hz = float(self.get_parameter('publish_hz').value)
        self.timer = self.create_timer(1.0 / publish_hz, self.control_loop)

    # function to store the data of master turtle pose received from turtle_spawner node
    def master_turtle_pose_callback(self, msg: Pose):
        self.master_pose = msg
        # Check for turtles to catch whenever pose updates
        if self.alive_turtle_names:
            self.check_and_kill_turtle(msg.x, msg.y)

    def alive_turtles_callback(self, msg: TurtleArray):
        # Parse the TurtleArray message into separate arrays
        self.alive_turtle_names = list(msg.names)
        self.alive_turtle_x = list(msg.x)
        self.alive_turtle_y = list(msg.y)
        self.catch_requests_in_progress.intersection_update(self.alive_turtle_names)

    def catch_turtle_callback(self, future, turtle_name):
        try:
            response = future.result()
            if response.success:
                self.get_logger().info(f'Successfully caught turtle: {turtle_name}')
            else:
                self.get_logger().warn(f'Failed to catch turtle: {turtle_name}')
                self.catch_requests_in_progress.discard(turtle_name)
        except Exception as e:
            self.get_logger().error(f'Service call failed for turtle {turtle_name}: {e}')
            self.catch_requests_in_progress.discard(turtle_name)

    def cleanup(self):
        """Restore terminal settings on shutdown"""
        if self.old_term_settings and TERMINAL_CONTROL_AVAILABLE:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_term_settings)

    # function to measure the distance between master turtle and alive turtles
    def distance_between_turtles(self, x1, y1, x2, y2):
        return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

    # making a function to check the distance between master turtle and alive turtles
    def check_and_kill_turtle(self, master_x, master_y):
        for i in range(len(self.alive_turtle_names)):
            distance = self.distance_between_turtles(master_x, master_y, self.alive_turtle_x[i], self.alive_turtle_y[i])
            turtle_name = self.alive_turtle_names[i]
            if (
                distance < self.get_parameter('catch_distance').value
                and turtle_name not in self.catch_requests_in_progress
            ):
                self.get_logger().info(f'Catching turtle: {turtle_name}')
                self.catch_requests_in_progress.add(turtle_name)
                
                # Call the catch service to kill the turtle using existing client
                request = CatchTurtle.Request()
                request.turtle_name = turtle_name
                future = self.catch_turtle_client.call_async(request)
                future.add_done_callback(
                    lambda fut, name=turtle_name: self.catch_turtle_callback(fut, name)
                )
                
    def control_loop(self):
        # Reset velocities to zero each iteration (direct control)
        linear_vel = 0.0
        angular_vel = 0.0

        if TERMINAL_CONTROL_AVAILABLE:
            # Capture key press (non-blocking)
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                key = sys.stdin.read(1)
                if key == 'w':
                    linear_vel = self.get_parameter('v_step').value
                elif key == 's':
                    linear_vel = -self.get_parameter('v_step').value
                elif key == 'a':
                    angular_vel = self.get_parameter('w_step').value
                elif key == 'd':
                    angular_vel = -self.get_parameter('w_step').value
                elif key == '\x03':  # Ctrl-C to quit
                    self.get_logger().info('Shutting down...')
                    if self.old_term_settings:
                        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_term_settings)
                    rclpy.shutdown()
                    return
        else:
            # If terminal control not available, just publish zero velocity
            linear_vel = 0.0
            angular_vel = 0.0

        # Apply P-controller to linear velocity based on distance to nearest turtle
        if self.master_pose and self.alive_turtle_names:
            min_distance = float('inf')
            for i in range(len(self.alive_turtle_names)):
                distance = self.distance_between_turtles(
                    self.master_pose.x, self.master_pose.y,
                    self.alive_turtle_x[i], self.alive_turtle_y[i]
                )
                min_distance = min(min_distance, distance)
            
            if min_distance < float('inf'):
                # P-controller: closer turtles = slower movement
                p_gain = self.get_parameter('p_gain').value
                distance_factor = min_distance / (min_distance + p_gain)
                linear_vel = linear_vel * distance_factor

        # Clamp velocities
        v_max = self.get_parameter('v_max').value
        w_max = self.get_parameter('w_max').value
        linear_vel = clamp(linear_vel, -v_max, v_max)
        angular_vel = clamp(angular_vel, -w_max, w_max)

        # Publish command
        cmd_msg = Twist()
        cmd_msg.linear.x = linear_vel
        cmd_msg.angular.z = angular_vel
        self.cmd_pub.publish(cmd_msg)

def main(args=None):
    rclpy.init(args=args)
    node = MasterController()   
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cleanup()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()

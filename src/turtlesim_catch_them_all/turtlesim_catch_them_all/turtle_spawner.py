#!/usr/bin/env python3
import math
import rclpy
import random
from rclpy.node import Node
from turtlesim.srv import Spawn
from turtlesim.srv import Kill
from my_robot_interfaces.msg import TurtleArray
from my_robot_interfaces.srv import CatchTurtle

class turtle_spawner(Node): 
    def __init__(self):
        super().__init__('turtle_spawner')
        # client for spawn service
        self.spawn_client = self.create_client(Spawn, '/spawn')
        while not self.spawn_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Spawn service not available, waiting...')
        self.get_logger().info('Turtle Spawner Node has been started.')

        # client for kill service
        self.kill_client = self.create_client(Kill, '/kill')
        while not self.kill_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info(f'Kill service not available, waiting...')
        
        # server to handle requests to catch turtles
        self.catch_service = self.create_service(CatchTurtle, '/catch_turtle', self.kill_turtle)

        self.declare_parameter("spawn_timer_period", 5.0)
        self.declare_parameter("coordinate_period_for_alive_turtles", 1.0)
        self.spawn_timer_period_ = self.get_parameter("spawn_timer_period").value
        self.send_coordinates_period_ = self.get_parameter("coordinate_period_for_alive_turtles").value
        self.alive_ = self.create_publisher(TurtleArray, '/alive', 10) #Publishing name and coordinates of alive turtles
        self.alive_turtles = []  # List to keep track of alive turtles
        self.spawn_timer = self.create_timer(self.spawn_timer_period_, self.spawn_turtle)
        self.coordinate_timer = self.create_timer(self.send_coordinates_period_, self.publish_alive_turtles)
   
    # making a function to spawn a turtle at random location
    def spawn_turtle(self):
        request = Spawn.Request()
        request.x = random.uniform(1.0, 10.0)
        request.y = random.uniform(1.0, 10.0)
        request.theta = math.pi / random.uniform(1.0, 4.0) # Random orientation between 45 to 180 degrees for new turtle
    
        future = self.spawn_client.call_async(request) # Asynchronous call to spawn service
        future.add_done_callback(lambda fut: self.spawn_done_callback(fut, request.x, request.y)) # Callback after spawn is done

    # Callback function to handle spawn result    
    def spawn_done_callback(self, future, x, y):
        if future.result() is not None:
            self.alive_turtles.append((future.result().name, x, y))
            self.get_logger().info(f'Spawned turtle: {future.result().name} at ({x:.2f}, {y:.2f})')
        else:
            self.get_logger().error('Failed to spawn turtle')

    # Publish the list of alive turtles
    def publish_alive_turtles(self):
        msg = TurtleArray()
        for name, x, y in self.alive_turtles:
            msg.names.append(name)
            msg.x.append(x)
            msg.y.append(y)
        self.alive_.publish(msg)
        # self.get_logger().info(f'Published alive turtles: {len(msg.names)} turtles')

    # Service callback to handle turtle catching requests
    def kill_turtle(self, request, response):
        turtle_name = request.turtle_name
        self.get_logger().info(f'Received request to kill turtle: {turtle_name}')
        
        # Check if turtle exists in alive list
        turtle_exists = any(name == turtle_name for name, _, _ in self.alive_turtles)
        
        if turtle_exists:
            # Call turtlesim kill service
            kill_request = Kill.Request()
            kill_request.name = turtle_name
            future = self.kill_client.call_async(kill_request)
            future.add_done_callback(lambda fut, n=turtle_name: self.kill_done_callback(fut, n))
            
            response.success = True
            self.get_logger().info(f'Successfully initiated kill for turtle: {turtle_name}')
        else:
            response.success = False
            self.get_logger().warn(f'Turtle {turtle_name} not found in alive turtles list')
        
        return response



    # Callback function to handle kill result    
    def kill_done_callback(self, future, turtle_name):
        try:
            future.result()
            self.alive_turtles = [t for t in self.alive_turtles if t[0] != turtle_name]
            self.get_logger().info(f'Killed turtle: {turtle_name}')
        except Exception as e:
            self.get_logger().error(f'Failed to kill turtle: {turtle_name}, error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = turtle_spawner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()

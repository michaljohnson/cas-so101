cmake_minimum_required(VERSION 3.22)
project(so101_gazebo)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch models DESTINATION share/${PROJECT_NAME})

ament_package()

cmake_minimum_required(VERSION 3.8)
project(multi_uav_monitor)

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(multi_uav_interfaces REQUIRED)

add_executable(mission_monitor src/mission_monitor.cpp)
ament_target_dependencies(mission_monitor rclcpp multi_uav_interfaces)

install(TARGETS mission_monitor DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

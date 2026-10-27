# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.16)
project(battery_icon_palette LANGUAGES CXX)
find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(KF6IconThemes REQUIRED)
add_executable(battery_icon_palette main.cpp)
target_link_libraries(battery_icon_palette PRIVATE Qt6::Widgets KF6::IconThemes)

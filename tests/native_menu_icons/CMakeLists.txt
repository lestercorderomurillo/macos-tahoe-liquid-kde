# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.16)
project(menu_icon_lookup LANGUAGES CXX)
find_package(Qt6 REQUIRED COMPONENTS Widgets)
find_package(KF6IconThemes REQUIRED)
add_executable(menu_icon_lookup main.cpp)
target_link_libraries(menu_icon_lookup PRIVATE Qt6::Widgets KF6::IconThemes)

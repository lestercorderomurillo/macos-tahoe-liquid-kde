# SPDX-License-Identifier: GPL-3.0-or-later
cmake_minimum_required(VERSION 3.16)
project(mac-tahoe-clipd LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_AUTOMOC ON)
find_package(Qt6 REQUIRED COMPONENTS Core Gui DBus)
find_package(KF6GuiAddons REQUIRED)
add_executable(mac-tahoe-clipd main.cpp)
target_link_libraries(mac-tahoe-clipd PRIVATE Qt6::Core Qt6::Gui Qt6::DBus KF6::GuiAddons)

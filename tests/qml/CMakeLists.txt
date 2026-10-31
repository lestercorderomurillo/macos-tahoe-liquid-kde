cmake_minimum_required(VERSION 3.20)
project(launcher-popup-probe LANGUAGES CXX)
find_package(ECM QUIET NO_MODULE)
if(NOT ECM_FOUND)
    message(STATUS "LAUNCHER_POPUP_SDK_MISSING")
    return()
endif()
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
set(QT_MAJOR_VERSION 6)
include(KDEInstallDirs6)
find_package(Qt6 QUIET COMPONENTS Core Qml Quick WaylandClient)
find_program(WAYLAND_SCANNER_EXECUTABLE wayland-scanner)
find_package(KF6Config QUIET)
find_package(KF6CoreAddons QUIET)
find_package(Plasma QUIET)
find_package(PlasmaQuick QUIET)
if(NOT TARGET Plasma::PlasmaQuick OR NOT TARGET Qt6::Quick
   OR NOT TARGET Qt6::qtwaylandscanner OR NOT WAYLAND_SCANNER_EXECUTABLE)
    message(STATUS "LAUNCHER_POPUP_SDK_MISSING")
    return()
endif()
# Fedora's Qt Wayland target advertises metatypes that its SDK does not ship.
# The launcher only needs the scanner; importing these unused QML types must
# fail here too, even on hosts whose Qt Wayland package includes the JSON.
set_property(TARGET Qt6::WaylandClient APPEND PROPERTY INTERFACE_SOURCES
    "$<$<BOOL:$<TARGET_PROPERTY:QT_CONSUMES_METATYPES>>:${CMAKE_CURRENT_BINARY_DIR}/unused-wayland-metatypes.json>")
add_subdirectory("${LAUNCHER_NATIVE_SOURCE}/launcher" launcher)

add_executable(dockgeometryprobe dockgeometryprobe.cpp)
target_link_libraries(dockgeometryprobe PRIVATE Qt6::Quick)

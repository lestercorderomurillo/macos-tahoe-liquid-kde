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
# Match the production KDE build, which disables Qt keyword macros.
target_compile_definitions(mactahoelauncher PRIVATE QT_NO_KEYWORDS QT_NO_CAST_FROM_ASCII QT_NO_CAST_TO_ASCII)

add_executable(dockgeometryprobe dockgeometryprobe.cpp)
target_link_libraries(dockgeometryprobe PRIVATE Qt6::Quick)

find_package(Qt6 REQUIRED COMPONENTS Test)
qt_add_qml_module(launcherinteraction
    URI LauncherInteraction VERSION 1.0
    PLUGIN_TARGET launcherinteraction
    OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/LauncherInteraction"
    SOURCES launcherinteraction.h
)
target_link_libraries(launcherinteraction PRIVATE Qt6::Quick Qt6::Test)

add_executable(controlglassprobe controlglassprobe.cpp
    "${LAUNCHER_NATIVE_SOURCE}/launcher/controlglass.cpp"
    "${LAUNCHER_NATIVE_SOURCE}/launcher/controlglass.h")
set_target_properties(controlglassprobe PROPERTIES AUTOMOC ON)
target_include_directories(controlglassprobe PRIVATE "${LAUNCHER_NATIVE_SOURCE}/launcher")
target_link_libraries(controlglassprobe PRIVATE Qt6::Quick KF6::WindowSystem)

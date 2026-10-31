set(CMAKE_AUTOMOC ON)
set(CMAKE_CXX_STANDARD 20)
find_package(Qt6 REQUIRED COMPONENTS WaylandClient DBus)
find_package(Wayland REQUIRED COMPONENTS Client)
find_program(WAYLAND_SCANNER_EXECUTABLE wayland-scanner REQUIRED)
# Plasma's exported integration header includes protocol headers that its SDK
# does not install. Generate declarations only; libplasma owns the connection.
get_target_property(qt_wayland_scanner Qt6::qtwaylandscanner LOCATION)
set(shell_protocol "${CMAKE_CURRENT_SOURCE_DIR}/wayland/plasma-shell.xml")
execute_process(COMMAND "${WAYLAND_SCANNER_EXECUTABLE}" client-header "${shell_protocol}"
    "${CMAKE_CURRENT_BINARY_DIR}/wayland-plasma-shell-client-protocol.h"
    COMMAND_ERROR_IS_FATAL ANY)
execute_process(COMMAND "${qt_wayland_scanner}" client-header "${shell_protocol}"
    OUTPUT_FILE "${CMAKE_CURRENT_BINARY_DIR}/qwayland-plasma-shell.h"
    COMMAND_ERROR_IS_FATAL ANY)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${shell_protocol}")
set(launcher_module_dir "${CMAKE_BINARY_DIR}/bin/org/kde/mac/tahoe/launcher")
qt_add_qml_module(mactahoelauncher
    URI org.kde.mac.tahoe.launcher
    VERSION 1.0
    PLUGIN_TARGET mactahoelauncher
    OUTPUT_DIRECTORY "${launcher_module_dir}"
    QML_FILES DockIcon.qml
    SOURCES launchersearchpopup.cpp launchersearchpopup.h iconthemewatcher.h
)
# Only the scanner is needed from Qt Wayland. PlasmaQuick owns the client;
# linking it here also pulls unused Wayland metatypes into QML registration.
target_link_libraries(mactahoelauncher PRIVATE Qt6::Quick Qt6::DBus Plasma::Plasma Plasma::PlasmaQuick KF6::WindowSystem Wayland::Client)
# The installer copies this module directly from the build tree.
set_target_properties(mactahoelauncher PROPERTIES PREFIX "lib" BUILD_WITH_INSTALL_RPATH TRUE)
target_include_directories(mactahoelauncher PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}")
install(TARGETS mactahoelauncher LIBRARY DESTINATION "${KDE_INSTALL_QMLDIR}/org/kde/mac/tahoe/launcher")
install(FILES "${launcher_module_dir}/qmldir" "${launcher_module_dir}/mactahoelauncher.qmltypes"
        DESTINATION "${KDE_INSTALL_QMLDIR}/org/kde/mac/tahoe/launcher")

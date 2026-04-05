cmake_minimum_required(VERSION 3.20)
project(mac-tahoe-menu VERSION 1.0)

set(QT_MIN_VERSION "6.6.0")
set(KF_MIN_VERSION "6.0.0")

find_package(ECM ${KF_MIN_VERSION} REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs6)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(ECMQmlModule)
include(FeatureSummary)

find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED COMPONENTS
    Core Widgets Quick
)
find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    CoreAddons Config
)
find_package(Plasma REQUIRED)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

plasma_add_applet(org.kde.mac.tahoe.liquid.menu
    QML_SOURCES
        qml/config.qml
        qml/configGeneral.qml
        qml/main.qml
        qml/AboutWindow.qml
    CPP_SOURCES
        menuapplet.cpp
    RESOURCES
        main.xml
    QML_ARGS DEPENDENCIES QtCore org.kde.plasma.core
)

target_link_libraries(org.kde.mac.tahoe.liquid.menu PRIVATE
    Qt::Core
    Qt::Widgets
    Qt::Quick
    Plasma::Plasma
)

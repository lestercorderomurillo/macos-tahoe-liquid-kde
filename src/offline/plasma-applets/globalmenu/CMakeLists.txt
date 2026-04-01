cmake_minimum_required(VERSION 3.20)
project(mac-tahoe-globalmenu VERSION 1.0)

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
    Core Widgets Quick DBus
)
find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    WindowSystem I18n CoreAddons
)
find_package(Plasma REQUIRED)
find_package(PlasmaActivities)
find_package(LibTaskManager REQUIRED)
find_package(dbusmenu-qt6 REQUIRED)

add_definitions(-DTRANSLATION_DOMAIN="plasma_applet_org.kde.mac.tahoe.globalmenu")

plasma_add_applet(org.kde.mac.tahoe.globalmenu
    QML_SOURCES
        qml/config.qml
        qml/configGeneral.qml
        qml/main.qml
        qml/MenuDelegate.qml
    CPP_SOURCES
        appmenuapplet.cpp
        appmenumodel.cpp
    RESOURCES
        main.xml
    QML_ARGS DEPENDENCIES QtCore org.kde.plasma.core
)

target_link_libraries(org.kde.mac.tahoe.globalmenu PRIVATE
    Qt::Core
    Qt::Widgets
    Qt::Quick
    Qt::DBus
    Plasma::Plasma
    KF6::WindowSystem
    KF6::I18n
    PW::LibTaskManager
    dbusmenuqt6
)

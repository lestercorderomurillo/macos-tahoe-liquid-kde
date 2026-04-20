cmake_minimum_required(VERSION 3.20)
project(mac-tahoe-taskmanager VERSION 1.0)

set(QT_MIN_VERSION "6.6.0")
set(KF_MIN_VERSION "6.0.0")

find_package(ECM ${KF_MIN_VERSION} REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})

include(KDEInstallDirs6)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)
include(ECMQtDeclareLoggingCategory)
include(ECMQmlModule)
include(FeatureSummary)

find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED COMPONENTS
    Core
    DBus
    Qml
    Quick
)
find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    Config
    CoreAddons
    I18n
    KIO
    Notifications
    Service
    WindowSystem
)
find_package(Plasma REQUIRED)
find_package(PlasmaActivities REQUIRED)
find_package(PlasmaActivitiesStats REQUIRED)
find_package(KSysGuard REQUIRED)
find_package(LibNotificationManager REQUIRED)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
add_definitions(-DTRANSLATION_DOMAIN="plasma_applet_org.kde.mac.tahoe.liquid.taskmanager")

file(GLOB_RECURSE TASKMANAGER_QML CONFIGURE_DEPENDS
    RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}"
    contents/config/*.qml
    contents/ui/*.qml
    contents/ui/*.js
)

set_source_files_properties(contents/ui/LayoutMetrics.js contents/ui/TaskTools.js PROPERTIES QT_QML_SKIP_QMLDIR_ENTRY TRUE)

set(QT_QML_NO_CACHEGEN TRUE)

plasma_add_applet(org.kde.mac.tahoe.liquid.taskmanager
    QML_SOURCES
        ${TASKMANAGER_QML}
    CPP_SOURCES
        backend.cpp
        smartlauncherbackend.cpp
        smartlauncheritem.cpp
    RESOURCES
        contents/config/main.xml
    GENERATE_APPLET_CLASS
    QML_ARGS DEPENDENCIES
        QtCore
        org.kde.taskmanager
        org.kde.kirigami
        org.kde.ksvg
        org.kde.plasma.components
        org.kde.plasma.core
        org.kde.plasma.extras
        org.kde.plasma.plasmoid
        org.kde.plasma.private.mpris
        org.kde.plasma.workspace.dbus
        org.kde.plasma.workspace.trianglemousefilter
)

kconfig_add_kcfg_files(org.kde.mac.tahoe.liquid.taskmanager
    kactivitymanagerd_plugins_settings.kcfgc
)

ecm_qt_declare_logging_category(org.kde.mac.tahoe.liquid.taskmanager
    HEADER log_settings.h
    IDENTIFIER TASKMANAGER_DEBUG
    CATEGORY_NAME org.kde.mac.tahoe.liquid.taskmanager
)

target_link_libraries(org.kde.mac.tahoe.liquid.taskmanager PRIVATE
    KF6::ConfigGui
    KF6::ConfigCore
    KF6::CoreAddons
    KF6::I18n
    KF6::KIOCore
    KF6::KIOFileWidgets
    KF6::KIOGui
    KF6::Notifications
    KF6::Service
    KF6::WindowSystem
    KSysGuard::ProcessCore
    Plasma::Activities
    Plasma::ActivitiesStats
    Plasma::Plasma
    PW::LibNotificationManager
    Qt::Core
    Qt::DBus
    Qt::Qml
    Qt::Quick
)

cmake_minimum_required(VERSION 3.16.0)

project(kwin_acrylic_glass)
set(PROJECT_VERSION "1.0.0")
set(PROJECT_VERSION_MAJOR 0)

set(KF_MIN_VERSION "5.240.0")
set(QT_MIN_VERSION "6.6.0")
set(QT_MAJOR_VERSION 6)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CPACK_PACKAGE_NAME "kwin-acrylic-glass")
set(CPACK_PACKAGING_INSTALL_PREFIX "/usr")
set(CPACK_PACKAGE_FILE_NAME "kwin-acrylic-glass")
set(CPACK_PACKAGE_VERSION "${PROJECT_VERSION}")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Acrylic Glass — blur and rounded corners for KDE Plasma 6 (MacTahoe Liquid KDE)")
include(CPack)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Choose Release or Debug" FORCE)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "${CMAKE_CXX_FLAGS_RELEASE} -DQT_NO_DEBUG_OUTPUT")

find_package(ECM REQUIRED NO_MODULE)
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} ${ECM_MODULE_PATH} ${ECM_KDE_MODULE_DIR})

option(GLASS_WAYLAND "Whether to build Acrylic Glass for Wayland if present." ON)
option(GLASS_X11 "Whether to build Acrylic Glass for X11 if present." OFF)

include(FeatureSummary)
include(KDEInstallDirs)
include(KDECMakeSettings)
include(KDECompilerSettings NO_POLICY_SCOPE)

find_package(Qt6 ${QT_MIN_VERSION} CONFIG REQUIRED COMPONENTS
    Gui
    Core
    DBus
    UiTools
    Widgets
    OpenGL
    Network
    Xml
)

include_directories(${Qt6Widgets_INCLUDE_DIRS} ${Qt6Network_INCLUDE_DIRS} ${Qt6OpenGL_INCLUDE_DIRS} ${Qt6Xml_INCLUDE_DIRS})
add_definitions(${Qt6Widgets_DEFINITIONS})

find_package(KF6 ${KF_MIN_VERSION} REQUIRED COMPONENTS
    Config
    ConfigWidgets
    CoreAddons
    Crash
    GlobalAccel
    I18n
    KIO
    Service
    #Init
    Notifications
    Service
    WidgetsAddons
    WindowSystem
    GuiAddons
    KCMUtils
)

find_package(epoxy REQUIRED)

find_package(X11 REQUIRED)
find_package(XCB REQUIRED COMPONENTS XCB)

if(GLASS_WAYLAND)
    find_package(KWin COMPONENTS
        kwineffects
    )
    if (${KWin_FOUND})
        find_package(KWinDBusInterface CONFIG REQUIRED)
    else()
        set(GLASS_WAYLAND OFF)
    endif()
endif()
if(GLASS_X11)
    find_package(KWinX11 COMPONENTS
        kwineffects
    )
    if (${KWinX11_FOUND})
        find_package(KWinX11DBusInterface CONFIG REQUIRED)
        set(KWin_VERSION ${KWinX11_VERSION})
    else()
        set(GLASS_X11 OFF)
    endif()
endif()

if(NOT GLASS_WAYLAND AND NOT GLASS_X11)
    message(FATAL_ERROR
        "Acrylic Glass requires KWin development files for Wayland or X11. "
        "Install the missing KWin dependencies and re-run."
    )
endif()

if(${KWin_VERSION} VERSION_LESS 6.4)
    message(FATAL_ERROR "Acrylic Glass requires KDE Plasma 6.4+ (found ${KWin_VERSION}).")
endif()

# KWin's private effect ABI changed at 6.7 (the proprietary blur
# protocol was replaced by ext_background_effect_v1, and the prePaint*
# methods dropped their presentTime parameter). The effect sources
# branch on a GLASS_KWIN_67 compile definition — same flag name and
# >= 6.7 threshold as the upstream kwin-effects-glass fork, kept
# identical so the two trees stay easy to cross-reference. The Wayland
# and X11 KWin packages can in principle sit at different versions, so
# the flag is evaluated per backend below.
set(GLASS_KWIN_67_WAYLAND OFF)
set(GLASS_KWIN_67_X11 OFF)
# Nest the version test so the *_VERSION variable is only dereferenced
# when its backend is actually enabled (and thus set). CMake's `AND`
# does not short-circuit at parse time, so a single combined condition
# would expand an unset KWinX11_VERSION to an empty left operand and
# error out on a Wayland-only build.
if(GLASS_WAYLAND)
    if(${KWin_VERSION} VERSION_GREATER_EQUAL 6.7)
        set(GLASS_KWIN_67_WAYLAND ON)
    endif()
endif()
if(GLASS_X11)
    if(${KWinX11_VERSION} VERSION_GREATER_EQUAL 6.7)
        set(GLASS_KWIN_67_X11 ON)
    endif()
endif()
message(STATUS "Acrylic Glass: KWin ${KWin_VERSION} (6.7 ABI: Wayland=${GLASS_KWIN_67_WAYLAND} X11=${GLASS_KWIN_67_X11})")

find_package(KDecoration3 REQUIRED)

add_subdirectory(src)

feature_summary(WHAT ALL FATAL_ON_MISSING_REQUIRED_PACKAGES)

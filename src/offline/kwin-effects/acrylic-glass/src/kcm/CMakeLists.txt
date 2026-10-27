set(kwin_liquidglass_config_SRCS
    config.cpp
    config.h
    presetcombobox.h
)

set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/../presets.json")
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../presets.json" MATERIAL_PRESETS_JSON)
configure_file(presets.h.in presets.h @ONLY)

ki18n_wrap_ui(kwin_liquidglass_config_SRCS config.ui)
kconfig_add_kcfg_files(kwin_liquidglass_config_SRCS ../glassconfig.kcfgc)

# This will only work as long as KWin and KWin X11 have the same interface
qt_add_dbus_interface(kwin_liquidglass_config_SRCS ${KWIN_EFFECTS_INTERFACE} kwineffects_interface)

add_library(kwin_liquidglass_config MODULE ${kwin_liquidglass_config_SRCS})
target_compile_definitions(kwin_liquidglass_config PRIVATE TRANSLATION_DOMAIN="kwin_effect_liquidglass")
install(DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/../../locale/" DESTINATION "${KDE_INSTALL_LOCALEDIR}")

target_link_libraries(kwin_liquidglass_config
    KF6::KCMUtils
    KF6::CoreAddons
    KF6::I18n
    KF6::WidgetsAddons
    Qt6::DBus
)

if(GLASS_WAYLAND)
    install(TARGETS kwin_liquidglass_config DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin/effects/configs)
endif()
if(GLASS_X11)
    install(TARGETS kwin_liquidglass_config DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin-x11/effects/configs)
endif()

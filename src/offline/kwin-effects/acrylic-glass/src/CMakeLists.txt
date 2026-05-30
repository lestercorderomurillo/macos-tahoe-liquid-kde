if(GLASS_WAYLAND OR GLASS_X11)
    add_subdirectory(kcm)
endif()

set(LIQUIDGLASS_SHADER_INCLUDES
    sdf.glsl
    blur.glsl
    distort.glsl
    highlight.glsl
)

function(preprocess_shader_includes input output)
    file(READ "${input}" SHADER_SOURCE)
    foreach(include_file IN LISTS LIQUIDGLASS_SHADER_INCLUDES)
        file(READ "shaders/${include_file}" INCLUDE_SOURCE)
        string(REPLACE "#include \"${include_file}\"" "${INCLUDE_SOURCE}" SHADER_SOURCE "${SHADER_SOURCE}")
    endforeach()
    file(WRITE "${output}" "${SHADER_SOURCE}")
endfunction()

preprocess_shader_includes(shaders/glass.glsl shaders/glass.frag)
preprocess_shader_includes(shaders/glass_core.glsl shaders/glass_core.frag)

set(liquidglass_SOURCES
    effect.cpp
    liquidglass.qrc
    main.cpp
)

kconfig_add_kcfg_files(liquidglass_SOURCES
    glassconfig.kcfgc
)

if(GLASS_WAYLAND)
    add_library(liquidglass MODULE ${liquidglass_SOURCES})
    target_link_libraries(liquidglass PRIVATE
        KDecoration3::KDecoration
        KF6::ConfigGui
        KWin::kwin
    )
    install(TARGETS liquidglass DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin/effects/plugins)
endif()
if(GLASS_X11)
    add_library(liquidglass_x11 MODULE ${liquidglass_SOURCES})
    target_link_libraries(liquidglass_x11 PRIVATE
        KDecoration3::KDecoration
        KF6::ConfigGui
        KWinX11::kwin
        XCB::XCB
    )
    target_compile_definitions(liquidglass_x11 PRIVATE GLASS_X11)
    install(TARGETS liquidglass_x11 DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin-x11/effects/plugins)
endif()

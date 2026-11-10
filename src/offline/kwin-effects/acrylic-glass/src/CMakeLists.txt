if(GLASS_WAYLAND OR GLASS_X11)
    add_subdirectory(kcm)
endif()

set(LIQUIDGLASS_SHADER_INCLUDES
    sdf.glsl
    blur.glsl
    distort.glsl
    highlight.glsl
)

# Everything liquidglass.qrc references except the four preprocessed
# .frag outputs generated below.
set(LIQUIDGLASS_SHADER_STATIC
    blur.glsl
    distort.glsl
    downsample.frag
    downsample_core.frag
    glass.vert
    glass_core.vert
    highlight.glsl
    sdf.glsl
    upsample.frag
    upsample_core.frag
    vertex.vert
    vertex_core.vert
)

# Preprocess and stage into the build tree — never into the source
# checkout, which must stay clean. rcc resolves qrc entries relative to the qrc
# file, so the staged qrc sits next to the staged shaders.
function(preprocess_shader_includes input output)
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/${input}" SHADER_SOURCE)
    foreach(include_file IN LISTS LIQUIDGLASS_SHADER_INCLUDES)
        file(READ "${CMAKE_CURRENT_SOURCE_DIR}/shaders/${include_file}" INCLUDE_SOURCE)
        string(REPLACE "#include \"${include_file}\"" "${INCLUDE_SOURCE}" SHADER_SOURCE "${SHADER_SOURCE}")
    endforeach()
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/${output}" "${SHADER_SOURCE}")
endfunction()

preprocess_shader_includes(shaders/glass.glsl shaders/glass.frag)
preprocess_shader_includes(shaders/glass_core.glsl shaders/glass_core.frag)
preprocess_shader_includes(shaders/noise.frag shaders/noise.frag)
preprocess_shader_includes(shaders/noise_core.frag shaders/noise_core.frag)

foreach(shader_file IN LISTS LIQUIDGLASS_SHADER_STATIC)
    configure_file("shaders/${shader_file}"
                   "${CMAKE_CURRENT_BINARY_DIR}/shaders/${shader_file}" COPYONLY)
endforeach()
# Resident older plugins keep their Qt resources registered too. Give each
# source build its own resource namespace, not just a new library filename.
file(GLOB_RECURSE identity_inputs CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/*.cpp" "${CMAKE_CURRENT_SOURCE_DIR}/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/shaders/*" "${CMAKE_CURRENT_SOURCE_DIR}/metadata.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/*.kcfg" "${CMAKE_CURRENT_SOURCE_DIR}/*.kcfgc")
list(SORT identity_inputs)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${identity_inputs})
set(identity_contents "")
foreach(input IN LISTS identity_inputs)
    file(SHA256 "${input}" input_hash)
    string(APPEND identity_contents "${input_hash}")
endforeach()
string(SHA256 build_identity "${identity_contents}")
set(resource_prefix "/effects/liquidglass/${build_identity}/")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/build_identity.h"
    "#pragma once\n#define MTTKDE_GLASS_BUILD_ID \"${build_identity}\"\n#define MTTKDE_GLASS_RESOURCE_PREFIX \":${resource_prefix}\"\n")
file(READ liquidglass.qrc resource_source)
string(REPLACE "/effects/liquidglass/" "${resource_prefix}" resource_source "${resource_source}")
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/liquidglass.qrc" "${resource_source}")

set(liquidglass_SOURCES
    effect.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/liquidglass.qrc
    main.cpp
)

kconfig_add_kcfg_files(liquidglass_SOURCES
    glassconfig.kcfgc
)

if(GLASS_WAYLAND)
    add_library(liquidglass MODULE ${liquidglass_SOURCES})
    target_include_directories(liquidglass PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
    target_link_libraries(liquidglass PRIVATE
        KDecoration3::KDecoration
        KF6::ConfigGui
        KWin::kwin
        XCB::XCB
        XCB::RENDER
    )
    # GLASS_KWIN_67 drives the 6.6-vs-6.7 ABI gating in kwin_version_compat.h.
    if(GLASS_KWIN_67_WAYLAND)
        target_compile_definitions(liquidglass PRIVATE GLASS_KWIN_67)
    endif()
    if(GLASS_KWIN_68_WAYLAND)
        target_compile_definitions(liquidglass PRIVATE GLASS_KWIN_68)
    endif()
    target_compile_definitions(liquidglass PRIVATE GLASS_WAYLAND)
    install(TARGETS liquidglass DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin/effects/plugins)
endif()
if(GLASS_X11)
    add_library(liquidglass_x11 MODULE ${liquidglass_SOURCES})
    target_include_directories(liquidglass_x11 PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
    target_link_libraries(liquidglass_x11 PRIVATE
        KDecoration3::KDecoration
        KF6::ConfigGui
        KWinX11::kwin
        XCB::XCB
        XCB::RENDER
    )
    target_compile_definitions(liquidglass_x11 PRIVATE GLASS_X11 KWIN_BUILD_X11)
    # KWin's X11 SDK retains the legacy effect ABI on Plasma 6.7, unlike
    # the Wayland SDK. Keep its ABI gates independent from the Wayland target.
    if(GLASS_KWIN_68_X11)
        target_compile_definitions(liquidglass_x11 PRIVATE GLASS_KWIN_68)
    endif()
    install(TARGETS liquidglass_x11 DESTINATION ${KDE_INSTALL_PLUGINDIR}/kwin-x11/effects/plugins)
endif()

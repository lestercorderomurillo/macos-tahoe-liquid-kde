/*
    SPDX-FileCopyrightText: 2026 Lester Cordero Murillo <lestercorderomurillo@gmail.com>

    SPDX-License-Identifier: GPL-2.0-or-later
*/

#pragma once

/**
 * KWin version gating for the Acrylic Glass effect.
 *
 * KWin's private effect ABI is not stable across feature releases, so
 * the parts of this effect that touch it have to be compiled against the
 * exact KWin the user is building on. Plasma 6.7 made two source-breaking
 * changes:
 *
 *   1. KDE retired its proprietary blur protocol (`org_kde_kwin_blur`)
 *      in favour of the freedesktop standard `ext_background_effect_v1`.
 *      The old per-surface blur / contrast Wayland headers
 *      (`wayland/blur.h`, `wayland/contrast.h`) and their
 *      `*ManagerInterface` classes are gone. 6.7 announces blur via
 *      `waylandServer()->backgroundEffectManager()->addBlurCapability()`
 *      and exposes the region as `SurfaceInterface::blurRegion()`
 *      (a floating-point RegionF). The contrast/saturation protocol was
 *      dropped entirely. (Apps that still speak only the old protocol —
 *      some terminals/editors as of mid-2026 — lose blur until they
 *      adopt the standard one; that is an app-side gap, not ours.)
 *
 *   2. The trailing `std::chrono::milliseconds presentTime` parameter
 *      was dropped from `prePaintScreen` / `prePaintWindow`. Keeping it
 *      makes the `override` mismatch the base class — the "marked
 *      override, but does not override" error.
 *
 * GLASS_KWIN_67 is defined by CMake (see CMakeLists.txt) when
 * find_package(KWin) reports >= 6.7 — the same flag and threshold the
 * upstream kwin-effects-glass fork uses, kept identical on purpose so
 * the two trees stay easy to cross-reference. When the macro is absent
 * we are on 6.6 (the supported floor): the old org_kde_kwin_blur
 * protocol with the presentTime paint parameter.
 */

#ifdef GLASS_KWIN_67
#define ACRYLIC_GLASS_KWIN_6_7 1
#else
#define ACRYLIC_GLASS_KWIN_6_7 0
#endif

#if ACRYLIC_GLASS_KWIN_6_7
/// Paint methods take no trailing presentTime on 6.7+ — expands to nothing.
#define ACRYLIC_GLASS_PRESENT_TIME_PARAM
/// Forwarding call to effects-> drops the presentTime argument on 6.7+.
#define ACRYLIC_GLASS_PRESENT_TIME_ARG
#else
/// 6.6 and earlier: the methods carry an explicit presentTime parameter.
#define ACRYLIC_GLASS_PRESENT_TIME_PARAM , std::chrono::milliseconds presentTime
#define ACRYLIC_GLASS_PRESENT_TIME_ARG , presentTime
#endif

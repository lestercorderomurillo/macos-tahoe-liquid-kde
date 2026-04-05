#pragma once

#include <QImage>
#include <QStringList>

namespace KWin
{

enum class WindowClassMatchingMode
{
    Blacklist,
    Whitelist
};


struct GeneralSettings
{
    int blurStrength;
    int noiseStrength;
    float brightness;
    float saturation;
    float contrast;
    QString tintColor;
    QString glowColor;
    bool edgeLighting;
    bool excludeDocks;
};

struct ForceBlurSettings
{
    QStringList windowClasses;
    WindowClassMatchingMode windowClassMatchingMode;
    bool blurDecorations;
    bool blurMenus;
    bool blurDocks;
};

struct RoundedCornersSettings
{
    float windowRadius;
    float dockRadius;
    float popupRadius;
    bool roundMaximized;
};

struct RefractionSettings
{
    float edgeSizePixels;
    float refractionStrength;
    float refractionNormalPow;
    float refractionRGBFringing;
};

class BlurSettings
{
public:
    GeneralSettings general{};
    ForceBlurSettings forceBlur{};
    RoundedCornersSettings roundedCorners{};
    RefractionSettings refraction{};

    void read();
};

}

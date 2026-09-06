"""Small, dependency-free localization layer for the installer surfaces.

Plasma widgets use KDE's native ``i18n()`` catalog machinery.  The Python
installer cannot rely on gettext catalogs being installed yet, so the GUI and
the curses wizard share this module instead.  English source strings are the
stable message ids and remain the fallback for incomplete translations.
"""

from __future__ import annotations

import json
import locale
import os
import tempfile
from pathlib import Path


LANGUAGES = (
    {"code": "auto", "label": "System default"},
    {"code": "en", "label": "English"},
    {"code": "es", "label": "Español"},
    {"code": "zh_CN", "label": "简体中文"},
)
LANGUAGE_CODES = tuple(item["code"] for item in LANGUAGES)


_ES = {
    "System default": "Predeterminado del sistema",
    "Language": "Idioma",
    "MacTahoe Liquid KDE Installer": "Instalador de MacTahoe Liquid KDE",
    "Update available:": "Actualización disponible:",
    "Install": "Instalar",
    "Uninstall": "Desinstalar",
    "Features": "Funciones",
    "Features…": "Funciones…",
    "Choose what gets installed": "Elige qué se instalará",
    "Could not load features.": "No se pudieron cargar las funciones.",
    "Installed": "Instalado",
    "Uninstalled": "Desinstalado",
    "Install Failed": "Error de instalación",
    "Install failed": "Falló la instalación",
    "Uninstall failed": "Falló la desinstalación",
    "Below is the tail of the install log. Retry runs the same action again; Close dismisses.":
        "A continuación se muestra el final del registro. Reintentar ejecuta la misma acción; Cerrar descarta esta ventana.",
    "Close": "Cerrar",
    "Retry": "Reintentar",
    "Starting…": "Iniciando…",
    "Cancelling… waiting for the current operation to stop safely; dismiss any authentication prompt":
        "Cancelando… esperando que la operación actual se detenga de forma segura; cierra cualquier solicitud de autenticación",
    "Please select the components you want to install": "Selecciona los componentes que deseas instalar",
    "Please select the components you want to remove": "Selecciona los componentes que deseas eliminar",
    "Move": "Mover", "Toggle": "Alternar", "Adjust": "Ajustar",
    "Continue": "Continuar", "Quit": "Salir", "Select": "Seleccionar",
    "Back": "Atrás", "Confirm": "Confirmar",
    "Theme Mode": "Modo del tema", "Auto": "Automático",
    "Light": "Claro", "Dark": "Oscuro",
    "In development — install at your own risk.": "En desarrollo: instala bajo tu propia responsabilidad.",
    "Do not install on production / work systems.": "No lo instales en sistemas de producción o trabajo.",
    "This will reset your desktop to Breeze defaults.": "Esto restablecerá el escritorio a los valores de Breeze.",
    "Only the selected components are removed.": "Solo se eliminarán los componentes seleccionados.",
    "Installing {enabled} of {total} components": "Instalando {enabled} de {total} componentes",
    "Removing {enabled} of {total} components": "Eliminando {enabled} de {total} componentes",
    "Skipped: {items}": "Omitidos: {items}",
    "Theme Mode: {mode}": "Modo del tema: {mode}",
    "OLED Care: every {interval} min, max {shift} px": "Cuidado OLED: cada {interval} min, máx. {shift} px",
    "Wallpapers: {choice}": "Fondos de pantalla: {choice}",
    "Reset to theme defaults": "Restablecer los valores del tema",
    "Keep smart light/dark choices": "Conservar las opciones inteligentes claro/oscuro",
    "Your selection is saved to features.json": "Tu selección se guarda en features.json",
    "Shift Interval": "Intervalo de desplazamiento", "Max Shift": "Desplazamiento máximo",
    "needs OLED Care": "requiere Cuidado OLED",
    "replace custom light/dark choices once": "reemplazar una vez las opciones claro/oscuro",
    "Reset Saved Wallpapers": "Restablecer fondos guardados",
    "VERIFICATION": "VERIFICACIÓN", "BUILDING": "COMPILACIÓN", "INSTALLING": "INSTALACIÓN",
    "RESTORING": "RESTAURACIÓN", "REMOVING": "ELIMINACIÓN",
    "Done — press any key to exit.": "Listo: pulsa cualquier tecla para salir.",
    "Finished with errors — full log: {path}": "Finalizó con errores; registro completo: {path}",
    "Working…  press Ctrl-C to abort": "Trabajando…  pulsa Ctrl-C para cancelar",
}

_ZH_CN = {
    "System default": "跟随系统",
    "Language": "语言",
    "MacTahoe Liquid KDE Installer": "MacTahoe Liquid KDE 安装程序",
    "Update available:": "有可用更新：",
    "Install": "安装",
    "Uninstall": "卸载",
    "Features": "功能",
    "Features…": "功能…",
    "Choose what gets installed": "选择要安装的内容",
    "Could not load features.": "无法加载功能列表。",
    "Installed": "已安装",
    "Uninstalled": "已卸载",
    "Install Failed": "安装失败",
    "Install failed": "安装失败",
    "Uninstall failed": "卸载失败",
    "Below is the tail of the install log. Retry runs the same action again; Close dismisses.":
        "下方是安装日志的末尾。“重试”将再次执行同一操作；“关闭”将关闭此窗口。",
    "Close": "关闭",
    "Retry": "重试",
    "Starting…": "正在启动…",
    "Cancelling… waiting for the current operation to stop safely; dismiss any authentication prompt":
        "正在取消…正在等待当前操作安全停止；请关闭任何身份验证提示",
    "Please select the components you want to install": "请选择要安装的组件",
    "Please select the components you want to remove": "请选择要删除的组件",
    "Move": "移动", "Toggle": "切换", "Adjust": "调整",
    "Continue": "继续", "Quit": "退出", "Select": "选择",
    "Back": "返回", "Confirm": "确认",
    "Theme Mode": "主题模式", "Auto": "自动",
    "Light": "浅色", "Dark": "深色",
    "In development — install at your own risk.": "此项目仍在开发中——请自行承担安装风险。",
    "Do not install on production / work systems.": "请勿安装在生产或工作系统上。",
    "This will reset your desktop to Breeze defaults.": "这将把桌面重置为 Breeze 默认设置。",
    "Only the selected components are removed.": "仅删除已选组件。",
    "Installing {enabled} of {total} components": "正在安装 {enabled}/{total} 个组件",
    "Removing {enabled} of {total} components": "正在删除 {enabled}/{total} 个组件",
    "Skipped: {items}": "已跳过：{items}",
    "Theme Mode: {mode}": "主题模式：{mode}",
    "OLED Care: every {interval} min, max {shift} px": "OLED 保护：每 {interval} 分钟，最大 {shift} 像素",
    "Wallpapers: {choice}": "壁纸：{choice}",
    "Reset to theme defaults": "重置为主题默认值",
    "Keep smart light/dark choices": "保留智能浅色/深色选择",
    "Your selection is saved to features.json": "您的选择将保存到 features.json",
    "Shift Interval": "移位间隔", "Max Shift": "最大移位",
    "needs OLED Care": "需要 OLED 保护",
    "replace custom light/dark choices once": "一次性替换自定义浅色/深色选择",
    "Reset Saved Wallpapers": "重置已保存的壁纸",
    "VERIFICATION": "验证", "BUILDING": "构建", "INSTALLING": "安装",
    "RESTORING": "恢复", "REMOVING": "删除",
    "Done — press any key to exit.": "完成——按任意键退出。",
    "Finished with errors — full log: {path}": "已完成，但有错误——完整日志：{path}",
    "Working…  press Ctrl-C to abort": "正在处理……按 Ctrl-C 中止",
}


_FEATURE_LABELS = {
    "fonts": "Fonts", "color_schemes": "Color Schemes",
    "plasma_theme": "Plasma Theme", "window_decorations": "Window Decorations",
    "kvantum": "Kvantum Theme", "icons": "Icons", "cursors": "Cursors",
    "wallpapers": "Wallpapers", "global_theme": "Global Theme",
    "layout": "Layout", "plasmoids": "Plasmoids", "globalmenu": "Global Menu",
    "acrylic_glass": "Acrylic Glass", "rounded_corners": "Rounded Corners",
    "sounds": "Sounds", "gtk": "GTK Theme", "firefox": "Firefox Theme",
    "sddm": "SDDM Login", "plymouth": "Plymouth", "apps": "Apps",
    "nautilus": "Nautilus", "nautilus_bookmarks": "Nautilus Bookmarks",
    "portals": "Portals", "oled_care": "OLED Care",
    "apply_theme": "Apply Theme", "kconf_update": "Config Migrations",
}

_ES.update({
    "Fonts": "Tipografías", "Color Schemes": "Esquemas de color",
    "Plasma Theme": "Tema de Plasma", "Window Decorations": "Decoraciones de ventanas",
    "Kvantum Theme": "Tema de Kvantum", "Icons": "Iconos", "Cursors": "Cursores",
    "Wallpapers": "Fondos de pantalla", "Global Theme": "Tema global",
    "Layout": "Disposición", "Plasmoids": "Plasmoides", "Global Menu": "Menú global",
    "Acrylic Glass": "Cristal acrílico", "Rounded Corners": "Esquinas redondeadas",
    "Sounds": "Sonidos", "GTK Theme": "Tema GTK", "Firefox Theme": "Tema de Firefox",
    "SDDM Login": "Inicio de sesión SDDM", "Plymouth": "Plymouth", "Apps": "Aplicaciones",
    "Nautilus": "Nautilus", "Nautilus Bookmarks": "Marcadores de Nautilus",
    "Portals": "Portales", "OLED Care": "Cuidado OLED",
    "Apply Theme": "Aplicar tema", "Config Migrations": "Migraciones de configuración",
    "Desktop backgrounds": "Fondos del escritorio", "SF Pro and SF Mono": "SF Pro y SF Mono",
    "Pointer theme": "Tema del puntero", "Panels and widgets": "Paneles y widgets",
    "Window frames": "Marcos de ventanas", "Qt app styling": "Estilo de aplicaciones Qt",
    "Light and dark palettes": "Paletas clara y oscura", "App and system icons": "Iconos de aplicaciones y del sistema",
    "Desktop widgets": "Widgets del escritorio", "Application menu bar": "Barra de menú de aplicaciones",
    "Window blur": "Desenfoque de ventanas", "Rounded windows": "Ventanas redondeadas",
    "Plasma look and feel": "Apariencia global de Plasma", "Top bar and Dock": "Barra superior y Dock",
    "System sound theme": "Tema de sonidos del sistema", "GTK app styling": "Estilo de aplicaciones GTK",
    "Browser theme": "Tema del navegador", "Login screen": "Pantalla de inicio de sesión",
    "Boot animation": "Animación de arranque", "Application settings": "Ajustes de aplicaciones",
    "File manager": "Gestor de archivos", "Sidebar shortcuts": "Accesos de la barra lateral",
    "KDE file dialogs": "Diálogos de archivos KDE", "Panel pixel shift": "Desplazamiento de píxeles del panel",
    "Activate after install": "Activar después de instalar", "Settings migrations": "Migraciones de ajustes",
})

_ZH_CN.update({
    "Fonts": "字体", "Color Schemes": "配色方案", "Plasma Theme": "Plasma 主题",
    "Window Decorations": "窗口装饰", "Kvantum Theme": "Kvantum 主题", "Icons": "图标",
    "Cursors": "光标", "Wallpapers": "壁纸", "Global Theme": "全局主题",
    "Layout": "布局", "Plasmoids": "Plasma 小程序", "Global Menu": "全局菜单",
    "Acrylic Glass": "亚克力玻璃", "Rounded Corners": "圆角", "Sounds": "声音",
    "GTK Theme": "GTK 主题", "Firefox Theme": "Firefox 主题", "SDDM Login": "SDDM 登录",
    "Plymouth": "Plymouth", "Apps": "应用", "Nautilus": "Nautilus",
    "Nautilus Bookmarks": "Nautilus 书签", "Portals": "门户", "OLED Care": "OLED 保护",
    "Apply Theme": "应用主题", "Config Migrations": "配置迁移",
    "Desktop backgrounds": "桌面背景", "SF Pro and SF Mono": "SF Pro 和 SF Mono",
    "Pointer theme": "指针主题", "Panels and widgets": "面板和小组件",
    "Window frames": "窗口边框", "Qt app styling": "Qt 应用样式",
    "Light and dark palettes": "浅色和深色调色板", "App and system icons": "应用和系统图标",
    "Desktop widgets": "桌面小组件", "Application menu bar": "应用菜单栏",
    "Window blur": "窗口模糊", "Rounded windows": "圆角窗口",
    "Plasma look and feel": "Plasma 外观与体验", "Top bar and Dock": "顶栏和 Dock",
    "System sound theme": "系统声音主题", "GTK app styling": "GTK 应用样式",
    "Browser theme": "浏览器主题", "Login screen": "登录屏幕", "Boot animation": "启动动画",
    "Application settings": "应用设置", "File manager": "文件管理器",
    "Sidebar shortcuts": "侧边栏快捷方式", "KDE file dialogs": "KDE 文件对话框",
    "Panel pixel shift": "面板像素移位", "Activate after install": "安装后激活",
    "Settings migrations": "设置迁移",
})

_TRANSLATIONS = {"es": _ES, "zh_CN": _ZH_CN}


def normalize_language(value: str | None) -> str:
    """Map locale spellings (``zh-CN.UTF-8``, ``es_CR``) to our codes."""
    text = (value or "").strip().replace("-", "_").split(".", 1)[0]
    low = text.lower()
    if low.startswith("zh_cn") or low.startswith("zh_hans") or low == "zh":
        return "zh_CN"
    if low.startswith("es"):
        return "es"
    if low.startswith("en"):
        return "en"
    return "en"


def system_language() -> str:
    for key in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        value = os.environ.get(key)
        if value:
            return normalize_language(value.split(":", 1)[0])
    try:
        value = locale.getlocale(locale.LC_MESSAGES)[0]
    except (AttributeError, ValueError):
        value = None
    return normalize_language(value)


def _config_path() -> Path:
    home = Path(os.environ.get("HOME") or Path.home())
    root = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return root / "mac-tahoe-liquid-kde/language.json"


def get_language() -> str:
    """Return the saved preference (``auto`` is intentionally preserved)."""
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "auto"
    code = data.get("language") if isinstance(data, dict) else None
    return code if code in LANGUAGE_CODES else "auto"


def effective_language(preference: str | None = None) -> str:
    code = preference if preference in LANGUAGE_CODES else get_language()
    return system_language() if code == "auto" else code


def set_language(code: str) -> bool:
    if code not in LANGUAGE_CODES:
        return False
    path = _config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix="language-", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"language": code}, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            os.replace(tmp_name, path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OSError:
        return False
    return True


def translate(message: str, language: str | None = None, **values: object) -> str:
    code = effective_language(language)
    result = _TRANSLATIONS.get(code, {}).get(message, message)
    return result.format(**values) if values else result


def feature_label(key: str, language: str | None = None) -> str:
    source = _FEATURE_LABELS.get(key, key.replace("_", " ").title())
    return translate(source, language)


def language_options(language: str | None = None) -> list[dict[str, str]]:
    """Native labels stay recognizable even after changing languages."""
    options = [dict(item) for item in LANGUAGES]
    options[0]["label"] = translate("System default", language)
    return options

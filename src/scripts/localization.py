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
    {"code": "pt_BR", "label": "Português (Brasil)"},
    {"code": "de", "label": "Deutsch"},
    {"code": "fr", "label": "Français"},
    {"code": "it", "label": "Italiano"},
)
LANGUAGE_CODES = tuple(item["code"] for item in LANGUAGES)


_ES = {
    "Could not install desktop settings launcher: {error}": "No se pudo instalar el lanzador de Ajustes: {error}",
    "Could not update widget configuration shortcuts.": "No se pudieron actualizar los accesos a los ajustes de los widgets.",
    "Application menus": "Menús de aplicaciones",
    "Show common menus for applications without a menu bar": "Mostrar menús comunes en aplicaciones sin barra de menús",
    "Search application menu actions": "Buscar acciones de los menús",
    "Switch open menus on hover": "Cambiar de menú al pasar el puntero",
    "Use a single button for the application menu": "Usar un solo botón para el menú de la aplicación",
    "Show menus for apps on different screens": "Mostrar menús de aplicaciones en otras pantallas",
    "World clocks": "Relojes mundiales",
    "World Clock I": "Reloj mundial I",
    "World Clock II": "Reloj mundial II",
    "World Clock III": "Reloj mundial III",
    "Digital World Clock": "Reloj mundial digital",
    "Time zones": "Zonas horarias",
    "Time zone": "Zona horaria",
    "Calendar sources": "Fuentes del calendario",
    "Scale text with widget size": "Ajustar el texto al tamaño del widget",
    "Calendar grid text size": "Tamaño del texto del calendario",
    "Event list text size": "Tamaño del texto de los eventos",
    "Player filter": "Filtro de reproductores",
    "Media players": "Reproductores",
    "Show selected players": "Mostrar reproductores seleccionados",
    "Hide selected players": "Ocultar reproductores seleccionados",
    "Refresh album art on track changes": "Actualizar la portada al cambiar de pista",
    "Blur upcoming lines": "Desenfocar los versos siguientes",
    "Current line opacity": "Opacidad del verso actual",
    "Other line opacity": "Opacidad de los demás versos",
    "Wide layout text size": "Tamaño del texto en formato ancho",
    "Tall layout text size": "Tamaño del texto en formato alto",
    'Downloads': 'Descargas',
    'No completed downloads yet': 'Todavía no hay descargas completadas',
    'Open Downloads': 'Abrir Descargas',
    'Open recent files or drag them into an application': 'Abre archivos recientes o arrástralos a una aplicación',
    'Open this file, or drag it into an application': 'Abre este archivo o arrástralo a una aplicación',
    "KWin could not activate the installed KDE Rounded Corners build": "KWin no pudo activar la compilación instalada de KDE Rounded Corners",
    "Icon appearance": "Apariencia de los iconos",
    "Automatic": "Automático",
    "Dock follows screen": "El Dock sigue la pantalla",
    "Dock on several screens": "Dock en varias pantallas",
    "Dock behaviour could not be enabled in kwinrc": "No se pudo activar el comportamiento del Dock en kwinrc",
    "Notification Center": "Centro de notificaciones",
    "Options": "Opciones",
    "On": "Activado",
    "Off": "Desactivado",
    "Audio outputs": "Salidas de audio",
    "File Sharing": "Compartir archivos",
    "Overview": "Vista general",
    "Screen Mirroring": "Duplicar pantalla",
    "Dark Mode": "Modo oscuro",
    "Screenshot": "Captura de pantalla",
    "Display Settings…": "Configuración de pantalla…",
    "Connected": "Conectado",

    "Edit Controls": "Editar controles",
    "Focus": "Concentración",
    "%1 — %2%": "%1 — %2%",
    "%1%": "%1%",
    "Balanced": "Equilibrado",
    "Battery": "Batería",
    "Connect a battery to see its status.": "Conecta una batería para ver su estado.",
    "Battery — %1%": "Batería — %1%",
    "Bluetooth": "Bluetooth",
    "Bluetooth Settings…": "Ajustes de Bluetooth…",
    "Brightness control unavailable": "Control de brillo no disponible",
    "Cancel Job": "Cancelar tarea",
    "Charging": "Cargando",
    "Clear History": "Borrar historial",
    "Collapse": "Contraer",
    "Connected to power": "Conectado a la corriente",
    "Control Center": "Centro de control",
    "Controlled by another application": "Controlado por otra aplicación",
    "Dismiss": "Descartar",
    "Display": "Pantalla",
    "Do Not Disturb": "No molestar",
    "Energy Settings…": "Ajustes de energía…",
    "Energy mode": "Modo de energía",
    "Expand": "Expandir",
    "Fully charged": "Carga completa",
    "Mute sound": "Silenciar sonido",
    "Network": "Red",
    "Network Settings…": "Ajustes de red…",
    "Next track": "Pista siguiente",
    "No Wi-Fi adapter": "No hay adaptador Wi-Fi",
    "No audio output": "No hay salida de audio",
    "No internal battery": "No hay batería interna",
    "No notifications": "No hay notificaciones",
    "Not connected": "Sin conexión",
    "Nothing playing": "No se está reproduciendo nada",
    "Notification Settings…": "Ajustes de notificaciones…",
    "Notifications": "Notificaciones",
    "Now Playing": "En reproducción",
    "On battery power": "Usando la batería",
    "Pause": "Pausar",
    "Pause notifications for one hour": "Pausar las notificaciones durante una hora",
    "Performance": "Rendimiento",
    "Play or pause": "Reproducir o pausar",
    "Power saver": "Ahorro de energía",
    "Previous track": "Pista anterior",
    "Reply…": "Responder…",
    "Resume": "Reanudar",
    "Scan for Networks": "Buscar redes",
    "Scanning…": "Buscando…",
    "Send": "Enviar",
    "Sound": "Sonido",
    "Volume": "Volumen",
    "Wi-Fi": "Wi-Fi",
    "Wi-Fi is blocked by the hardware switch": "El interruptor físico bloquea el Wi-Fi",
    "Wi-Fi is off": "El Wi-Fi está desactivado",

    "Icons unchanged — skipping generation and installation": "Iconos sin cambios — se omiten la generación y la instalación",
    "{label} (unchanged)": "{label} (sin cambios)",
    'Dock preset update failed': 'No se pudo actualizar el preset del Dock',
    'Recovered {size} MiB. Git ancestry and local recovery data were preserved.': 'Se recuperaron {size} MiB. Se conservaron la ascendencia de Git y los datos locales de recuperación.',
    'Published historical files may download again on demand; current source and local work stay available.': 'Los archivos históricos publicados pueden descargarse de nuevo cuando se necesiten; el código actual y el trabajo local siguen disponibles.',
    'Git maintenance disabled by local configuration.': 'El mantenimiento de Git está desactivado en la configuración local.',
    'Compacting Git storage: {path}': 'Compactando el almacenamiento de Git: {path}',
    'Recovered {size} MiB. Git history and recovery data were preserved.': 'Se recuperaron {size} MiB. Se conservaron el historial de Git y los datos de recuperación.',
    'Files still referenced by Git history remain; cleanup does not remove older commits.': 'Los archivos referenciados por el historial de Git se conservan; la limpieza no elimina commits antiguos.',
    'Git maintenance could not finish: {reason}': 'No se pudo completar el mantenimiento de Git: {reason}',
    'No independent Git checkout (archives need no Git cleanup).': 'No hay un clon independiente de Git (los archivos descargados no necesitan limpiar Git).',
    'Shared object store or linked worktrees; leaving it unchanged.': 'El almacén de objetos es compartido o tiene árboles de trabajo vinculados; se conserva sin cambios.',
    'Not the root of a Git checkout.': 'La carpeta no es la raíz de un clon de Git.',
    'Could not remove old Rounded Corners cache: {exc}': 'No se pudo eliminar la caché antigua de Rounded Corners: {exc}',
    "Generating icons: {completed}/{total}": "Generando iconos: {completed}/{total}",
    "Cron entries installed, but no running cron daemon could be confirmed. Enable your cron service for scheduled features.": "Se instalaron las entradas de cron, pero no se pudo confirmar que haya un servicio cron en ejecución. Activa el servicio cron para las funciones programadas.",

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
    "Application menus": "应用程序菜单",
    "Blur upcoming lines": "模糊后续歌词",
    "Calendar grid text size": "日历网格文字大小",
    "Calendar sources": "日历来源",
    "Could not update widget configuration shortcuts.": "无法更新小组件设置快捷方式。",
    "Current line opacity": "当前歌词行的不透明度",
    "Digital World Clock": "数字世界时钟",
    "Event list text size": "事件列表文字大小",
    "Hide selected players": "隐藏选中的播放器",
    "Media players": "媒体播放器",
    "Other line opacity": "其他歌词行的不透明度",
    "Player filter": "播放器筛选",
    "Refresh album art on track changes": "切换曲目时刷新专辑封面",
    "Scale text with widget size": "随小组件大小缩放文字",
    "Show selected players": "显示选中的播放器",
    "Tall layout text size": "纵向布局文字大小",
    "Time zone": "时区",
    "Time zones": "时区",
    "Use a single button for the application menu": "使用单个按钮显示应用程序菜单",
    "Wide layout text size": "横向布局文字大小",
    "World Clock I": "世界时钟 I",
    "World Clock II": "世界时钟 II",
    "World Clock III": "世界时钟 III",
    "World clocks": "世界时钟",
    "Show common menus for applications without a menu bar": "为没有菜单栏的应用程序显示通用菜单",
    "Search application menu actions": "搜索应用程序菜单操作",
    "Switch open menus on hover": "悬停时切换打开的菜单",
    "Show menus for apps on different screens": "在其他屏幕上显示应用程序菜单",
    "Could not install desktop settings launcher: {error}": "无法安装桌面设置启动器：{error}",
    'Downloads': '下载',
    'No completed downloads yet': '暂无已完成的下载',
    'Open Downloads': '打开下载文件夹',
    'Open recent files or drag them into an application': '打开最近的文件，或将其拖入应用程序',
    'Open this file, or drag it into an application': '打开此文件，或将其拖入应用程序',
    "KWin could not activate the installed KDE Rounded Corners build": "KWin 无法启用已安装的 KDE Rounded Corners 版本",
    "Icon appearance": "图标外观",
    "Automatic": "自动",
    "Dock follows screen": "Dock 跟随屏幕",
    "Dock on several screens": "多屏幕 Dock",
    "Dock behaviour could not be enabled in kwinrc": "无法在 kwinrc 中启用 Dock 行为",
    "Notification Center": "通知中心",
    "Options": "选项",
    "On": "开启",
    "Off": "关闭",
    "Audio outputs": "音频输出",
    "File Sharing": "文件共享",
    "Overview": "概览",
    "Screen Mirroring": "屏幕镜像",
    "Dark Mode": "深色模式",
    "Screenshot": "截屏",
    "Display Settings…": "显示设置…",
    "Connected": "已连接",

    "Edit Controls": "编辑控制",
    "Focus": "专注模式",
    "%1 — %2%": "%1 — %2%",
    "%1%": "%1%",
    "Balanced": "平衡",
    "Battery": "电池",
    "Connect a battery to see its status.": "连接电池以查看其状态。",
    "Battery — %1%": "电池 — %1%",
    "Bluetooth": "蓝牙",
    "Bluetooth Settings…": "蓝牙设置…",
    "Brightness control unavailable": "亮度控制不可用",
    "Cancel Job": "取消任务",
    "Charging": "正在充电",
    "Clear History": "清除历史记录",
    "Collapse": "收起",
    "Connected to power": "已连接电源",
    "Control Center": "控制中心",
    "Controlled by another application": "由其他应用控制",
    "Dismiss": "关闭",
    "Display": "显示器",
    "Do Not Disturb": "勿扰模式",
    "Energy Settings…": "电源设置…",
    "Energy mode": "电源模式",
    "Expand": "展开",
    "Fully charged": "已充满",
    "Mute sound": "静音",
    "Network": "网络",
    "Network Settings…": "网络设置…",
    "Next track": "下一首",
    "No Wi-Fi adapter": "没有无线网卡",
    "No audio output": "没有音频输出",
    "No internal battery": "没有内置电池",
    "No notifications": "没有通知",
    "Not connected": "未连接",
    "Nothing playing": "未在播放",
    "Notification Settings…": "通知设置…",
    "Notifications": "通知",
    "Now Playing": "正在播放",
    "On battery power": "使用电池供电",
    "Pause": "暂停",
    "Pause notifications for one hour": "暂停通知一小时",
    "Performance": "性能",
    "Play or pause": "播放或暂停",
    "Power saver": "节能",
    "Previous track": "上一首",
    "Reply…": "回复…",
    "Resume": "继续",
    "Scan for Networks": "扫描网络",
    "Scanning…": "正在扫描…",
    "Send": "发送",
    "Sound": "声音",
    "Volume": "音量",
    "Wi-Fi": "无线网络",
    "Wi-Fi is blocked by the hardware switch": "无线网络已被硬件开关禁用",
    "Wi-Fi is off": "无线网络已关闭",

    "Icons unchanged — skipping generation and installation": "图标未更改 — 跳过生成和安装",
    "{label} (unchanged)": "{label}（未更改）",
    'Dock preset update failed': 'Dock 预设更新失败',
    'Recovered {size} MiB. Git ancestry and local recovery data were preserved.': '已回收 {size} MiB。Git 提交关系和本地恢复数据已保留。',
    'Published historical files may download again on demand; current source and local work stay available.': '已发布的历史文件可按需重新下载；当前源代码和本地工作仍然可用。',
    'Git maintenance disabled by local configuration.': '本地配置已禁用 Git 维护。',
    'Compacting Git storage: {path}': '正在压缩 Git 存储：{path}',
    'Recovered {size} MiB. Git history and recovery data were preserved.': '已回收 {size} MiB。Git 历史记录和恢复数据已保留。',
    'Files still referenced by Git history remain; cleanup does not remove older commits.': 'Git 历史记录仍引用的文件将被保留；清理不会删除旧提交。',
    'Git maintenance could not finish: {reason}': 'Git 维护未能完成：{reason}',
    'No independent Git checkout (archives need no Git cleanup).': '没有独立的 Git 工作副本（归档文件无需清理 Git）。',
    'Shared object store or linked worktrees; leaving it unchanged.': '存在共享对象存储或关联工作树；保持不变。',
    'Not the root of a Git checkout.': '此目录不是 Git 工作副本的根目录。',
    'Could not remove old Rounded Corners cache: {exc}': '无法删除旧的 Rounded Corners 缓存：{exc}',
    "Generating icons: {completed}/{total}": "正在生成图标：{completed}/{total}",
    "Cron entries installed, but no running cron daemon could be confirmed. Enable your cron service for scheduled features.": "已安装 cron 条目，但无法确认 cron 守护进程正在运行。请启用 cron 服务以运行计划任务。",

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

_ES.update({'PyQt6 is required for the graphical installer but could not be imported.\n  Install the python-pyqt6 package for your distribution and re-run ./installer.': 'El instalador gráfico necesita PyQt6, pero no se pudo importar.\n  Instala PyQt6 para tu distribución y vuelve a ejecutar ./installer.'})
_ZH_CN.update({'PyQt6 is required for the graphical installer but could not be imported.\n  Install the python-pyqt6 package for your distribution and re-run ./installer.': '图形安装程序需要 PyQt6，但无法导入。\n  请安装适合你的发行版的 PyQt6，然后重新运行 ./installer。'})

_ES["Rollback: {command}"] = "Revertir: {command}"
_ZH_CN["Rollback: {command}"] = "回退：{command}"

_ES.update({'Dock apps': 'Apps del Dock',
 'Dock visibility': 'Visibilidad del Dock',
 'Auto-hide': 'Ocultar automáticamente',
 'Show outside full screen': 'Mostrar salvo en pantalla completa',
 'Hide on overlap': 'Ocultar si una ventana lo cubre',
 'Dock apps…': 'Apps del Dock…',
 'Installed equivalents are reused. Select only the missing apps you want to install.': 'Se '
                                                                                        'reutilizan '
                                                                                        'las apps '
                                                                                        'equivalentes '
                                                                                        'instaladas. '
                                                                                        'Selecciona '
                                                                                        'solo las '
                                                                                        'apps '
                                                                                        'faltantes '
                                                                                        'que '
                                                                                        'quieras '
                                                                                        'instalar.',
 'Distribution repositories': 'Repositorios de la distribución',
 'Flatpak for my user (installs Flatpak if needed)': 'Flatpak para mi usuario (instala Flatpak si '
                                                     'hace falta)',
 'Allow adding Flathub for my user if it is missing': 'Permitir añadir Flathub para mi usuario si '
                                                      'falta',
 'Flatpak apps may use their own appearance. No system remote is changed.': 'Las apps Flatpak '
                                                                            'pueden tener su '
                                                                            'propia apariencia. No '
                                                                            'se cambia ningún '
                                                                            'repositorio del '
                                                                            'sistema.',
 'Unavailable from this source': 'No disponible en este origen',
 'Availability is checked during installation. Failed apps remain pending; removing the theme keeps your apps.': 'La '
                                                                                                                 'disponibilidad '
                                                                                                                 'se '
                                                                                                                 'comprueba '
                                                                                                                 'al '
                                                                                                                 'instalar. '
                                                                                                                 'Las '
                                                                                                                 'apps '
                                                                                                                 'que '
                                                                                                                 'fallen '
                                                                                                                 'quedan '
                                                                                                                 'pendientes; '
                                                                                                                 'desinstalar '
                                                                                                                 'el '
                                                                                                                 'tema '
                                                                                                                 'conserva '
                                                                                                                 'tus '
                                                                                                                 'apps.',
 'Use installed apps only': 'Usar solo las apps instaladas',
 'Could not add {app}. The theme will continue; this Dock category remains pending.': 'No se pudo '
                                                                                      'añadir '
                                                                                      '{app}. El '
                                                                                      'tema '
                                                                                      'continuará; '
                                                                                      'esta '
                                                                                      'categoría '
                                                                                      'del Dock '
                                                                                      'queda '
                                                                                      'pendiente.',
 'Mail': 'Correo',
 'Calendar': 'Calendario',
 'Notes': 'Notas',
 'Photos': 'Fotos',
 'Music': 'Música',
 'Video': 'Vídeo'})
_ZH_CN.update({'Dock apps': 'Dock 应用',
 'Dock visibility': 'Dock 可见性',
 'Auto-hide': '自动隐藏',
 'Show outside full screen': '非全屏时显示',
 'Hide on overlap': '窗口重叠时隐藏',
 'Dock apps…': 'Dock 应用…',
 'Installed equivalents are reused. Select only the missing apps you want to install.': '将使用已安装的同类应用。仅选择要安装的缺失应用。',
 'Distribution repositories': '发行版软件仓库',
 'Flatpak for my user (installs Flatpak if needed)': '为当前用户安装 Flatpak 应用（必要时安装 Flatpak）',
 'Allow adding Flathub for my user if it is missing': '允许为当前用户添加尚未配置的 Flathub',
 'Flatpak apps may use their own appearance. No system remote is changed.': 'Flatpak '
                                                                            '应用的外观可能不同。不会更改系统级远程仓库。',
 'Unavailable from this source': '此来源不可用',
 'Availability is checked during installation. Failed apps remain pending; removing the theme keeps your apps.': '安装时将检查可用性。安装失败的应用将保持待添加状态；卸载主题不会删除应用。',
 'Use installed apps only': '仅使用已安装的应用',
 'Could not add {app}. The theme will continue; this Dock category remains pending.': '无法添加 '
                                                                                      '{app}。主题安装将继续；此 '
                                                                                      'Dock '
                                                                                      '类别保持待添加状态。',
 'Mail': '邮件',
 'Calendar': '日历',
 'Notes': '笔记',
 'Photos': '照片',
 'Music': '音乐',
 'Video': '视频'})

_ES["Removed {size} MiB of temporary compiler objects."] = "Se eliminaron {size} MiB de archivos objeto temporales del compilador."
_ZH_CN["Removed {size} MiB of temporary compiler objects."] = "已删除 {size} MiB 的临时编译目标文件。"
# Installer diagnostics. Message keys are shared by the console and graphical log.
_ES.update({
    "Errors: {count}": "Errores: {count}",
    "Version {current} is up to date.": "La versión {current} está actualizada.",
    "--no-apply-theme: files installed but Plasma left untouched. Re-run with --apply-theme to switch over.": "Archivos instalados con --no-apply-theme. Para activar el tema en Plasma, ejecute el instalador con --apply-theme.",
    "  \u001b[0;90mReport bugs at: https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new\u001b[0m": "  Informes de errores: https://github.com/lestercorderomurillo/macos-tahoe-liquid-kde/issues/new",
    "       └ not referenced in layout JS (optional)": "    Componente opcional sin referencia en el script de distribución.",
    "  Qt plugins: {plugins}": "  Complementos de Qt: {plugins}",
    "  Qt qml:     {qml}": "  Módulos QML de Qt: {qml}",
    "  free on {home_probe}: {home_free_mb} MB": "  Espacio disponible en {home_probe}: {home_free_mb} MB",
    "  free on {probe}: {usr_free_mb} MB": "  Espacio disponible en {probe}: {usr_free_mb} MB",
    "  probe path: {probe}": "  Ruta de comprobación: {probe}",
    "  …  Reconfiguring KWin": "  Actualizando la configuración de KWin…",
    "  …  Restarting Plasma": "  Reiniciando Plasma…",
    "Acrylic Glass KCM installed": "Módulo de configuración de Acrylic Glass instalado",
    "Acrylic Glass installed": "Acrylic Glass instalado",
    "Acrylic Glass loaded": "Acrylic Glass cargado",
    "Acrylic Glass material settings ready": "Configuración del material de Acrylic Glass preparada",
    "Acrylic Glass translation installed: {language}": "Traducción de Acrylic Glass instalada: {language}",
    "Administrative privileges": "Permisos de administración",
    "All required packages are installed": "Todos los paquetes necesarios están instalados",
    "Applied {copied} Nautilus override(s)": "Ajustes aplicados a Nautilus: {copied}",
    "Applies settings, flushes caches, restarts KWin": "Aplicación de los ajustes, limpieza de cachés y reinicio de KWin.",
    "Applying Changes": "Aplicación de los cambios",
    "Applying preferences": "Aplicación de preferencias",
    "Available disk space": "Espacio disponible en disco",
    "Bookmarks written ({value1} entries)": "Marcadores guardados: {value1}",
    "Boot splash activated": "Pantalla de arranque activada",
    "Boot splash files": "Archivos de la pantalla de arranque",
    "Building Compiled Components": "Compilación de componentes",
    "Building components": "Compilación de componentes",
    "Building {label}": "Compilación: {label}",
    "Builds C++ plasmoids and KWin effects — must succeed before install": "Compilación de los componentes de Plasma en C++ y de los efectos de KWin antes de la instalación.",
    "Caches flushed": "Cachés vaciadas",
    "Cancelling…": "Cancelando…",
    "Checking and installing required tools": "Comprobación e instalación de las herramientas necesarias.",
    "Checking theme configuration was applied": "Verificación de la configuración del tema.",
    "Checks KDE version": "Comprobación de la versión de KDE.",
    "Checks KDE version and required tools": "Comprobación de la versión de KDE y de las herramientas necesarias.",
    "Clipboard": "Portapapeles",
    "Clipboard history (Meta+V)": "Historial del portapapeles (Meta+V)",
    "Clipboard history is stored privately in ~/.local/share/mac-tahoe-liquid-kde/clipboard": "El historial del portapapeles se guarda en el directorio privado ~/.local/share/mac-tahoe-liquid-kde/clipboard",
    "Clipboard service": "Servicio del portapapeles",
    "Clipboard service and popup installed": "Servicio y ventana del portapapeles instalados",
    "Color scheme": "Esquema de color",
    "Continuous menu corners": "Estilo de menús con esquinas continuas",
    "Continuous menu corners built": "Estilo de esquinas continuas para los menús compilado",
    "Continuous menu corners installed": "Estilo de esquinas continuas para los menús instalado",
    "Control Center transition": "Transición del centro de control",
    "Copy diagnostic": "Copiar diagnóstico",
    "Couldn't save log: {error}": "No se pudo guardar el registro: {error}",
    "Cursor theme": "Tema de cursor",
    "D-Bus session": "Sesión D-Bus",
    "DBus session bus reachable ({value1})": "Bus de sesión D-Bus disponible ({value1})",
    "Dependencies": "Dependencias",
    "Dock Task Manager": "Gestor de tareas del Dock",
    "Dock motion": "Animación del Dock",
    "Downloading Online Components": "Descarga de componentes",
    "Downloading {label}": "Descarga: {label}",
    "Elapsed {duration}": "Tiempo transcurrido: {duration}",
    "Error": "Error",
    "Fetches the pinned KDE Rounded Corners source and verifies SHA-256": "Descarga de la versión especificada de KDE Rounded Corners y verificación de su suma SHA-256.",
    "Final checks": "Comprobaciones finales",
    "Firefox profile themed: {value1}": "Tema de Firefox aplicado al perfil {value1}",
    "Firefox profiles modified: 0": "Perfiles de Firefox modificados: 0",
    "Firefox theme skipped. Open Firefox to create a profile, then run the installer again.": "Se omitió el tema de Firefox. Para aplicarlo, abra Firefox una vez para crear un perfil y vuelva a ejecutar el instalador.",
    "Firefox theme: {changed}/{value2} profiles installed; restart browsers to apply": "Tema de Firefox aplicado a {changed} de {value2} perfiles. Reinicie Firefox para cargar los cambios.",
    "Fonts installed": "Tipos de letra instalados",
    "Forced UseSimpledrm=true (keeps the shutdown splash full-size)": "UseSimpledrm=true configurado para mantener la pantalla de apagado a tamaño completo",
    "Full log storage is unavailable. Only the latest output is retained.": "No se pudo guardar el registro completo. Se conservan las últimas líneas.",
    "GTK Global Menu startup integration": "Integración del menú global de GTK al iniciar sesión",
    "GTK themes installed or reinstalled: {n}": "Temas GTK instalados o reinstalados: {n}",
    "Generating icons: {completed}/{total}": "Iconos generados: {completed} de {total}",
    "Global Menu": "Menú global",
    "Global Menu installed": "Menú global instalado",
    "Global Menu runtime QML": "Módulo QML del menú global",
    "Global Menu {language} translation installed": "Traducción del menú global instalada: {language}",
    "Hide details": "Ocultar detalles",
    "Icon theme": "Tema de iconos",
    "Installation paths": "Rutas de instalación",
    "Installation stopped. A system check failed.": "Instalación detenida. Falló una comprobación del sistema.",
    "Installation stopped. The package manager could not install the required dependencies.": "Instalación detenida. El gestor de paquetes no pudo instalar las dependencias necesarias.",
    "Installing Layout": "Instalación de la distribución del escritorio",
    "Installing OLED Care": "Instalación de la protección OLED",
    "Installing Theme Switcher": "Instalación del selector de apariencia",
    "Installing components": "Instalación de componentes",
    "Installing required packages: {value1}": "Instalación de paquetes necesarios: {value1}",
    "Installing {edition}": "Instalación de {edition}",
    "Installing {label}": "Instalación: {label}",
    "Installs the auto light/dark theme switcher": "Instalación del servicio de cambio automático entre apariencia clara y oscura.",
    "KDE Plasma version": "Versión de KDE Plasma",
    "KDE Rounded Corners GPL-3.0 license installed": "Licencia GPL-3.0 de KDE Rounded Corners instalada",
    "KDE Rounded Corners active radius": "Radio de las esquinas de la ventana activa",
    "KDE Rounded Corners core shader installed": "Sombreador principal de KDE Rounded Corners instalado",
    "KDE Rounded Corners effect installed": "Efecto KDE Rounded Corners instalado",
    "KDE Rounded Corners inactive radius": "Radio de las esquinas de las ventanas inactivas",
    "KDE Rounded Corners loaded": "Efecto KDE Rounded Corners cargado",
    "KDE Rounded Corners radius set to {CORNER_RADIUS}": "Radio de las esquinas configurado: {CORNER_RADIUS}",
    "KDE Rounded Corners settings installed": "Configuración de KDE Rounded Corners instalada",
    "KDE Rounded Corners shader installed": "Sombreador de KDE Rounded Corners instalado",
    "KDE Rounded Corners v{UPSTREAM_VERSION} downloaded and verified{suffix}": "KDE Rounded Corners {UPSTREAM_VERSION} descargado y verificado{suffix}",
    "KDE Rounded Corners v{UPSTREAM_VERSION} installed from verified upstream source": "KDE Rounded Corners {UPSTREAM_VERSION} instalado desde el código fuente verificado del proyecto.",
    "KDE configuration tools": "Herramientas de configuración de KDE",
    "KDE portal routing installed": "Configuración de los portales de KDE instalada",
    "KWin reconfigured": "Configuración de KWin aplicada",
    "KWin reconfigured ": "Configuración de KWin aplicada",
    "Kvantum GPL-3.0 license installed": "Licencia GPL-3.0 de Kvantum instalada",
    "Kvantum Qt 6 engine v{ENGINE_VERSION} built": "Motor Kvantum para Qt 6 compilado (versión {ENGINE_VERSION})",
    "Kvantum Qt 6 engine v{ENGINE_VERSION} installed": "Motor Kvantum para Qt 6 instalado (versión {ENGINE_VERSION})",
    "Kvantum Qt 6 engine v{version}": "Motor Kvantum para Qt 6 (versión {version})",
    "Kvantum Qt styling removed": "Estilo Kvantum eliminado de las aplicaciones Qt",
    "Kvantum installation record prepared": "Registro de instalación de Kvantum preparado",
    "Kvantum source information recorded": "Origen de Kvantum registrado",
    "Kvantum style installed for Qt applications": "Estilo Kvantum instalado para las aplicaciones Qt",
    "Latest 2,000 lines. Copy or save includes the complete output.": "Se muestran las últimas 2000 líneas. Al copiar o guardar se incluye el registro completo.",
    "Launcher and Dock": "Lanzador y Dock",
    "Layout installed": "Distribución del escritorio instalada",
    "Layout installed (kept {count} pinned apps)": "Distribución del escritorio instalada. Aplicaciones fijadas conservadas: {count}.",
    "Log files (*.log);;All files (*)": "Archivos de registro (*.log);;Todos los archivos (*)",
    "Log out and back in to enable GTK Global Menu crash protection": "Cierre la sesión y vuelva a iniciarla para activar la protección frente a fallos del menú global de GTK.",
    "MacTahoe Liquid KDE {verb} successfully": "MacTahoe Liquid KDE: {verb}",
    "MacTahoe sound theme": "Tema de sonido MacTahoe",
    "Menu style": "Estilo de los menús",
    "Meta+V now opens the clipboard popup": "Atajo del portapapeles configurado: Meta+V",
    "Nautilus configured": "Nautilus configurado",
    "Nautilus set as default for folders": "Nautilus configurado como aplicación predeterminada para abrir carpetas",
    "Next reboot will show the {THEME_NAME} splash.": "En el próximo arranque se mostrará el tema {THEME_NAME}.",
    "OLED care disabled — enable with --oled-care": "Protección OLED desactivada. Puede activarse con --oled-care.",
    "Opt-in pixel shift that guards OLED panels against burn-in": "Desplazamiento opcional de píxeles para reducir la retención de imagen en pantallas OLED.",
    "Panel glass forced translucent": "Translucidez del panel aplicada",
    "Plasma restarted ": "Plasma reiniciado",
    "Plasma theme": "Tema de Plasma",
    "Plasma widget identifiers": "Identificadores de componentes de Plasma",
    "Plasma {major}.{minor} meets the {value3}.{value4}+ minimum": "Plasma {major}.{minor} cumple el requisito mínimo de versión ({value3}.{value4}).",
    "Preflight": "Comprobaciones previas",
    "Preparing…": "Preparando…",
    "Previous Acrylic Glass binary removed": "Ejecutable anterior de Acrylic Glass eliminado",
    "Qt 6 plugin paths": "Rutas de complementos de Qt 6",
    "Qt QML path discovered: {qml}": "Ruta de módulos QML de Qt: {qml}",
    "Qt plugin path discovered: {plugins}": "Ruta de complementos de Qt: {plugins}",
    "Removal stopped. A system check failed.": "Desinstalación detenida. Falló una comprobación del sistema.",
    "Removes the Mac top bar/Dock and preserves pinned applications": "Eliminación de la barra superior y del Dock. Se conservan las aplicaciones fijadas.",
    "Removing Clipboard": "Desinstalación del portapapeles",
    "Removing OLED Care": "Desinstalación de la protección OLED",
    "Removing Theme Switcher": "Desinstalación del selector de apariencia",
    "Removing components": "Desinstalación de componentes",
    "Removing {edition}": "Desinstalación de {edition}",
    "Removing {label}": "Desinstalación: {label}",
    "Resets to Breeze defaults before removing theme assets": "Restauración de los ajustes de Breeze antes de eliminar los archivos del tema.",
    "Resetting Layout": "Restauración de la distribución del escritorio",
    "Restarting Plasma": "Reinicio de Plasma",
    "Restarts Plasma shell to finalize changes": "Reinicio del escritorio Plasma para completar los cambios.",
    "Restarts Plasma shell to load all changes": "Reinicio del escritorio Plasma para cargar los cambios.",
    "Restoring desktop settings": "Restauración de los ajustes del escritorio",
    "Retries the panel layout after Plasma reloads new plasmoids": "Nuevo intento de aplicar la distribución tras cargar los componentes de Plasma.",
    "Retrying Layout": "Nuevo intento de aplicar la distribución del escritorio",
    "Rounded Corners locale: {value1}": "Traducción de Rounded Corners instalada: {value1}",
    "Save installation log": "Guardar registro de instalación",
    "Save log…": "Guardar registro…",
    "Show details": "Mostrar detalles",
    "Show summary": "Mostrar resumen",
    "Show technical output": "Mostrar registro técnico",
    "Skipped": "Omitido",
    "Skipping Activation": "Activación omitida",
    "Sound theme selected": "Tema de sonido seleccionado",
    "Step {number}: {title}": "Paso {number} · {title}",
    "Stops and removes the auto light/dark theme switcher": "Detención y eliminación del selector automático de apariencia.",
    "Stops the clipboard service, returns Meta+V to Plasma and deletes its history": "Detención del servicio del portapapeles, restauración de Meta+V en Plasma y eliminación del historial.",
    "Stops the pixel shift and restores panel geometry": "Detención del desplazamiento de píxeles y restauración de la geometría del panel.",
    "System checks": "Comprobaciones del sistema",
    "System info helper installed": "Herramienta de información del sistema instalada",
    "Theme applied ({value1})": "Tema aplicado ({value1})",
    "Theme switcher installed": "Selector de apariencia instalado",
    "Unchanged": "Sin cambios",
    "Verification": "Verificación",
    "Verifies sudo, paths, Qt6, KDE version, config tools, DBus, kded6, disk space, plasmoid IDs": "Comprobación de permisos, rutas, Qt 6, KDE, herramientas de configuración, D-Bus, kded6, espacio disponible e identificadores de componentes.",
    "Warning": "Advertencia",
    "Warnings": "Advertencias",
    "Widget style installed": "Estilo de los controles instalado",
    "Window decoration reset to Breeze": "Decoración de ventanas restaurada a Breeze",
    "Window decoration set to {chosen}": "Decoración de ventanas configurada: {chosen}",
    "Window decorations": "Decoración de ventanas",
    "acrylic-glass plugin dir": "Directorio de complementos de Acrylic Glass",
    "continuous menu style": "Estilo de menús con esquinas continuas",
    "disk space OK ({usr_free_mb} MB on system, {home_free_mb} MB on $HOME)": "Espacio disponible: {usr_free_mb} MB en el sistema y {home_free_mb} MB en $HOME",
    "dock config migrated to MacTahoe dock fork": "Configuración del Dock transferida al Dock de MacTahoe",
    "empty": "vacío",
    "features.json loaded": "Configuración de componentes cargada desde features.json",
    "globalmenu .so": "Biblioteca del menú global",
    "globalmenu GTK login environment": "Entorno de inicio de sesión del menú global de GTK",
    "globalmenu QML module": "Módulo QML del menú global",
    "icon theme": "Tema de iconos",
    "icon themes": "Temas de iconos",
    "installed": "instalado",
    "kconf_update scripts": "Scripts de migración de kconf_update",
    "kded6 is running": "Servicio kded6 en ejecución",
    "kded6 service (optional)": "Servicio kded6 (opcional)",
    "kvantum Qt6 style plugin": "Complemento de estilo Kvantum para Qt 6",
    "kvantum bundled-source license": "Licencia de la versión incluida de Kvantum",
    "kvantum bundled-source marker": "Registro del origen de Kvantum",
    "kwriteconfig6 + kreadconfig6 present": "Herramientas disponibles: kwriteconfig6 y kreadconfig6",
    "launcher QML module": "Módulo QML del lanzador",
    "mac-tahoe-liquid-kde theme (installed)": "Tema mac-tahoe-liquid-kde instalado",
    "mac-tahoe-liquid-kdeDark theme": "Tema mac-tahoe-liquid-kdeDark",
    "mac-tahoe-liquid-kdeDark theme (installed)": "Tema mac-tahoe-liquid-kdeDark instalado",
    "no online components selected — skipping download phase": "Descarga omitida. No se seleccionaron componentes en línea.",
    "org.kde.mac.tahoe.liquid.taskmanager (installed compiled dock base)": "Componente compilado del Dock instalado: org.kde.mac.tahoe.liquid.taskmanager",
    "org.kde.mac.tahoe.liquid.taskmanager (installed runtime QML)": "Módulo QML de org.kde.mac.tahoe.liquid.taskmanager instalado",
    "plasmoid": "Componente de Plasma",
    "plasmoids": "Componentes de Plasma",
    "plasmoids share dir": "Directorio compartido de componentes de Plasma",
    "removed": "eliminado",
    "rounded-corners license": "Licencia de Rounded Corners",
    "rounded-corners locale dir": "Directorio de traducciones de Rounded Corners",
    "rounded-corners plugin dir": "Directorio de complementos de Rounded Corners",
    "rounded-corners shader dir": "Directorio de sombreadores de Rounded Corners",
    "sudo hop ok — wrote, read, removed {value1}": "Permisos verificados mediante la escritura, lectura y eliminación de {value1}",
    "taskmanager .so": "Biblioteca del gestor de tareas",
    "taskmanager QML module": "Módulo QML del gestor de tareas",
    "uninstalled": "desinstalado",
    "{appearance} appearance · {launcher} launcher": "Apariencia: {appearance} · Lanzador: {launcher}",
    "{grp} — {value2} installed, {value3} reinstalled": "{grp}: {value2} instalaciones y {value3} reinstalaciones.",
    "{label} (copy failed)": "Error al copiar {label}",
    "{label} (expected {expected}, got {value3})": "{label}: se esperaba {expected}; se obtuvo {value3}",
    "{label} (installed)": "Instalación: {label}",
    "{label} (source missing: {src})": "No se encontró el archivo de origen de {label}: {src}",
    "{label} (unchanged)": "{label} (sin cambios)",
    "{label} built": "Compilación completada: {label}",
    "{label} removed": "Eliminación: {label}",
    "{label}: build failed": "Error de compilación: {label}",
    "{label}: cmake configure failed": "Error de configuración de CMake: {label}",
    "{message} (reinstalled)": "Reinstalación: {message}",
    "{minutes} min {seconds:02d} sec": "{minutes} min {seconds:02d} s",
    "{name} (installed)": "Instalación: {name}",
    "{name} (removed local override)": "Configuración local de {name} eliminada",
    "{n} Plasma themes installed/reinstalled": "Temas de Plasma instalados o reinstalados: {n}",
    "{n} cursor themes installed/reinstalled": "Temas de cursor instalados o reinstalados: {n}",
    "{n} {label} installed/reinstalled": "{label}: {n} instalaciones o reinstalaciones",
    "{seconds} sec": "{seconds} s",
    "{value1} (installed)": "Instalación: {value1}",
    "{value1} Aurorae themes — {n_inst} installed, {n_re} reinstalled": "Temas Aurorae: {value1}. Instalados: {n_inst}. Reinstalados: {n_re}.",
    "{value1} color schemes — {n_inst} installed, {n_re} reinstalled": "Esquemas de color: {value1}. Instalados: {n_inst}. Reinstalados: {n_re}.",
    "{value1} issue(s):": "Incidencias registradas: {value1}",
    "{value1} removed": "Eliminación: {value1}",
    "{value1} sound events installed/reinstalled": "Sonidos de eventos instalados o reinstalados: {value1}",
    "{value1} wallpapers — {n_inst} installed, {n_re} reinstalled": "Fondos de escritorio: {value1}. Instalados: {n_inst}. Reinstalados: {n_re}.",
    "{v} removed": "Eliminación: {v}",
    "~/.config/user-dirs.dirs not found — skipping Nautilus bookmarks": "Se omitieron los marcadores de Nautilus. No se encontró ~/.config/user-dirs.dirs."
})
_ZH_CN.update({
    "Errors: {count}": "错误数：{count}",
    "Version {current} is up to date.": "版本 {current} 已是最新版本。",
    "Kvantum Qt 6 engine v{version}": "Qt 6 的 Kvantum 引擎（版本 {version}）",
    "Administrative privileges": "管理权限",
    "All required packages are installed": "所需的软件包均已安装",
    "Applying preferences": "应用设置",
    "Available disk space": "可用磁盘空间",
    "Building components": "编译组件",
    "Building {label}": "编译：{label}",
    "Clipboard": "剪贴板",
    "Continuous menu corners installed": "已安装菜单连续圆角样式",
    "Copy diagnostic": "复制诊断信息",
    "Couldn't save log: {error}": "无法保存日志：{error}",
    "D-Bus session": "D-Bus 会话",
    "Dependencies": "依赖项",
    "Downloading {label}": "下载：{label}",
    "Downloads": "下载",
    "Elapsed {duration}": "已用时间：{duration}",
    "Error": "错误",
    "Final checks": "最终检查",
    "Firefox profiles modified: 0": "已修改的 Firefox 配置文件：0",
    "Firefox theme skipped. Open Firefox to create a profile, then run the installer again.": "已跳过 Firefox 主题。请打开 Firefox 创建配置文件，然后重新运行安装程序。",
    "Full log storage is unavailable. Only the latest output is retained.": "无法保存完整日志，仅保留最近的输出。",
    "GTK themes installed or reinstalled: {n}": "已安装或重新安装的 GTK 主题：{n}",
    "Generating icons: {completed}/{total}": "已生成图标：{completed}/{total}",
    "Global menu": "全局菜单",
    "Hide details": "隐藏详细信息",
    "Installation paths": "安装路径",
    "Installation stopped. A system check failed.": "安装已停止。一项系统检查失败。",
    "Installation stopped. The package manager could not install the required dependencies.": "安装已停止。软件包管理器无法安装所需的依赖项。",
    "Installing components": "安装组件",
    "Installing required packages: {value1}": "正在安装所需的软件包：{value1}",
    "Installing {edition}": "安装 {edition}",
    "Installing {label}": "正在安装：{label}",
    "KDE Plasma version": "KDE Plasma 版本",
    "KDE configuration tools": "KDE 配置工具",
    "Kvantum GPL-3.0 license installed": "已安装 Kvantum GPL-3.0 许可证",
    "Kvantum Qt 6 engine v{ENGINE_VERSION} installed": "已安装 Qt 6 的 Kvantum 引擎（版本 {ENGINE_VERSION}）",
    "Kvantum installation record prepared": "已准备 Kvantum 安装记录",
    "Kvantum source information recorded": "已记录 Kvantum 来源",
    "Kvantum style installed for Qt applications": "已为 Qt 应用安装 Kvantum 样式",
    "Latest 2,000 lines. Copy or save includes the complete output.": "显示最近 2000 行。复制或保存时会包含完整日志。",
    "Launcher and Dock": "启动器和程序坞",
    "Log files (*.log);;All files (*)": "日志文件 (*.log);;所有文件 (*)",
    "Menu style": "菜单样式",
    "Plasma widget identifiers": "Plasma 组件标识符",
    "Qt 6 plugin paths": "Qt 6 插件路径",
    "Removal stopped. A system check failed.": "卸载已停止。一项系统检查失败。",
    "Removing components": "移除组件",
    "Removing {edition}": "移除 {edition}",
    "Removing {label}": "正在移除：{label}",
    "Restoring desktop settings": "恢复桌面设置",
    "Rounded Corners": "圆角",
    "Save installation log": "保存安装日志",
    "Save log…": "保存日志…",
    "Show details": "显示详细信息",
    "Show summary": "显示摘要",
    "Show technical output": "显示技术日志",
    "Skipped": "已跳过",
    "Step {number}: {title}": "步骤 {number} · {title}",
    "System checks": "系统检查",
    "Unchanged": "未更改",
    "Warning": "警告",
    "Warnings": "警告",
    "Widget style installed": "已安装控件样式",
    "Window decoration set to {chosen}": "窗口装饰已设为 {chosen}",
    "kded6 service (optional)": "kded6 服务（可选）",
    "mac-tahoe-liquid-kde theme (installed)": "已安装 mac-tahoe-liquid-kde 主题",
    "mac-tahoe-liquid-kdeDark theme (installed)": "已安装 mac-tahoe-liquid-kdeDark 主题",
    "{appearance} appearance · {launcher} launcher": "外观：{appearance} · 启动器：{launcher}",
    "{label} (installed)": "已安装：{label}",
    "{message} (reinstalled)": "已重新安装：{message}",
    "{minutes} min {seconds:02d} sec": "{minutes} 分 {seconds:02d} 秒",
    "{name} (installed)": "已安装：{name}",
    "{seconds} sec": "{seconds} 秒",
    "{value1} (installed)": "已安装：{value1}",
    "{value1} Aurorae themes — {n_inst} installed, {n_re} reinstalled": "Aurorae 主题共 {value1} 个：新安装 {n_inst} 个，重新安装 {n_re} 个。"
})

_TRANSLATIONS = {"es": _ES, "zh_CN": _ZH_CN}


def _load_catalog(code: str) -> dict[str, str]:
    bundled = globals().get("_BUNDLED_CATALOGS")
    if bundled is not None:
        return bundled[code]
    path = Path(__file__).with_name("locales") / f"{code}.json"
    return json.loads(path.read_text(encoding="utf-8"))


for _code in ("pt_BR", "de", "fr", "it"):
    _TRANSLATIONS[_code] = _load_catalog(_code)


def normalize_language(value: str | None) -> str:
    """Map locale spellings (``zh-CN.UTF-8``, ``es_CR``) to our codes."""
    text = (value or "").strip().replace("-", "_").split(".", 1)[0]
    low = text.lower().split("@", 1)[0]
    if low in ("zh", "zh_cn", "zh_hans") or low.startswith("zh_hans_"):
        return "zh_CN"
    if low == "pt" or low == "pt_br":
        return "pt_BR"
    if low == "it" or low.startswith("it_"):
        return "it"
    if low == "fr" or low.startswith("fr_"):
        return "fr"
    if low == "de" or low.startswith("de_"):
        return "de"
    if low == "es" or low.startswith("es_"):
        return "es"
    if low == "en" or low.startswith("en_"):
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
    inherited = os.environ.get("MTTKDE_LANGUAGE")
    code = preference if preference in LANGUAGE_CODES else (
        inherited if inherited in LANGUAGE_CODES else get_language())
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


def tr(message: str, /, **values: object) -> str:
    """Translate a complete message before interpolating runtime values."""
    result = _TRANSLATIONS.get(effective_language(), {}).get(message, message)
    return result.format(**values) if values else result


def language_options(language: str | None = None) -> list[dict[str, str]]:
    """Native labels stay recognizable even after changing languages."""
    options = [dict(item) for item in LANGUAGES]
    options[0]["label"] = translate("System default", language)
    return options

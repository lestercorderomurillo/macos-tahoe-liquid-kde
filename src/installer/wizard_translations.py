"""Translations for the graphical wizard; English message IDs are the fallback."""

from localization import effective_language, translate

# English | Spanish | Simplified Chinese | Brazilian Portuguese | German
_ROWS = '''Which window controls would you like?|¿Qué controles de ventana prefieres?|你想使用哪种窗口控件？|Quais controles de janela você prefere?|Welche Fensterknöpfe möchtest du verwenden?
Window controls|Controles de ventana|窗口控件|Controles da janela|Fensterknöpfe
Flat|Planos|扁平|Planos|Flach
Glassy|Cristalinos|玻璃质感|Vítreos|Glasartig
Simple, solid colors.|Colores sólidos y sencillos.|简洁的纯色。|Cores sólidas e simples.|Schlichte, einfarbige Knöpfe.
Soft gradients and reflective highlights.|Degradados suaves y reflejos.|柔和的渐变与反光。|Gradientes suaves e reflexos.|Sanfte Farbverläufe und Lichtreflexe.
Close, minimize and maximize buttons.|Botones para cerrar, minimizar y maximizar.|关闭、最小化和最大化按钮。|Botões para fechar, minimizar e maximizar.|Knöpfe zum Schließen, Minimieren und Maximieren.
Window shadows|Sombras de las ventanas|窗口阴影|Sombras das janelas|Fensterschatten
None|Ninguna|无|Nenhuma|Keine
Soft|Suaves|柔和|Suaves|Weich
Medium|Medias|中等|Médias|Mittel
Hard|Fuertes|强烈|Fortes|Stark
No shadows|Sin sombras|无阴影|Sem sombras|Keine Schatten
Soft shadows|Sombras suaves|柔和阴影|Sombras suaves|Weiche Schatten
Medium shadows|Sombras medias|中等阴影|Sombras médias|Mittlere Schatten
Hard shadows|Sombras fuertes|强烈阴影|Sombras fortes|Starke Schatten
Applies to the theme's window decorations and GTK windows.|Se aplica a las decoraciones del tema y a las ventanas GTK.|应用于主题的窗口装饰和 GTK 窗口。|Aplica-se às decorações do tema e às janelas GTK.|Gilt für die Fensterdekorationen des Themes und GTK-Fenster.
Install Nautilus as your file manager?|¿Instalar Nautilus como administrador de archivos?|将 Nautilus 安装为文件管理器？|Instalar o Nautilus como gerenciador de arquivos?|Nautilus als Dateimanager installieren?
Install Nautilus|Instalar Nautilus|安装 Nautilus|Instalar Nautilus|Nautilus installieren
Install and use as the default file manager.|Instalar y usar como administrador de archivos predeterminado.|安装并设为默认文件管理器。|Instalar e usar como gerenciador de arquivos padrão.|Installieren und als Standard-Dateimanager verwenden.
Use Dolphin|Usar Dolphin|使用 Dolphin|Usar Dolphin|Dolphin verwenden
Skip Nautilus and use KDE's file manager.|Omitir Nautilus y usar el administrador de KDE.|跳过 Nautilus，使用 KDE 文件管理器。|Ignorar o Nautilus e usar o gerenciador do KDE.|Nautilus überspringen und den KDE-Dateimanager verwenden.
Skip Nautilus and keep my file manager|Omitir Nautilus y conservar mi administrador de archivos|跳过 Nautilus 并保留当前文件管理器|Ignorar o Nautilus e manter meu gerenciador de arquivos|Nautilus überspringen und meinen Dateimanager beibehalten
Keep my file manager|Conservar mi administrador de archivos|保留当前文件管理器|Manter meu gerenciador de arquivos|Meinen Dateimanager beibehalten
Reset Dock and panel customization|Restablecer la personalización del Dock y los paneles|重置程序坞和面板自定义设置|Redefinir personalizações do Dock e dos painéis|Anpassungen von Dock und Leisten zurücksetzen
Reinstall keeps your layout, sizes, hiding behavior and widgets unless reset is selected.|La reinstalación conserva la distribución, los tamaños, la ocultación y los widgets salvo que elijas restablecerlos.|重新安装会保留布局、大小、隐藏方式和组件，除非选择重置。|A reinstalação mantém o layout, tamanhos, ocultação e widgets, salvo se você escolher redefini-los.|Bei der Neuinstallation bleiben Anordnung, Größen, Ausblendverhalten und Miniprogramme erhalten, sofern du sie nicht zurücksetzt.
The current launcher setup is kept unless you reset the layout.|Se conserva la configuración del launcher salvo que restablezcas la distribución.|除非重置布局，否则保留当前启动器设置。|A configuração atual do lançador é mantida, salvo se você redefinir o layout.|Die aktuelle Starter-Konfiguration bleibt erhalten, sofern du die Anordnung nicht zurücksetzt.
Keep current layout|Conservar distribución actual|保留当前布局|Manter layout atual|Aktuelle Anordnung beibehalten
Reset layout|Restablecer distribución|重置布局|Redefinir layout|Anordnung zurücksetzen
Minimize|Minimizar|最小化|Minimizar|Minimieren
Maximize|Maximizar|最大化|Maximizar|Maximieren
Restore|Restaurar|还原|Restaurar|Wiederherstellen
Express install|Instalación rápida|快速安装|Instalação rápida|Schnellinstallation
Use the defaults and review before installing.|Usa los valores predeterminados y revísalos antes de instalar.|使用默认设置并在安装前检查。|Use as opções padrão e revise antes de instalar.|Standardeinstellungen vor der Installation überprüfen.
Selections, top bar and Dock.|Selecciones, barra superior y Dock.|选中项、顶栏和程序坞。|Seleções, barra superior e Dock.|Auswahl, obere Leiste und Dock.
Icons, selections, top bar and Dock.|Iconos, selecciones, barra superior y Dock.|图标、选中项、顶栏和程序坞。|Ícones, seleções, barra superior e Dock.|Symbole, Auswahl, obere Leiste und Dock.
Everything in its place.|Todo en su lugar.|一切井然有序。|Tudo em seu lugar.|Alles an seinem Platz.
Color|Color|颜色|Cor|Farbe
Background|Fondo|壁纸|Fundo|Hintergrund
Boot|Arranque|启动|Inicialização|Systemstart
Included with the theme|Incluido con el tema|主题包含|Incluído com o tema|Im Thema enthalten
Global menu, window theme, cursors, sounds, Qt and GTK styles and file dialogs.|Menú global, tema de ventanas, cursores, sonidos, estilos Qt y GTK y diálogos de archivos.|全局菜单、窗口主题、光标、声音、Qt 和 GTK 样式及文件对话框。|Menu global, tema de janelas, cursores, sons, estilos Qt e GTK e diálogos de arquivos.|Globales Menü, Fensterthema, Mauszeiger, Klänge, Qt- und GTK-Stile und Dateidialoge.
Cancel|Cancelar|取消|Cancelar|Abbrechen
The following theme components will be removed:|Se retirarán los siguientes componentes del tema:|将移除以下主题组件：|Os seguintes componentes do tema serão removidos:|Folgende Komponenten des Themas werden entfernt:
Icons, fonts, sounds and appearance.|Iconos, fuentes, sonidos y apariencia.|图标、字体、声音和外观。|Ícones, fontes, sons e aparência.|Symbole, Schriftarten, Klänge und Erscheinungsbild.
Top bar, Dock and project widgets.|Barra superior, Dock y widgets del proyecto.|顶栏、程序坞和项目组件。|Barra superior, Dock e widgets do projeto.|Obere Leiste, Dock und Projekt-Miniprogramme.
Effects and scheduled tasks.|Efectos y tareas automáticas.|效果和计划任务。|Efeitos e tarefas agendadas.|Effekte und geplante Aufgaben.
Keep|Conservar|保留|Manter|Beibehalten
Custom file|Archivo elegido|所选文件|Arquivo escolhido|Ausgewählte Datei
Desktop|Escritorio|桌面|Área de trabalho|Arbeitsfläche
Effects|Efectos|效果|Efeitos|Effekte
Preparing…|Preparando…|正在准备…|Preparando…|Vorbereitung…
Review the installation details before trying again.|Revisa los detalles de la instalación antes de reintentar.|重试前请查看安装详情。|Revise os detalhes da instalação antes de tentar novamente.|Prüfe vor einem neuen Versuch die Installationsdetails.
Which appearance would you like?|¿Qué apariencia quieres usar?|你想使用哪种外观？|Qual aparência você quer usar?|Welches Erscheinungsbild möchtest du verwenden?
Which icons and color would you like?|¿Qué iconos y color quieres usar?|你想使用哪些图标和颜色？|Quais ícones e cor você quer usar?|Welche Symbole und Farbe möchtest du verwenden?
Which wallpaper would you like?|¿Qué fondo quieres usar?|你想使用哪张壁纸？|Qual papel de parede você quer usar?|Welchen Hintergrund möchtest du verwenden?
Which launcher would you like?|¿Qué launcher quieres usar?|你想使用哪个启动器？|Qual lançador você quer usar?|Welchen Starter möchtest du verwenden?
What would you like to add to your desktop?|¿Qué quieres añadir al escritorio?|你想在桌面上添加什么？|O que você quer adicionar à área de trabalho?|Was möchtest du dem Desktop hinzufügen?
Which effects would you like to enable?|¿Qué efectos quieres activar?|你想启用哪些效果？|Quais efeitos você quer ativar?|Welche Effekte möchtest du aktivieren?
Which fonts would you like to use?|¿Qué fuentes quieres usar?|你想使用哪些字体？|Quais fontes você quer usar?|Welche Schriftarten möchtest du verwenden?
Apply the theme to Firefox?|¿Aplicar el tema a Firefox?|将主题应用到 Firefox？|Aplicar o tema ao Firefox?|Das Thema auf Firefox anwenden?
Which file manager would you like to use?|¿Qué gestor de archivos quieres usar?|你想使用哪个文件管理器？|Qual gerenciador de arquivos você quer usar?|Welchen Dateimanager möchtest du verwenden?
Change the boot animation?|¿Cambiar la animación de arranque?|更改启动动画？|Alterar a animação de inicialização?|Die Startanimation ändern?
Enable OLED protection?|¿Activar la protección para pantallas OLED?|启用 OLED 保护？|Ativar a proteção para telas OLED?|OLED-Schutz aktivieren?
Review your installation|Revisa la instalación|检查安装选项|Revise a instalação|Installation überprüfen
Choose your options and begin installation.|Personaliza las opciones y comienza la instalación.|选择选项并开始安装。|Escolha as opções e inicie a instalação.|Wähle deine Optionen und starte die Installation.
Automatic|Automática|自动|Automática|Automatisch
Light by day, dark at night.|Clara de día, oscura de noche.|白天浅色，夜间深色。|Clara de dia, escura à noite.|Tagsüber hell, nachts dunkel.
Light|Clara|浅色|Clara|Hell
Dark|Oscura|深色|Escura|Dunkel
Regular|Regulares|常规|Regulares|Normal
Light and dark, following your appearance.|Claros y oscuros, según la apariencia.|随外观切换浅色和深色。|Claros e escuros, conforme a aparência.|Hell und dunkel, passend zum Erscheinungsbild.
Glass|Cristal|玻璃|Vidro|Glas
Translucent, with your chosen color.|Translúcidos, con el color que elijas.|半透明，使用所选颜色。|Translúcidos, com a cor escolhida.|Durchscheinend, in deiner gewählten Farbe.
Keep my icons|Conservar mis iconos|保留我的图标|Manter meus ícones|Meine Symbole beibehalten
Theme color|Color del tema|主题颜色|Cor do tema|Themenfarbe
Blue|Azul|蓝色|Azul|Blau
Purple|Violeta|紫色|Roxo|Violett
Pink|Rosa|粉色|Rosa|Rosa
Red|Rojo|红色|Vermelho|Rot
Orange|Naranja|橙色|Laranja|Orange
Yellow|Amarillo|黄色|Amarelo|Gelb
Green|Verde|绿色|Verde|Grün
Gray|Grafito|石墨色|Grafite|Graphit
Landscape|Paisaje|风景|Paisagem|Landschaft
Keep my wallpaper|Conservar mi fondo|保留我的壁纸|Manter meu papel de parede|Meinen Hintergrund beibehalten
Choose a file…|Elegir archivo…|选择文件…|Escolher arquivo…|Datei auswählen…
Choose a wallpaper|Elegir un fondo de pantalla|选择壁纸|Escolher um papel de parede|Hintergrund auswählen
Categories and apps in one window.|Categorías y aplicaciones en una ventana.|分类和应用位于同一窗口。|Categorias e aplicativos em uma janela.|Kategorien und Apps in einem Fenster.
Separate search and application grid.|Búsqueda separada y cuadrícula de aplicaciones.|独立搜索栏和应用网格。|Busca separada e grade de aplicativos.|Separate Suche und App-Raster.
Top bar|Barra superior|顶栏|Barra superior|Obere Leiste
Global menu, clock and system controls.|Menú global, reloj y controles del sistema.|全局菜单、时钟和系统控件。|Menu global, relógio e controles do sistema.|Globales Menü, Uhr und Systemsteuerung.
Pinned apps and open windows.|Aplicaciones fijadas y ventanas abiertas.|固定的应用和打开的窗口。|Aplicativos fixados e janelas abertas.|Angeheftete Apps und offene Fenster.
Transparency and blur|Transparencia y desenfoque|透明和模糊|Transparência e desfoque|Transparenz und Unschärfe
Panels, menus and windows.|En paneles, menús y ventanas.|应用于面板、菜单和窗口。|Em painéis, menus e janelas.|Für Leisten, Menüs und Fenster.
Rounded corners|Esquinas redondeadas|圆角|Cantos arredondados|Abgerundete Ecken
Preserves your radius settings.|Se conserva tu ajuste de redondeo.|保留你的圆角半径设置。|Mantém seu ajuste de arredondamento.|Deine Radiuseinstellungen bleiben erhalten.
Theme fonts|Fuentes del tema|主题字体|Fontes do tema|Schriftarten des Themas
Keep my fonts|Conservar mis fuentes|保留我的字体|Manter minhas fontes|Meine Schriftarten beibehalten
Keep the current typography.|Mantener la tipografía actual.|保留当前字体。|Manter a tipografia atual.|Aktuelle Schriftarten beibehalten.
Your files.|Tus archivos.|你的文件。|Seus arquivos.|Deine Dateien.
Documents, photos and ideas.|Documentos, fotos e ideas.|文档、照片和创意。|Documentos, fotos e ideias.|Dokumente, Fotos und Ideen.
Apply the theme|Aplicar el tema|应用主题|Aplicar o tema|Thema anwenden
Keep Firefox as it is|Conservar Firefox como está|保持 Firefox 原样|Manter o Firefox como está|Firefox unverändert lassen
Recommended · Files theme|Recomendado · Estilo Files del tema|推荐 · Files 风格|Recomendado · Estilo Files do tema|Empfohlen · Files-Stil des Themas
KDE file manager|Gestor de archivos de KDE|KDE 文件管理器|Gerenciador de arquivos do KDE|Dateimanager von KDE
Add folder shortcuts to the sidebar|Añadir accesos a mis carpetas en la barra lateral|在侧栏中添加文件夹快捷方式|Adicionar atalhos de pastas à barra lateral|Ordnerverknüpfungen zur Seitenleiste hinzufügen
Use the theme animation|Usar la animación del tema|使用主题动画|Usar a animação do tema|Animation des Themas verwenden
Keep my boot animation|Conservar mi animación|保留我的启动动画|Manter minha animação|Meine Startanimation beibehalten
Do not enable|No activar|不启用|Não ativar|Nicht aktivieren
Enable pixel shifting|Activar desplazamiento de píxeles|启用像素偏移|Ativar deslocamento de pixels|Pixelverschiebung aktivieren
Interval (minutes)|Intervalo (minutos)|间隔（分钟）|Intervalo (minutos)|Intervall (Minuten)
Maximum shift (pixels)|Desplazamiento máximo (píxeles)|最大偏移（像素）|Deslocamento máximo (pixels)|Maximale Verschiebung (Pixel)
Change|Cambiar|更改|Alterar|Ändern
Included: global menu, window theme, cursors, sounds, Qt and GTK styles and file dialogs.|Incluido: menú global, tema de ventanas, cursores, sonidos, estilos Qt y GTK y diálogos de archivos.|包含全局菜单、窗口主题、光标、声音、Qt 和 GTK 样式及文件对话框。|Incluído: menu global, tema de janelas, cursores, sons, estilos Qt e GTK e diálogos de arquivos.|Enthalten: globales Menü, Fensterthema, Mauszeiger, Klänge, Qt- und GTK-Stile und Dateidialoge.
The theme is applied immediately when installation finishes.|El tema se aplicará inmediatamente al terminar.|安装完成后立即应用主题。|O tema será aplicado imediatamente ao terminar.|Das Thema wird nach der Installation sofort angewendet.
Installing…|Instalando…|正在安装…|Instalando…|Installation läuft…
Uninstalling…|Desinstalando…|正在卸载…|Desinstalando…|Deinstallation läuft…
Installation details|Detalles de la instalación|安装详情|Detalhes da instalação|Installationsdetails
Installation complete|Instalación terminada|安装完成|Instalação concluída|Installation abgeschlossen
The theme is now applied. You can close the installer.|El tema ya está aplicado. Puedes cerrar el instalador.|主题已应用。你可以关闭安装程序。|O tema já foi aplicado. Você pode fechar o instalador.|Das Thema ist angewendet. Du kannst das Installationsprogramm schließen.
Uninstallation complete|Desinstalación terminada|卸载完成|Desinstalação concluída|Deinstallation abgeschlossen
The theme components have been removed.|Se han retirado los componentes del tema.|主题组件已移除。|Os componentes do tema foram removidos.|Die Komponenten des Themas wurden entfernt.
The theme's icons, fonts, sounds, appearance, panels, effects and scheduled tasks will be removed.|Se retirarán los iconos, fuentes, sonidos, apariencia, paneles, efectos y tareas automáticas del tema.|将移除主题的图标、字体、声音、外观、面板、效果和计划任务。|Os ícones, fontes, sons, aparência, painéis, efeitos e tarefas agendadas do tema serão removidos.|Symbole, Schriftarten, Klänge, Erscheinungsbild, Leisten, Effekte und geplante Aufgaben des Themas werden entfernt.
The desktop will return to Breeze. Previous settings are restored where a backup exists.|El escritorio volverá a Breeze. Se restaurarán los ajustes anteriores cuando exista una copia.|桌面将恢复为 Breeze。有备份的设置将恢复。|A área de trabalho voltará ao Breeze. As configurações anteriores serão restauradas quando houver backup.|Der Desktop kehrt zu Breeze zurück. Gesicherte Einstellungen werden wiederhergestellt.
Your documents and personal applications are kept.|Tus documentos y aplicaciones personales se conservan.|你的文档和个人应用将被保留。|Seus documentos e aplicativos pessoais serão mantidos.|Deine Dokumente und persönlichen Anwendungen bleiben erhalten.
The operation could not be completed|No se pudo completar la operación|无法完成操作|Não foi possível concluir a operação|Der Vorgang konnte nicht abgeschlossen werden
Next|Siguiente|下一步|Avançar|Weiter
Back|Atrás|返回|Voltar|Zurück
Retry|Reintentar|重试|Tentar novamente|Erneut versuchen
Save|Guardar|保存|Salvar|Speichern
Step|Paso|步骤|Etapa|Schritt
Appearance|Apariencia|外观|Aparência|Erscheinungsbild
Icons|Iconos|图标|Ícones|Symbole
Wallpaper|Fondo de pantalla|壁纸|Papel de parede|Hintergrund
Launcher|Launcher|启动器|Lançador|Starter
Fonts|Fuentes|字体|Fontes|Schriftarten
Files|Archivos|文件|Arquivos|Dateien
Boot animation|Animación de arranque|启动动画|Animação de inicialização|Startanimation
OLED protection|Protección OLED|OLED 保护|Proteção OLED|OLED-Schutz
Enabled|Activado|已启用|Ativado|Aktiviert
Disabled|Desactivado|已禁用|Desativado|Deaktiviert
Auto|Automática|自动|Automática|Automatisch
Custom|Archivo elegido|所选文件|Arquivo escolhido|Gewählte Datei'''

CATALOGS = {code: {} for code in ('es', 'zh_CN', 'pt_BR', 'de')}
for row in _ROWS.splitlines():
    source, *translations = row.split('|')
    if len(translations) != len(CATALOGS):
        raise ValueError('Incomplete wizard translation: ' + source)
    for code, text in zip(CATALOGS, translations):
        CATALOGS[code][source] = text


def wizard_translate(message, language):
    return CATALOGS.get(effective_language(language), {}).get(message, translate(message, language))

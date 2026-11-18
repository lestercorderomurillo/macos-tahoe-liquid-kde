import sys,json,gi
from pathlib import Path
major=sys.argv[2] if len(sys.argv)>2 else '4'
try: gi.require_version('Gtk',major+'.0')
except ValueError: sys.exit(77)
from gi.repository import Gtk,GLib
sys.path.insert(0,str(Path(sys.argv[1])/'src/scripts'))
from theme_accent import recolor
from theme_switch import gtk4_compatible_css
from installer_choices import COLORS
Gtk.init([]) if major=='3' else Gtk.init()
Gtk.Settings.get_default().set_property('gtk-enable-animations',False)
w=Gtk.Window()
if major=='4':
 box=Gtk.Box();box.add_css_class('sidebar-pane');w.set_child(box)
 ls=Gtk.ListBox();ls.add_css_class('navigation-sidebar');box.append(ls)
 label=Gtk.Label(label='Documents');ls.append(label);row=label.get_parent();ls.select_row(row)
else:
 model=Gtk.ListStore(str);model.append(['Documents'])
 row=Gtk.TreeView(model=model);row.append_column(Gtk.TreeViewColumn('Places',Gtk.CellRendererText(),text=0))
 row.get_selection().select_path(Gtk.TreePath.new_first());w.add(row);label=row
 w.show_all()
w.present()
provider=Gtk.CssProvider()
if major=='4': Gtk.StyleContext.add_provider_for_display(w.get_display(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)
else: Gtk.StyleContext.add_provider_for_screen(w.get_screen(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)
def lum(v):
 return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*k for c,k in zip(v,(.2126,.7152,.0722)))

states=(Gtk.StateFlags.NORMAL,Gtk.StateFlags.PRELIGHT,Gtk.StateFlags.FOCUSED,Gtk.StateFlags.BACKDROP)

def selection_colors(css):
 if major=='4': css=gtk4_compatible_css(css)
 provider.load_from_data(css.encode())
 for extra in states:
  state=Gtk.StateFlags.SELECTED|extra
  row.set_state_flags(state,True)
  while GLib.MainContext.default().iteration(False):pass
  context=label.get_style_context()
  if major=='4':
   fg=context.get_color();found,bg=context.lookup_color('accent_bg_color');assert found
  else:
   fg=context.get_color(state);bg=context.get_background_color(state)
  yield (fg.red,fg.green,fg.blue),(bg.red,bg.green,bg.blue)

for mode in ('Light','Dark','Light'):
 source=(Path(sys.argv[1])/f'src/offline/gtk/MacTahoeLiquidKde-{mode}/gtk-{major}.0/gtk.css').read_text()
 bundled=list(selection_colors(source))
 for name,color in COLORS.items():
  actual=selection_colors(recolor(source,color))
  for extra,(foreground,background),(bundled_foreground,_) in zip(states,actual,bundled):
   if name=='gray':
    darker,lighter=sorted((lum(foreground),lum(background)))
    assert (lighter+.05)/(darker+.05)>=4.5,(mode,name,int(extra),foreground,background)
   else:
    assert foreground==bundled_foreground,(mode,name,int(extra),foreground,bundled_foreground)
print('GTK_ACCENT_STATES_OK: 8 accents, light/dark/light, selected/hover/focus/backdrop')
w.destroy()

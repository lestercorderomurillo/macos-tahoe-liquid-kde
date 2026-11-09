#include <systemmenustyle.h>
#include <QMenu>
#include <QImage>
#include <QKeyEvent>
#include <QIconEngine>
#include <cassert>
class NamedIcon : public QIconEngine {
 QString m_name;
public:
 explicit NamedIcon(QString name):m_name(name){}
 QIconEngine* clone() const override {return new NamedIcon(m_name);}
 QString iconName() override {return m_name;}
 void paint(QPainter* p,const QRect& r,QIcon::Mode,QIcon::State) override {p->fillRect(r,Qt::magenta);}
};
int main(int argc, char** argv) {
 QApplication app(argc, argv);
 QStyle* original = app.style();
 for (int points : {10, 18}) {
  QMenu menu;
  QFont font=app.font("QMenu"); font.setPointSize(points); menu.setFont(font);
  menu.setStyle(new SystemMenuStyle(&menu));
  auto* first=menu.addAction("About This Computer");
  menu.addSeparator();
  auto* second=menu.addAction("System Settings…");
  menu.addAction("App Store…");
  menu.addSeparator();
  menu.addAction("Force Quit…");
  menu.addAction("Sleep");
  menu.addAction("Restart…");
  menu.addAction("Shut Down…");
  auto* lock = menu.addAction("Lock Screen");
  lock->setShortcut(QKeySequence(Qt::CTRL | Qt::META | Qt::Key_Q));
  auto* logout = menu.addAction("Log Out A Much Longer User Name…");
  logout->setShortcut(QKeySequence(Qt::SHIFT | Qt::META | Qt::Key_Q));
  menu.adjustSize();
  const qreal scale=SystemMenuStyle::scaleFor(font,&menu);
  const qreal required=QFontMetricsF(font).horizontalAdvance(logout->text())
      +QFontMetricsF(font).horizontalAdvance(QStringLiteral("⇧⌘Q"))+48*scale;
  assert(menu.actionGeometry(logout).width()>=qCeil(required));
  if (menu.actionGeometry(first).left()==menu.actionGeometry(logout).left())
   assert(menu.sizeHint().width()<qCeil(required+50*scale));
  assert(menu.actionGeometry(first).height()==qRound(24*scale));
  assert(menu.actionGeometry(first).height()==menu.actionGeometry(second).height());
  assert(menu.sizeHint().width()>=qRound(280*scale));
  assert(menu.actionGeometry(menu.actions().at(1)).height()==qRound(12*scale));
  QStyleOptionMenuItem option;
  option.initFrom(&menu); option.font=font;
  option.menuItemType=QStyleOptionMenuItem::Normal;
  option.state=QStyle::State_Enabled|QStyle::State_Selected;
  option.rect=QRect(0,0,268*scale,24*scale);
  QImage image(option.rect.size(),QImage::Format_ARGB32_Premultiplied); image.fill(Qt::transparent);
  QPainter painter(&image); menu.style()->drawControl(QStyle::CE_MenuItem,&option,&painter,&menu); painter.end();
  assert(image.pixelColor(0,0).alpha()==0);
  assert(image.pixelColor(qRound(7*scale),0).alpha()>240);
  assert(image.pixelColor(0,image.height()/2).alpha()>240);
  for (const QString& name : {QStringLiteral("computer"), QStringLiteral("preferences-system"),
                              QStringLiteral("software-store-symbolic"), QStringLiteral("custom-icon")}) {
   option.icon=QIcon(new NamedIcon(name));
   option.state=QStyle::State_Enabled;
   image.fill(Qt::transparent);
   QPainter iconPainter(&image);
   menu.style()->drawControl(QStyle::CE_MenuItem,&option,&iconPainter,&menu);
   iconPainter.end();
   int opaque=0,magenta=0;
   for(int y=0;y<image.height();++y)for(int x=0;x<image.width();++x){
    QColor pixel=image.pixelColor(x,y);
    if(pixel.alpha()>0)++opaque;
    if(pixel==QColor(Qt::magenta))++magenta;
   }
   assert(opaque>0);
   assert((name==QStringLiteral("custom-icon"))==(magenta>0));
  }
  for (const auto direction : {Qt::LeftToRight, Qt::RightToLeft}) {
   option.direction=direction;
   option.icon=QIcon();
   option.text=QStringLiteral("Log Out A Much Longer User Name…\tMeta+Shift+Q");
   option.rect.setWidth(menu.style()->sizeFromContents(QStyle::CT_MenuItem,&option,{},nullptr).width());
   const auto labelWidth=QFontMetricsF(font).horizontalAdvance(option.text.section('\t',0,0));
   const auto hintWidth=QFontMetricsF(font).horizontalAdvance(QStringLiteral("⇧⌘Q"));
   assert(option.rect.width()>=qCeil(labelWidth+hintWidth+48*scale));
   QImage row(option.rect.size(),QImage::Format_ARGB32_Premultiplied); row.fill(Qt::transparent);
   QPainter p(&row);menu.style()->drawControl(QStyle::CE_MenuItem,&option,&p,&menu);p.end();
   const int edge=qRound(12*scale);
   const int start=direction==Qt::LeftToRight?row.width()-edge-qCeil(hintWidth):edge;
   int pixels=0;
   for(int x=start;x<start+qCeil(hintWidth);++x)for(int y=0;y<row.height();++y)
    if(row.pixelColor(x,y).alpha()>0)++pixels;
   assert(pixels>0);
  }
  assert(SystemMenuStyle::shortcutSymbols(QStringLiteral("Meta+Ctrl+Q"))==QStringLiteral("⌃⌘Q"));
  assert(SystemMenuStyle::shortcutSymbols(QStringLiteral("Meta+Shift+Q"))==QStringLiteral("⇧⌘Q"));
  assert(SystemMenuStyle::shortcutSymbols(QStringLiteral("Alt+F4"))==QStringLiteral("Alt+F4"));
  menu.show();
  menu.setActiveAction(first);
  QKeyEvent down(QEvent::KeyPress, Qt::Key_Down, Qt::NoModifier);
  QApplication::sendEvent(&menu, &down);
  assert(menu.activeAction()==second);
  QKeyEvent escape(QEvent::KeyPress, Qt::Key_Escape, Qt::NoModifier);
  QApplication::sendEvent(&menu, &escape);
  assert(!menu.isVisible());
  assert(app.style()==original);
 }
 QMenu unaffected; assert(unaffected.style()==original);
}

#include <systemmenustyle.h>
#include <QMenu>
#include <QImage>
#include <QKeyEvent>
#include <QIconEngine>
#include <cassert>
#include <QProxyStyle>
#include <QPointer>
class NamedIcon : public QIconEngine {
 QString m_name;
public:
 explicit NamedIcon(QString name):m_name(name){}
 QIconEngine* clone() const override {return new NamedIcon(m_name);}
 QString iconName() override {return m_name;}
 void paint(QPainter* p,const QRect& r,QIcon::Mode,QIcon::State) override {p->fillRect(r,Qt::magenta);}
};
// A plugin surface is independent of the palette, like Kvantum's SVG fill.
class SurfaceStyle : public QProxyStyle {
 QColor surface;
public:
 explicit SurfaceStyle(QColor color):QProxyStyle("Fusion"),surface(color){}
 void drawPrimitive(PrimitiveElement element,const QStyleOption* option,QPainter* painter,
                    const QWidget* widget=nullptr) const override {
  if(element==PE_PanelMenu){painter->fillRect(option->rect,surface);return;}
  QProxyStyle::drawPrimitive(element,option,painter,widget);
 }
};
static QImage surface(QMenu& menu) {
 QStyleOption option;option.initFrom(&menu);option.rect=QRect(0,0,120,80);
 QImage image(option.rect.size(),QImage::Format_ARGB32_Premultiplied);image.fill(Qt::transparent);
 QPainter painter(&image);menu.style()->drawPrimitive(QStyle::PE_PanelMenu,&option,&painter,&menu);
 return image;
}
static void liveStyleCycle() {
 QMenu system,ordinary;
 system.setStyle(new SystemMenuStyle(&system));
 auto* scoped=system.style();
 // Reuse the same menu/style across light -> dark -> light, with unchanged
 // palettes, so a palette-only fix or an independently cached style fails.
 for(const QColor color : {QColor(230,230,230),QColor(18,18,18),QColor(230,230,230)}) {
  QPointer<QStyle> previous=QApplication::style();
  QApplication::setStyle(new SurfaceStyle(color));
  QApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
  assert(previous.isNull());
  assert(system.style()==scoped);
  assert(ordinary.style()==QApplication::style());
  assert(surface(system)==surface(ordinary));
  assert(surface(system).pixelColor(60,40)==color);
 }
 QPointer<QStyle> live=QApplication::style();
 // Destroying the scoped style must never destroy the shared desktop style.
 system.setStyle(nullptr);delete scoped;
 assert(!live.isNull());
}
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
                              QStringLiteral("software-store-symbolic"), QStringLiteral("dialog-cancel"),
                              QStringLiteral("system-suspend"), QStringLiteral("system-reboot"),
                              QStringLiteral("system-shutdown"), QStringLiteral("system-lock-screen"),
                              QStringLiteral("user-identity"), QStringLiteral("custom-icon")}) {
   option.icon=QIcon(new NamedIcon(name));
   option.state=QStyle::State_Enabled;
   image=QImage(option.rect.size()*4,QImage::Format_ARGB32_Premultiplied);
   image.setDevicePixelRatio(4);
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
   if (name==QStringLiteral("preferences-system") || name==QStringLiteral("system-suspend")) {
    const int size=qRound(16*scale);
    const QPoint origin(qRound(12*scale),qRound(QRectF(option.rect).center().y()-size/2.0));
    auto alpha = [&](qreal x,qreal y) {
     return image.pixelColor(qRound((origin.x()+x*size/16)*4),
                             qRound((origin.y()+y*size/16)*4)).alpha();
    };
    if (name==QStringLiteral("system-suspend")) {
     // Apple's Sleep symbol has a low bar, rather than a centered minus.
     assert(alpha(8,8)<80);
     int lowBar=0;
     for (qreal y=9.5;y<=12;y+=0.25) lowBar=std::max(lowBar,alpha(8,y));
     assert(lowBar>100);
     continue;
    }
    // Actual glyph pixels: three spokes, three open sectors and a hollow hub.
    // The old hollow gear cannot satisfy the spoke checks.
    for (int spoke=0;spoke<3;++spoke) {
     const qreal angle=spoke*2*M_PI/3;
     assert(alpha(8+2.4*std::cos(angle),8+2.4*std::sin(angle))>100);
     const qreal gap=angle+M_PI/3;
     assert(alpha(8+2.8*std::cos(gap),8+2.8*std::sin(gap))<80);
    }
    assert(alpha(8,8)<100);
   }
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
 liveStyleCycle();
}

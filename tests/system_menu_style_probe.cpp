#include <systemmenustyle.h>
#include <QMenu>
#include <QImage>
#include <QKeyEvent>
#include <cassert>
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
  menu.addAction("Lock Screen");
  menu.addAction("Log Out A Much Longer User Name…");
  menu.adjustSize();
  const qreal scale=SystemMenuStyle::scaleFor(font,&menu);
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

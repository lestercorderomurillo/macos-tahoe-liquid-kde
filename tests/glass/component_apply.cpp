// SPDX-License-Identifier: GPL-3.0-or-later
#include <KCModule>
#include <KPluginFactory>
#include <KPluginMetaData>
#include <QApplication>
#include <QCheckBox>
#include <QComboBox>
#include <QDoubleSpinBox>
#include <QSpinBox>
#include <QJsonDocument>
#include <QJsonObject>
#include <QFile>
#include <QLabel>
#include <QClipboard>
#include <QPushButton>
#include <cstdio>
int main(int argc,char **argv){
 QApplication app(argc,argv);app.clipboard()->setText(QString());
 if(argc<3)return 2;
 auto result=KPluginFactory::instantiatePlugin<KCModule>(KPluginMetaData(QString::fromLocal8Bit(argv[1])));
 if(!result){fprintf(stderr,"%s\n",qPrintable(result.errorString));return 3;}
 auto *m=result.plugin;m->load();
 QFile file(QString::fromLocal8Bit(argv[2]));if(!file.open(QIODevice::ReadOnly))return 4;
 auto request=QJsonDocument::fromJson(file.readAll()).object();
 if(request.contains("preset")){
  auto *presets=m->widget()->findChild<QComboBox*>("kcfg_MaterialPreset");
  const int row=request.value("preset").toInt();
  if(!presets || row<0 || row>=presets->count()) return 8;
  presets->setCurrentIndex(row);presets->activated(row);
 }
 if(request.value("restore").toBool()){
  auto *restore=m->widget()->findChild<QPushButton*>("resetPreset");
  if(!restore)return 9;restore->click();
 }
 auto *selector=m->widget()->findChild<QComboBox*>(QStringLiteral("componentSelector"));
 const int index=selector->findData(request.value(QStringLiteral("component")).toString());
 if(index<0)return 5;selector->setCurrentIndex(index);
 const auto values=request.value(QStringLiteral("values")).toObject();
 for(auto i=values.begin();i!=values.end();++i){
  auto *w=m->widget()->findChild<QWidget*>(QStringLiteral("kcfg_")+i.key());
  if(auto *n=qobject_cast<QDoubleSpinBox*>(w))n->setValue(i.value().toDouble());
  else if(auto *n=qobject_cast<QSpinBox*>(w))n->setValue(i.value().toInt());
  else if(auto *b=qobject_cast<QCheckBox*>(w))b->setChecked(i.value().toBool());
  else return 6;
 }
 if(!request.contains("save") || request.value("save").toBool())m->save();
 auto *error=m->widget()->findChild<QLabel*>(QStringLiteral("applyError"));
 if(!error->isHidden()){fprintf(stderr,"%s\n",qPrintable(error->text()));return 7;}
 if(argc==4){m->widget()->resize(620,760);m->widget()->show();app.processEvents();m->widget()->grab().save(QString::fromLocal8Bit(argv[3]));}
 QJsonObject observed;
 for(const auto &name : {"BlurStrength", "MagnifyGlassStrength", "BlurCoverage", "SurfaceTransparencyLight", "SurfaceTransparencyDark", "DarkGradientOverlay"}){
  auto *w=m->widget()->findChild<QWidget*>(QStringLiteral("kcfg_")+QString::fromLatin1(name));
  if(auto *n=qobject_cast<QDoubleSpinBox*>(w))observed.insert(name,n->value());
  else if(auto *n=qobject_cast<QSpinBox*>(w))observed.insert(name,n->value());
  else if(auto *b=qobject_cast<QCheckBox*>(w))observed.insert(name,b->isChecked());
  else return 10;
 }
 puts(QJsonDocument(observed).toJson(QJsonDocument::Compact).constData());
 delete m;return 0;
}

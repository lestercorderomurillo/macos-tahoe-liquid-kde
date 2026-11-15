# SPDX-License-Identifier: GPL-3.0-or-later
import sys
from PyQt6.QtWidgets import QApplication,QWidget
from PyQt6.QtCore import QTimer,QMimeData
from PyQt6.QtGui import QImage,QColor
app=QApplication([]);w=QWidget();w.setWindowTitle('Clipboard producer');w.show()
def copy():
    if sys.argv[1]=='image':
        img=QImage(200,120,QImage.Format.Format_RGB32);img.fill(QColor('#4488cc'));app.clipboard().setImage(img)
    elif sys.argv[1]=='secret':
        md=QMimeData();md.setText('DO-NOT-RECORD');md.setData('x-kde-passwordManagerHint',b'secret');app.clipboard().setMimeData(md)
    else: app.clipboard().setText('Clipboard qualification text')
QTimer.singleShot(1200,copy);QTimer.singleShot(60000,app.quit);app.exec()

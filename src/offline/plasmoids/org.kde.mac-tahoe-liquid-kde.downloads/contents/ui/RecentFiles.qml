// SPDX-License-Identifier: GPL-3.0-only
import QtQuick
import QtCore
import Qt.labs.folderlistmodel

FolderListModel {
    id: files
    folder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
    showDirs: false
    showHidden: false
    showDotAndDotDot: false
    showOnlyReadable: true
    sortField: FolderListModel.Time
    sortReversed: false

    property int limit: 7
    property bool frozen: false
    property var entries: []

    function refresh() {
        if (frozen)
            return;
        const result = [];
        for (let row = 0; row < count && result.length < limit; row++) {
            const name = get(row, "fileName");
            // Browsers and download managers rename these when complete.
            if (/\.(part|crdownload|download|tmp)$/i.test(name))
                continue;
            result.push({name: name, url: get(row, "fileUrl").toString()});
        }
        entries = result;
    }

    onCountChanged: Qt.callLater(refresh)
    onStatusChanged: Qt.callLater(refresh)
    onLimitChanged: Qt.callLater(refresh)
    onFrozenChanged: Qt.callLater(refresh)
    Component.onCompleted: Qt.callLater(refresh)

    property Connections updates: Connections {
        target: files
        function onDataChanged() { Qt.callLater(files.refresh); }
        function onModelReset() { Qt.callLater(files.refresh); }
        function onRowsInserted() { Qt.callLater(files.refresh); }
        function onRowsRemoved() { Qt.callLater(files.refresh); }
        function onRowsMoved() { Qt.callLater(files.refresh); }
    }
}

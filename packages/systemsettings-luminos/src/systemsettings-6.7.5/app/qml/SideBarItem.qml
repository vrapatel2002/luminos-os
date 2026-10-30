/*
   SPDX-FileCopyrightText: 2017 Marco Martin <mart@kde.org>
   SPDX-FileCopyrightText: 2023 ivan tkachenko <me@ratijas.tk>

   SPDX-License-Identifier: LGPL-2.0-only
*/

import QtQuick 2.15

import org.kde.kirigami 2.20 as Kirigami

Kirigami.ApplicationItem {
    id: root

    // [CHANGE: claude-code | 2026-10-12] Luminos: mock nav width; a narrow window collapses it to icon tiles
    // Phase 5: one column only; a category's sub-pages replace the main list (which moves to the left drawer)
    implicitWidth: systemsettings.width < 860 ? 72 : 330 + 32
    wideScreen: false

    pageStack.initialPage: mainColumn
    pageStack.separatorVisible: false // [CHANGE: claude-code | 2026-10-12] Luminos: the hole's gap divides
    pageStack.defaultColumnWidth: root.width

    property alias searchMode: mainColumn.searchMode
    readonly property real headerHeight: mainColumn.header.height

    CategoriesPage {
        id: mainColumn
        focus: true
    }

    SubCategoryPage {
        id: subCategoryColumn
        enabled: pageStack.visibleItems.includes(subCategoryColumn)
    }
}

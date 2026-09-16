"""DICOMProvenance -- additive-only notes and result/edit provenance tracking
for a Slicer DICOM database, plus an on-demand lineage graph popup.

See DICOMProvenanceLib/core.py for the actual DICOM object construction and
the small local provenance.sqlite index. Everything in this module and its
lib folder resolves paths relative to its own location -- the whole
containing folder is meant to be movable without editing anything.
"""

import os

import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleWidget,
)

from DICOMProvenanceLib import core


class DICOMProvenance(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        parent.title = "DICOM Provenance"
        parent.categories = ["Informatics"]
        parent.dependencies = []
        parent.contributors = ["Ron Kikinis lab"]
        parent.helpText = (
            "Attach structured notes to DICOM studies/series, record segmentation "
            "results and manual edits with provenance (tool, version, task, parent, "
            "author), and view the resulting lineage graph -- all additive, never "
            "modifying existing DICOM data."
        )
        parent.acknowledgementText = "Local lab tool."


class DICOMProvenanceLogic(ScriptedLoadableModuleLogic):
    """Thin pass-through to DICOMProvenanceLib.core, kept separate so the
    widget stays UI-only and the core logic stays independently scriptable."""

    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)

    def searchSeries(self, text):
        return core.search_series(text)

    def ensureDatabaseOpen(self):
        return core.ensure_database_open()

    def isUsingColocatedDatabase(self):
        return core.is_using_colocated_database()

    def defaultDatabaseDir(self):
        return core.default_database_dir()

    def getAuthor(self):
        return core.get_author()

    def setAuthor(self, name):
        return core.set_author(name)

    def attachNote(self, seriesUID, categoryCode, categoryMeaning, freeText=None):
        return core.create_note_sr(seriesUID, categoryCode, categoryMeaning, freeText)

    def recordResult(self, segmentationNode, parentSeriesUID, kind, label, detail,
                      task=None, tool=None, version=None, segmentAlgorithmType="AUTOMATIC"):
        return core.export_seg_with_provenance(
            segmentationNode, parentSeriesUID, kind, label, detail,
            task=task, tool=tool, version=version, segmentAlgorithmType=segmentAlgorithmType,
        )

    def nextEditNumber(self, parentSeriesUID):
        return core.next_edit_number(parentSeriesUID)

    def getLineage(self, seriesUID):
        return core.get_lineage(seriesUID)


_KIND_COLORS = {
    "algorithm": qt.QColor(120, 170, 230),
    "edit": qt.QColor(230, 190, 110),
    "validation": qt.QColor(150, 210, 150),
    "note": qt.QColor(210, 150, 210),
    "root": qt.QColor(200, 200, 200),
}


class LineageGraphDialog(qt.QDialog):
    """Compact, precomputed lineage viewer: a hand-drawn tree of small boxes
    (color-coded by kind) connected by lines. No external graph-drawing
    dependency -- lineages here are small by design."""

    NODE_W = 190
    NODE_H = 46
    X_GAP = 24
    Y_GAP = 46

    def __init__(self, lineage, focusSeriesUID, parent=None):
        qt.QDialog.__init__(self, parent)
        self.setWindowTitle("Lineage")
        self.resize(720, 480)
        layout = qt.QVBoxLayout(self)

        self.scene = qt.QGraphicsScene(self)
        self.view = qt.QGraphicsView(self.scene, self)
        self.view.setRenderHint(qt.QPainter.Antialiasing)
        layout.addWidget(self.view)

        closeButton = qt.QPushButton("Close")
        closeButton.clicked.connect(self.accept)
        layout.addWidget(closeButton)

        self._build(lineage, focusSeriesUID)

    def _addNode(self, x, y, label, kind, subtitle=None):
        color = _KIND_COLORS.get(kind, qt.QColor(210, 210, 210))
        rect = self.scene.addRect(x, y, self.NODE_W, self.NODE_H,
                                   qt.QPen(qt.QColor(60, 60, 60)), qt.QBrush(color))
        text = label if len(label) <= 30 else label[:27] + "..."
        item = self.scene.addText(text)
        font = item.font()
        font.setPointSize(9)
        item.setFont(font)
        item.setPos(x + 6, y + 4)
        if subtitle:
            sub = self.scene.addText(subtitle)
            f2 = sub.font()
            f2.setPointSize(7)
            sub.setFont(f2)
            sub.setDefaultTextColor(qt.QColor(70, 70, 70))
            sub.setPos(x + 6, y + self.NODE_H - 18)
        return rect

    def _addEdge(self, x1, y1, x2, y2):
        self.scene.addLine(x1, y1, x2, y2, qt.QPen(qt.QColor(120, 120, 120), 1.5))

    def _subtreeWidth(self, node):
        children = node.get("children", [])
        if not children:
            return self.NODE_W
        return sum(self._subtreeWidth(c) + self.X_GAP for c in children) - self.X_GAP

    def _layoutDescendants(self, node, x, y):
        """Draw node's children below (x, y), returns the subtree's horizontal extent."""
        children = node.get("children", [])
        width = self._subtreeWidth(node)
        cx = x + width / 2 - self.NODE_W / 2
        cursor = x
        for child in children:
            cw = self._subtreeWidth(child)
            childX = cursor + cw / 2 - self.NODE_W / 2
            childY = y + self.NODE_H + self.Y_GAP
            self._addEdge(cx + self.NODE_W / 2, y + self.NODE_H,
                          childX + self.NODE_W / 2, childY)
            self._addNode(childX, childY, child["label"], child["kind"],
                          subtitle=self._subtitle(child))
            self._layoutDescendants(child, cursor, childY)
            cursor += cw + self.X_GAP
        return width

    def _subtitle(self, entry):
        bits = []
        if entry.get("author"):
            bits.append(entry["author"])
        if entry.get("created_at"):
            bits.append(entry["created_at"][:10])
        return " · ".join(bits)

    def _rootLabel(self, seriesUID):
        try:
            return core.series_label(seriesUID)
        except Exception:
            return seriesUID[:24] + "..."

    def _build(self, lineage, focusSeriesUID):
        # core.get_lineage()'s "ancestors" is oldest-first and its LAST entry is
        # the focus series' own provenance record (empty if the focus series is an
        # original acquisition with no record of its own).
        chain = lineage.get("ancestors", [])
        descendants = lineage.get("descendants", [])

        x0 = 20
        y = 20
        prevBottomY = None
        focusY = y

        # The original acquired series has no row in the provenance index, so it
        # is named from the DICOM database and drawn above the oldest record.
        if chain:
            rootUID = chain[0].get("parent_series_uid")
            if rootUID:
                self._addNode(x0, y, self._rootLabel(rootUID), "root")
                prevBottomY = y + self.NODE_H
                y += self.NODE_H + self.Y_GAP

        for entry in chain:
            isFocus = entry["series_uid"] == focusSeriesUID
            label = ("▶ " if isFocus else "") + entry["label"]
            self._addNode(x0, y, label, entry["kind"], subtitle=self._subtitle(entry))
            if prevBottomY is not None:
                self._addEdge(x0 + self.NODE_W / 2, prevBottomY, x0 + self.NODE_W / 2, y)
            prevBottomY = y + self.NODE_H
            focusY = y
            y += self.NODE_H + self.Y_GAP

        if not chain:
            # Focus series has no provenance record of its own.
            self._addNode(x0, focusY, "▶ " + self._rootLabel(focusSeriesUID), "root")

        self._layoutDescendants({"children": descendants}, x0, focusY)

        rect = self.scene.itemsBoundingRect()
        self.scene.setSceneRect(rect.adjusted(-20, -20, 20, 20))


class DICOMProvenanceWidget(ScriptedLoadableModuleWidget):
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        self.logic = DICOMProvenanceLogic()

        # --- Database status -------------------------------------------------
        dbBox = ctk.ctkCollapsibleButton()
        dbBox.text = "Database"
        dbBox.collapsed = False
        self.layout.addWidget(dbBox)
        dbForm = qt.QFormLayout(dbBox)
        self.dbStatusLabel = qt.QLabel()
        dbForm.addRow("Status:", self.dbStatusLabel)
        useDbButton = qt.QPushButton("Use this folder's SlicerDICOMDatabase")
        useDbButton.setToolTip(self.logic.defaultDatabaseDir())
        useDbButton.clicked.connect(self.onUseDatabase)
        dbForm.addRow(useDbButton)
        self._refreshDbStatus()

        # --- Series picker (shared by all actions below) ---------------------
        pickerBox = ctk.ctkCollapsibleButton()
        pickerBox.text = "Series"
        pickerBox.collapsed = False
        self.layout.addWidget(pickerBox)
        pickerLayout = qt.QVBoxLayout(pickerBox)
        self.searchEdit = qt.QLineEdit()
        self.searchEdit.setPlaceholderText("Search patient / study / series...")
        self.searchEdit.textChanged.connect(self.onSearchChanged)
        pickerLayout.addWidget(self.searchEdit)
        self.resultsList = qt.QListWidget()
        self.resultsList.setMaximumHeight(160)
        pickerLayout.addWidget(self.resultsList)
        self._seriesRows = []
        self.onSearchChanged("")

        # --- Attach note -------------------------------------------------------
        noteBox = ctk.ctkCollapsibleButton()
        noteBox.text = "Attach note"
        self.layout.addWidget(noteBox)
        noteForm = qt.QFormLayout(noteBox)
        self.categoryCombo = qt.QComboBox()
        for code, meaning in core.NOTE_CATEGORIES:
            self.categoryCombo.addItem(meaning, code)
        self.categoryCombo.currentIndexChanged.connect(self.onCategoryChanged)
        noteForm.addRow("Category:", self.categoryCombo)
        self.noteText = qt.QLineEdit()
        self.noteText.setMaxLength(200)
        self.noteText.setEnabled(False)
        noteForm.addRow("Text (Other only):", self.noteText)
        attachButton = qt.QPushButton("Attach note to selected series")
        attachButton.clicked.connect(self.onAttachNote)
        noteForm.addRow(attachButton)

        # --- Record result -------------------------------------------------------
        resultBox = ctk.ctkCollapsibleButton()
        resultBox.text = "Record result (algorithm / edit / validation)"
        self.layout.addWidget(resultBox)
        resultForm = qt.QFormLayout(resultBox)
        self.segmentationSelector = slicer.qMRMLNodeComboBox()
        self.segmentationSelector.nodeTypes = ["vtkMRMLSegmentationNode"]
        self.segmentationSelector.setMRMLScene(slicer.mrmlScene)
        resultForm.addRow("Segmentation:", self.segmentationSelector)

        self.kindCombo = qt.QComboBox()
        self.kindCombo.addItem("Algorithm result", "algorithm")
        self.kindCombo.addItem("Manual edit", "edit")
        self.kindCombo.addItem("Validation", "validation")
        self.kindCombo.currentIndexChanged.connect(self.onKindChanged)
        resultForm.addRow("Kind:", self.kindCombo)

        self.toolEdit = qt.QLineEdit()
        resultForm.addRow("Tool:", self.toolEdit)
        self.versionEdit = qt.QLineEdit()
        resultForm.addRow("Version:", self.versionEdit)
        self.taskEdit = qt.QLineEdit()
        resultForm.addRow("Task:", self.taskEdit)

        self.reasonCombo = qt.QComboBox()
        for code, meaning in core.EDIT_REASONS:
            self.reasonCombo.addItem(meaning, code)
        resultForm.addRow("Reason:", self.reasonCombo)

        recordButton = qt.QPushButton("Export & Record")
        recordButton.clicked.connect(self.onRecordResult)
        resultForm.addRow(recordButton)
        self.onKindChanged(0)

        # --- Show lineage -------------------------------------------------------
        lineageBox = ctk.ctkCollapsibleButton()
        lineageBox.text = "Show lineage"
        self.layout.addWidget(lineageBox)
        lineageLayout = qt.QVBoxLayout(lineageBox)
        showButton = qt.QPushButton("Show lineage for selected series")
        showButton.clicked.connect(self.onShowLineage)
        lineageLayout.addWidget(showButton)

        self.layout.addStretch(1)

    # -- helpers --------------------------------------------------------------

    def _refreshDbStatus(self):
        ok, message = core.database_status()
        self.dbStatusLabel.text = message
        self.dbStatusLabel.setWordWrap(True)
        return ok

    def onUseDatabase(self):
        try:
            self.logic.ensureDatabaseOpen()
        except Exception as e:
            slicer.util.errorDisplay(f"Could not open this folder's database:\n{e}")
        self._refreshDbStatus()
        # Switching the database invalidates whatever the list was showing, so
        # repopulate it rather than leaving a stale error in place.
        self.onSearchChanged(self.searchEdit.text)

    def onSearchChanged(self, text):
        self.resultsList.clear()
        self._seriesRows = []
        ok, message = core.database_status()
        if not ok:
            self.resultsList.addItem(message)
            return
        try:
            rows = self.logic.searchSeries(text)
        except Exception as e:
            self.resultsList.addItem(f"Could not read the database: {e}")
            return
        if not rows:
            self.resultsList.addItem("(no series match this search)")
            return
        for row in rows:
            patient, patientID, studyDesc, studyDate, seriesDesc, modality, seriesUID, studyUID = row
            label = f"{patient or patientID}  |  {studyDesc or ''} {studyDate or ''}  |  [{modality}] {seriesDesc or ''}"
            self.resultsList.addItem(label)
            self._seriesRows.append({"seriesUID": seriesUID, "studyUID": studyUID, "label": label})

    def _selectedSeries(self):
        row = self.resultsList.currentRow
        if row is None or row < 0 or row >= len(self._seriesRows):
            return None
        return self._seriesRows[row]

    def onCategoryChanged(self, index):
        code = self.categoryCombo.itemData(index)
        self.noteText.setEnabled(code == "OTHER")

    def onKindChanged(self, index):
        kind = self.kindCombo.itemData(index)
        isAlgorithm = kind == "algorithm"
        self.toolEdit.setEnabled(isAlgorithm)
        self.versionEdit.setEnabled(isAlgorithm)
        self.taskEdit.setEnabled(isAlgorithm)
        self.reasonCombo.setEnabled(not isAlgorithm)

    def onAttachNote(self):
        selected = self._selectedSeries()
        if not selected:
            slicer.util.errorDisplay("Select a series first.")
            return
        code = self.categoryCombo.itemData(self.categoryCombo.currentIndex)
        meaning = self.categoryCombo.currentText
        freeText = self.noteText.text if code == "OTHER" else None
        try:
            self.logic.attachNote(selected["seriesUID"], code, meaning, freeText)
            slicer.util.infoDisplay("Note attached.")
            self.onSearchChanged(self.searchEdit.text)
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to attach note: {e}")

    def onRecordResult(self):
        selected = self._selectedSeries()
        if not selected:
            slicer.util.errorDisplay("Select the parent series first.")
            return
        segNode = self.segmentationSelector.currentNode()
        if not segNode:
            slicer.util.errorDisplay("Select a segmentation node first.")
            return

        kind = self.kindCombo.itemData(self.kindCombo.currentIndex)
        author = core.get_author() or core.ensure_author()
        parentSeriesUID = selected["seriesUID"]

        if kind == "algorithm":
            tool = self.toolEdit.text.strip()
            version = self.versionEdit.text.strip()
            task = self.taskEdit.text.strip()
            if not tool:
                slicer.util.errorDisplay("Enter a tool name for an algorithm result.")
                return
            label = f"{tool} {task or ''} {version or ''}".strip()
            detail = f"tool={tool}; version={version}; task={task}"
            segAlgType = "AUTOMATIC"
        else:
            reasonCode = self.reasonCombo.itemData(self.reasonCombo.currentIndex)
            reasonMeaning = self.reasonCombo.currentText
            n = core.next_edit_number(parentSeriesUID)
            who = author or "unknown"
            label = f"{kind}#{n} ({who}) of {selected['label'].split('|')[-1].strip()}"
            detail = f"{kind} round {n} of {parentSeriesUID}; reason={reasonMeaning}; by {who}"
            tool = version = task = None
            segAlgType = "MANUAL"

        try:
            newSeriesUID = self.logic.recordResult(
                segNode, parentSeriesUID, kind, label, detail,
                task=task, tool=tool, version=version, segmentAlgorithmType=segAlgType,
            )
            slicer.util.infoDisplay(f"Recorded as new series {newSeriesUID}.")
            self.onSearchChanged(self.searchEdit.text)
        except Exception as e:
            slicer.util.errorDisplay(f"Failed to record result: {e}")

    def onShowLineage(self):
        selected = self._selectedSeries()
        if not selected:
            slicer.util.errorDisplay("Select a series first.")
            return
        lineage = self.logic.getLineage(selected["seriesUID"])
        dlg = LineageGraphDialog(lineage, selected["seriesUID"], parent=slicer.util.mainWindow())
        dlg.exec_()

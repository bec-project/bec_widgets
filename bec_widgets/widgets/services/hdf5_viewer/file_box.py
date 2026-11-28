"""The box on top of the File tab: what its plot draws, by role, as the Signals tab shows it."""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Callable, Hashable

from qtpy.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.fuzzy_search import close_names, match
from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_preview import (
    KEPT_MAX,
    SCAN_AXES,
    TIME,
    VIEW_LABELS,
    H5Preview,
    dataset_name,
)
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import H5Node, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.role_fields import ChipInfo, Role, RoleBox, Swatch
from bec_widgets.widgets.services.hdf5_viewer.role_list import ListEntry, Listing, RoleTyping
from bec_widgets.widgets.services.hdf5_viewer.style import mute

#: Title of the group of Index and Timestamp in the list of the X field, as in the Signals tab.
X_MODES_TITLE = "Plot axis"
#: Title of the group of the scan's axes and the datasets next to the shown one.
X_AXES_TITLE = "Scan axes"
#: What each entry of the plot axis group puts on the x axis.
X_WORDS = {"": "row number", TIME: "time of each value", SCAN_AXES: "the scan's positions"}
#: Tooltip of the x axis while the file chose it.
AUTO_TIP = "Chosen automatically: the axis the file names for this dataset"
#: Tooltip of the x axis while the file names none for the dataset.
AUTO_INDEX_TIP = "The file names no axis for this dataset: its values are plotted by row"
#: Tooltip of the chip of the selected dataset.
SELECTED_TIP = "The dataset selected in the tree; this curve follows the selection"
#: Words of the list of the Y field: what a dataset becomes, what Enter does.
CAN_BE = "can be a curve"
_boxes = itertools.count()


def group_of(path: str) -> str:
    """
    The group a dataset is listed under, as said next to its name in the list of the Y field.

    Args:
        path (str): Path of the dataset inside its file.

    Returns:
        str: E.g. ``devices`` for ``/entry/collection/devices/bpm4i/bpm4i/value`` (a BEC
        ``value`` dataset is named by its signal group, see :func:`dataset_name`), ``data`` for
        ``/entry/data/samx``, ``/`` at the top of the file.
    """
    parts = [part for part in path.split("/") if part]
    depth = 3 if len(parts) > 3 and parts[-1] == "value" else 1
    return parts[-depth - 1] if len(parts) > depth else "/"


class FileBox(QWidget):
    """
    The top of the File tab, over the tree of the file: the X and Y fields of the Signals tab,
    for the plot of the File tab. X is what the Line view plots against, Y the selected dataset
    and the datasets kept next to it.
    """

    def __init__(
        self,
        preview: H5Preview,
        service: H5Service,
        content: QWidget,
        parent: QWidget | None = None,
    ):
        """
        Args:
            preview (H5Preview): The plot of the File tab.
            service (H5Service): Reads the list of datasets the Y field offers.
            content (QWidget): What the tab shows under the box: the tree and its details.
            parent (QWidget | None): The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("file_box_panel")
        self.preview = preview
        self.service = service
        self._channel = f"file-box-{next(_boxes)}-datasets"
        #: The datasets of a file that can be a curve, by file, once listed.
        self._datasets: dict[str, list[H5Node]] = {}
        #: Why the datasets of a file could not be listed, by file.
        self._dataset_errors: dict[str, str] = {}
        self._listing_file = ""
        #: Reset and whether the plot is at its default, where another box decides them.
        self._link: tuple[Callable[[], None], Callable[[], bool]] | None = None
        #: The box whose x axis the File tab shares now, e.g. the Signals tab's, or None.
        self._x_owner: Callable[[], object | None] = lambda: None
        #: The box whose fields the File tab shows while the plot pane shows that box's plot,
        #: e.g. the Signals tab's for the plot of the selected scan, or None.
        self._scan_owner: Callable[[], object | None] = lambda: None
        #: Keeps a dataset taken in the Y field, or takes it off; the preview's by default.
        self._keep: Callable[[H5Node], None] = preview.toggle_kept
        #: Whether a dataset is on the plot of the box that owns the fields, or cannot be, as
        #: the list of the Y field says it; None while the preview's kept datasets tell.
        self._owner_y_state: Callable[[H5Node], tuple[str, str]] | None = None
        #: The file the tab shows, for the list of the Y field while nothing is selected.
        self._shown_file: Callable[[], str] = lambda: ""
        #: A note of the viewer under the fields, e.g. why a running scan's file is not open.
        self._viewer_note = ""

        self.box = RoleBox(self)
        self.box.setObjectName("file_role_box")
        self.box.hide()
        self.reset_button = self.box.reset_button
        self.box.remove_requested.connect(self.remove_from_role)
        self.box.reset_requested.connect(self.reset)
        self.typing = RoleTyping(
            self, self.box, self.role_listing, self.take_role, self.remove_from_role
        )

        self.note = QLabel(self)
        self.note.setObjectName("file_box_note")
        self.note.setWordWrap(True)
        mute(self.note)
        self.note.setContentsMargins(6, 2, 6, 2)
        self.note.hide()

        top = QWidget(self)
        top.setObjectName("file_top")
        top.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)
        top_layout.addWidget(self.box)
        top_layout.addWidget(self.note)
        self.top = top

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(top)
        layout.addWidget(content, 1)

        preview.roles_changed.connect(self.update_box)
        preview.kept_changed.connect(self.update_box)
        self.update_box()

    # -- what the box shows -------------------------------------------------------------

    def roles(self) -> list[Role]:
        """
        The rows of the box for what the File tab shows now.

        Returns:
            list[Role]: X, then Y; none while nothing is selected and nothing is kept.
        """
        owner = self._scan_owner()
        if owner is not None:
            return self._owner_roles(owner)
        preview = self.preview
        node = preview.node
        if node is None and not preview.kept_paths():
            return []
        return [self._x_role(), self._y_role()]

    @staticmethod
    def _owner_roles(owner) -> list[Role]:
        """
        The fields of the box that owns the plot, as it shows them. The curves are taken from
        the file's datasets here, so the Y field of Lines offers those.
        """
        roles = []
        for role in owner.roles():
            if role.letter == "Y" and owner.role_kind("Y") == "curves":
                role = dataclasses.replace(
                    role,
                    hint="" if role.inactive else "Type to add a dataset",
                    can_be=CAN_BE,
                    placeholder="Add a dataset…",
                )
            roles.append(role)
        return roles

    def _owns(self, letter: str):
        """The box that owns a field, or None where this box answers for it itself."""
        owner = self._scan_owner()
        if owner is None:
            return self._x_owner() if letter == "X" else None
        if letter == "Y" and owner.role_kind("Y") == "curves":
            return None
        return owner

    def _not_used(self) -> str:
        """Why the fields do not apply to what the plot shows, or empty when they do."""
        node = self.preview.node
        if node is None:
            return "Select a dataset to plot it"
        view = self.preview.view
        if view == "line":
            return ""
        if view in VIEW_LABELS:
            return f"Not used in {VIEW_LABELS[view]}"
        return "Not used for this entry"

    def _x_role(self) -> Role:
        preview = self.preview
        data = preview.x_data()
        inactive = self._not_used()
        if preview.view == "map" and data is not None:
            inactive = ""
        owner = self._x_owner()
        if owner is not None:
            # Shared: the X of the Signals tab, as it shows it there.
            role = next(role for role in owner.roles() if role.letter == "X")
            return dataclasses.replace(role, inactive=inactive) if inactive else role
        chips = ()
        if data is not None and not inactive:
            auto = preview.x_is_auto()
            tip = ""
            if auto:
                tip = AUTO_INDEX_TIP if data == "" else AUTO_TIP
            chips = (ChipInfo(("x", data), preview.x_text(), auto=auto, tip=tip),)
        name = chips[0].label if chips else "none"
        return Role(
            "X",
            axis=True,
            multi=False,
            caption="x axis",
            chips=chips,
            name=f"The x axis: {name}",
            hint="" if inactive else "Type to choose what to plot against",
            can_be="can be the x axis",
            inactive=inactive,
        )

    def _y_role(self) -> Role:
        preview = self.preview
        node = preview.node
        inactive = self._not_used()
        selected = node.path if node is not None else ""
        kept = preview.kept_chips()
        chips: list[ChipInfo] = []
        if not inactive and selected and selected not in preview.kept_paths():
            chips.append(
                ChipInfo(
                    ("selected", selected),
                    preview.signal_name(),
                    tag="selected",
                    swatch=Swatch(preview.selected_color()),
                    tip=SELECTED_TIP,
                )
            )
        for chip in kept:
            tag = "selected" if chip.path == selected and not inactive else ""
            chips.append(
                ChipInfo(
                    ("kept", chip.path),
                    chip.label,
                    removable=True,
                    swatch=Swatch(chip.color or chip.slot_color),
                    tip=f"Kept on the plot: {chip.path}",
                    problem=chip.problem,
                    tag=tag,
                )
            )
        count = len(chips)
        return Role(
            "Y",
            axis=False,
            multi=True,
            caption="",
            chips=tuple(chips),
            name=f"The curves on the plot, {count} curve{'' if count == 1 else 's'}",
            hint="" if inactive else "Type to add a dataset",
            can_be=CAN_BE,
            placeholder="Add a dataset…",
            inactive=inactive,
        )

    def update_box(self) -> None:
        """Show what the plot of the File tab draws now."""
        letters = list(self.box.fields)
        preview = self.preview
        self.box.set_roles(self.roles(), not self.is_default())
        if list(self.box.fields) != letters:
            self.typing.attach()
        elif self.typing.is_open():
            self.typing.refresh()
        notes = [text for text in (self._viewer_note, preview.x_note, preview.kept_note()) if text]
        self.note.setText("\n".join(notes))
        self.note.setVisible(bool(notes))

    def set_viewer_note(self, text: str) -> None:
        """
        Say something under the fields for the viewer, e.g. why the tree is empty.

        Args:
            text (str): The note, or empty for none.
        """
        if text != self._viewer_note:
            self._viewer_note = text
            self.update_box()

    # -- the chips ----------------------------------------------------------------------

    def remove_from_role(self, letter: str, key: Hashable) -> None:
        """
        The x of a chip, or Backspace or Delete on it: take a kept dataset off the plot.

        Args:
            letter (str): The field.
            key (Hashable): The key of the chip.
        """
        owner = self._scan_owner()
        if owner is not None:
            owner.remove_from_role(letter, key)
            return
        if letter == "Y" and isinstance(key, tuple) and key[0] == "kept":
            self.preview.remove_kept(key[1])

    def link(
        self,
        reset: Callable[[], None],
        is_default: Callable[[], bool],
        x_owner: Callable[[], object | None] | None = None,
        scan_owner: Callable[[], object | None] | None = None,
        keep: Callable[[H5Node], None] | None = None,
        y_state: Callable[[H5Node], tuple[str, str]] | None = None,
        shown_file: Callable[[], str] | None = None,
    ) -> None:
        """
        Let another box decide what Reset does and when it shows, e.g. the viewer while the
        File tab shows the file of the selected scan and shares its curves with Signals.

        Args:
            reset (Callable[[], None]): Does the reset.
            is_default (Callable[[], bool]): Whether the plot is at its default.
            x_owner (Callable[[], object | None] | None): The box that owns the x axis while
                it is shared, e.g. the Signals tab's list, or None while the File tab has its
                own: its X field then shows, lists and takes what that box does.
            scan_owner (Callable[[], object | None] | None): The box whose plot the plot pane
                shows now, or None while it shows the File tab's preview: the fields are then
                that box's, and only the curves of Lines are taken from the file's datasets.
            keep (Callable[[H5Node], None] | None): Keeps a dataset taken in the Y field, in
                place of the preview's own keeping.
            y_state (Callable[[H5Node], tuple[str, str]] | None): Whether a dataset is on the
                plot of ``scan_owner`` or cannot be, as ``("on", words)``, ``("off", reason)``
                or ``("", "")``, for the list of the Y field while that box owns the fields.
            shown_file (Callable[[], str] | None): The file the tab shows, whose datasets the
                Y field lists while no dataset is selected.
        """
        self._link = (reset, is_default)
        if x_owner is not None:
            self._x_owner = x_owner
        if scan_owner is not None:
            self._scan_owner = scan_owner
        if keep is not None:
            self._keep = keep
        if y_state is not None:
            self._owner_y_state = y_state
        if shown_file is not None:
            self._shown_file = shown_file
        self.update_box()

    def is_default(self) -> bool:
        """
        Whether the plot is at its default, so that Reset does not show.

        Returns:
            bool: True while nothing was changed by hand.
        """
        if self._link is not None:
            return self._link[1]()
        return self.own_default()

    def own_default(self) -> bool:
        """Whether the plot is the axes the file names and no kept dataset."""
        return self.preview.x_is_auto() and not self.preview.kept_paths()

    def reset(self) -> None:
        """Reset: the default plot again."""
        if self._link is not None:
            self._link[0]()
        else:
            self.own_reset()
        self.update_box()

    def own_reset(self) -> None:
        """Plot against the axes the file names again and take every kept dataset off."""
        self.preview.reset_x()
        self.preview.clear_kept()

    # -- typing in the fields -----------------------------------------------------------

    def role_listing(self, letter: str, text: str) -> Listing:
        """
        The list under a field: what fits a typed text, or everything that can take the role.

        Args:
            letter (str): ``X`` or ``Y``.
            text (str): What was typed; empty for the full list.

        Returns:
            Listing: Its lines and the line Enter takes.
        """
        field = self.box.fields.get(letter)
        if field is None or field.role.inactive:
            return Listing((), None)
        owner = self._owns(letter)
        if owner is not None:
            return owner.role_listing(letter, text)
        if letter == "X":
            return self._x_listing(text)
        return self._y_listing(text)

    def take_role(self, letter: str, key: Hashable) -> None:
        """
        Give the role of a field to what was chosen in its list.

        Args:
            letter (str): ``X`` or ``Y``.
            key (Hashable): The key of the entry.
        """
        owner = self._owns(letter)
        if owner is not None:
            owner.take_role(letter, key)
            return
        if not isinstance(key, tuple) or len(key) != 2:
            return
        kind, value = key
        if letter == "X" and kind == "x":
            if value != self.preview.x_data():
                self.preview.choose_x(value)
        elif letter == "Y" and kind == "dataset":
            node = next(
                (n for n in self._datasets.get(self._listing_file, []) if n.path == value), None
            )
            if node is None:
                return
            if self._scan_owner() is not None and self._owner_y_state is not None:
                # On the scan's plot already, or no room for it: nothing to take.
                if self._y_state(node)[0] == "":
                    self._keep(node)
            elif value not in self.preview.kept_paths():
                self._keep(node)

    # X ------------------------------------------------------------------------------------

    def _x_entries(self) -> list[tuple[str, str, str, str, str]]:
        """(group, name, data, state, tip) of each choice of the X field, as the plot offers it."""
        preview = self.preview
        shown = preview.x_data()
        axes = preview.scan_axes
        found = []
        for entry in preview.x_entries():
            if entry.data in ("", TIME):
                group = X_MODES_TITLE
            else:
                group = X_AXES_TITLE
            name = axes.names if entry.data == SCAN_AXES and axes is not None else entry.text
            state = "on" if entry.data == shown else ("" if entry.enabled else "off")
            found.append((group, name, entry.data, state, entry.tip))
        return found

    @staticmethod
    def _x_entry(found, positions: tuple[int, ...] = ()) -> ListEntry:
        _group, name, data, state, tip = found
        if state == "on":
            right = short = "x axis"
        elif state == "off":
            right = short = tip
        else:
            right = X_WORDS.get(data, "dataset")
            short = right
        return ListEntry("entry", name, ("x", data), positions, right, short, state=state)

    def _x_listing(self, text: str) -> Listing:
        found = self._x_entries()
        if not found:
            return Listing(
                (ListEntry("message", "Nothing to plot against here", strong=True),), None
            )
        if not text.strip():
            entries: list[ListEntry] = []
            for title in (X_MODES_TITLE, X_AXES_TITLE):
                members = [f for f in found if f[0] == title and f[3] != "off"]
                if members:
                    entries.append(ListEntry("head", title, count=len(members)))
                    entries += [self._x_entry(f) for f in members]
            return Listing(tuple(entries), None)
        fits = []
        for position, item in enumerate(found):
            fit = match(text, item[1])
            if fit is not None:
                fits.append((fit.rank, position, item, fit.positions))
        fits.sort(key=lambda f: (f[0], f[1]))
        fits = [f for f in fits if f[2][3] != "off"] + [f for f in fits if f[2][3] == "off"]
        entries = [self._x_entry(f[2], f[3]) for f in fits]
        if not entries:
            return Listing(
                (
                    ListEntry(
                        "message", f"Nothing to plot against fits “{text.strip()}”", strong=True
                    ),
                ),
                None,
            )
        mark = next((i for i, e in enumerate(entries) if e.takeable), None)
        return Listing(tuple(entries), mark)

    # Y ------------------------------------------------------------------------------------

    def _file_of_datasets(self) -> str:
        """The file whose datasets the Y field offers: the one the tree shows."""
        node = self.preview.node
        if node is not None and node.file_path:
            return node.file_path
        return self._shown_file() or self.preview.kept_file()

    def _datasets_of(self, file_path: str) -> list[H5Node] | None:
        """The datasets of a file that can be a curve, or None while they are being listed."""
        if file_path in self._datasets:
            return self._datasets[file_path]
        if file_path in self._dataset_errors:
            return []
        if self._listing_file != file_path or not self.service.has_pending(self._channel):
            self._listing_file = file_path

            def done(nodes: list[H5Node], path=file_path):
                self._datasets = {path: nodes}
                self._dataset_errors.pop(path, None)
                if self.typing.is_open("Y"):
                    self.typing.refresh()

            def failed(error: H5ReadError, path=file_path):
                self._dataset_errors[path] = error.message
                if self.typing.is_open("Y"):
                    self.typing.refresh()

            self.service.request(
                self._channel,
                file_path,
                lambda ctx: h5_reader.curve_datasets(file_path, cancel=ctx.cancelled),
                done,
                failed,
            )
        return None

    def _y_state(self, node: H5Node) -> tuple[str, str]:
        if self._scan_owner() is not None and self._owner_y_state is not None:
            # The plot of the scan: no dataset is drawn because it is selected.
            return self._owner_y_state(node)
        preview = self.preview
        selected = preview.node.path if preview.node is not None else ""
        if node.path in preview.kept_paths():
            return "on", "on the plot"
        if node.path == selected:
            return "on", "selected"
        if len(preview.kept_paths()) >= KEPT_MAX:
            return "off", f"{KEPT_MAX} kept at most"
        return "", ""

    @staticmethod
    def _y_entry(node: H5Node, positions: tuple[int, ...], state: tuple[str, str]) -> ListEntry:
        length = h5_reader.format_count(node.size)
        if state[0]:
            right, short = state[1], state[1]
        else:
            right, short = f"{group_of(node.path)} · {length}", length
        return ListEntry(
            "entry",
            dataset_name(node.path),
            ("dataset", node.path),
            positions,
            right,
            short,
            state=state[0],
        )

    def _y_listing(self, text: str) -> Listing:
        file_path = self._file_of_datasets()
        nodes = self._datasets_of(file_path) if file_path else []
        if nodes is None:
            return Listing((ListEntry("message", "Listing the datasets of the file…"),), None)
        error = self._dataset_errors.get(file_path, "")
        if error:
            return Listing(
                (ListEntry("message", f"The datasets could not be listed: {error}", strong=True),),
                None,
            )
        states = {node.path: self._y_state(node) for node in nodes}
        typed = text.strip()
        if not typed:
            entries = [ListEntry("head", "Datasets", count=len(nodes))]
            entries += [self._y_entry(node, (), states[node.path]) for node in nodes]
            if not nodes:
                entries = [ListEntry("message", f"No dataset of this file {CAN_BE}", strong=True)]
            return Listing(tuple(entries), None)
        fits = []
        for position, node in enumerate(nodes):
            fit = match(typed, dataset_name(node.path))
            if fit is not None:
                fits.append((fit.rank, position, node, fit.positions))
        fits.sort(key=lambda f: (f[0], f[1]))
        can = [f for f in fits if states[f[2].path][0] != "off"]
        cannot = [f for f in fits if states[f[2].path][0] == "off"]
        entries = [self._y_entry(f[2], f[3], states[f[2].path]) for f in can + cannot]
        if not entries:
            return self._y_no_fit(typed, nodes, states)
        mark = next((i for i, e in enumerate(entries) if e.takeable), None)
        return Listing(tuple(entries), mark)

    def _y_no_fit(self, typed: str, nodes: list[H5Node], states) -> Listing:
        entries = [ListEntry("message", f"No dataset of this file fits “{typed}”", strong=True)]
        by_name: dict[str, H5Node] = {}
        for node in nodes:
            if states[node.path][0] != "off":
                by_name.setdefault(dataset_name(node.path), node)
        close = [by_name[name] for name in close_names(typed, list(by_name))]
        if not close:
            return Listing(tuple(entries), None)
        entries.append(ListEntry("head", "Similar names", count=len(close)))
        entries += [self._y_entry(node, (), states[node.path]) for node in close]
        return Listing(tuple(entries), None)

    def cleanup(self) -> None:
        """Stop listing datasets and close the list."""
        self.typing.close()
        self.service.cancel(self._channel)

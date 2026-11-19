"""
Volume data model for the VolumePlot widget.

Pure numpy: a regular 3D grid of values with one coordinate array per axis, named cuts
("marks"), slicing, projections and the gridding of scattered scan points. Nothing here
touches Qt or OpenGL, so it is cheap to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

AXIS_NAMES = ("x", "y", "z")


@dataclass(frozen=True)
class VolumeMark:
    """A named position along one axis, for example a focus in a beam caustic."""

    axis: int
    coordinate: float
    label: str


@dataclass
class VolumeData:
    """
    A regular 3D grid of values.

    Args:
        values (np.ndarray): Array of shape (nx, ny, nz). NaN marks voxels without data.
        axes (tuple[np.ndarray, np.ndarray, np.ndarray]): Voxel centre coordinates per axis.
        labels (tuple[str, str, str]): Axis names, for example motor names.
        units (tuple[str, str, str]): Axis units.
        value_label (str): Name of the value, for example the monitored signal.
        marks (list[VolumeMark]): Named cuts shown in the cut strip and the 3D view.
        box_aspect (tuple[float, float, float] | None): Relative box lengths in the 3D view;
            None picks them from the coordinates (see :meth:`display_box`).
        up_axis (int): Data axis that points up in the 3D view.
    """

    values: np.ndarray
    axes: tuple[np.ndarray, np.ndarray, np.ndarray]
    labels: tuple[str, str, str] = AXIS_NAMES
    units: tuple[str, str, str] = ("", "", "")
    value_label: str = "value"
    marks: list[VolumeMark] = field(default_factory=list)
    box_aspect: tuple[float, float, float] | None = None
    up_axis: int = 2

    def __post_init__(self):
        values = np.asarray(self.values, dtype=float)
        if values.ndim != 3:
            raise ValueError(f"Volume values must be 3D, got shape {values.shape}.")
        self.values = values
        axes = []
        for axis, n in enumerate(values.shape):
            coords = None if self.axes is None else self.axes[axis]
            coords = np.arange(n, dtype=float) if coords is None else np.asarray(coords, float)
            if coords.shape != (n,):
                raise ValueError(f"Axis {axis} has {coords.shape[0]} coordinates for {n} voxels.")
            axes.append(coords)
        self.axes = tuple(axes)
        if self.up_axis not in (0, 1, 2):
            raise ValueError("up_axis must be 0, 1 or 2.")

    @classmethod
    def from_array(
        cls,
        values: np.ndarray,
        x: np.ndarray | None = None,
        y: np.ndarray | None = None,
        z: np.ndarray | None = None,
        **kwargs,
    ) -> VolumeData:
        """
        Build a volume from a 3D array and optional coordinates.

        Args:
            values (np.ndarray): Array of shape (nx, ny, nz).
            x (np.ndarray | None): Coordinates of the first axis; voxel indices when omitted.
            y (np.ndarray | None): Coordinates of the second axis.
            z (np.ndarray | None): Coordinates of the third axis.
            **kwargs: Further VolumeData fields (labels, units, marks, ...).

        Returns:
            VolumeData: The volume.
        """
        return cls(values=values, axes=(x, y, z), **kwargs)

    # ------------------------------------------------------------------ geometry
    @property
    def shape(self) -> tuple[int, int, int]:
        """Number of voxels per axis."""
        return tuple(int(n) for n in self.values.shape)

    def spacing(self, axis: int) -> float:
        """Coordinate step between two voxel centres along ``axis`` (1.0 for one voxel)."""
        coords = self.axes[axis]
        if coords.size < 2:
            return 1.0
        step = float(coords[-1] - coords[0]) / (coords.size - 1)
        return step if step != 0 else 1.0

    def extent(self, axis: int) -> tuple[float, float]:
        """Outer edges of the voxels along ``axis``, in coordinates."""
        coords = self.axes[axis]
        half = 0.5 * self.spacing(axis)
        return float(coords[0] - half), float(coords[-1] + half)

    def coordinate(self, axis: int, index: int) -> float:
        """Coordinate of the voxel centre ``index`` along ``axis``."""
        return float(self.axes[axis][int(np.clip(index, 0, self.shape[axis] - 1))])

    def index_of(self, axis: int, coordinate: float) -> int:
        """Index of the voxel centre nearest to ``coordinate`` along ``axis``."""
        coords = self.axes[axis]
        return int(np.clip(np.nanargmin(np.abs(coords - coordinate)), 0, coords.size - 1))

    def display_box(self) -> tuple[float, float, float]:
        """
        Relative box lengths for the 3D view, the longest one being 1.

        The explicit ``box_aspect`` wins. Otherwise the physical lengths are used when all
        axes share a unit and no axis is more than ten times longer than another; in every
        other case the box is a cube.
        """
        if self.box_aspect is not None:
            lengths = np.asarray(self.box_aspect, dtype=float)
        else:
            lengths = np.array([abs(np.subtract(*self.extent(a))) for a in range(3)])
            same_unit = len(set(self.units)) == 1
            finite = np.all(np.isfinite(lengths)) and np.all(lengths > 0)
            if not (same_unit and finite and lengths.max() / lengths.min() <= 10):
                lengths = np.ones(3)
        return tuple(float(v) for v in lengths / lengths.max())

    # ------------------------------------------------------------------ cuts
    @staticmethod
    def plane_axes(axis: int) -> tuple[int, int]:
        """The two axes spanning a cut perpendicular to ``axis``, in data order."""
        return tuple(a for a in range(3) if a != axis)  # type: ignore[return-value]

    def slice(self, axis: int, index: int) -> np.ndarray:
        """
        The cut perpendicular to ``axis`` at voxel ``index``.

        Returns:
            np.ndarray: Array indexed by the two remaining axes in data order,
            for example ``values[:, :, k]`` for a cut along z.
        """
        index = int(np.clip(index, 0, self.shape[axis] - 1))
        return np.take(self.values, index, axis=axis)

    def projection(self, axis: int, mode: str = "sum") -> np.ndarray:
        """
        Project the volume along ``axis``, ignoring voxels without data.

        Args:
            axis (int): Axis to project along.
            mode (str): "sum" or "max".

        Returns:
            np.ndarray: Array indexed by the two remaining axes in data order.
        """
        if not np.isfinite(self.values).any():
            return np.zeros([n for a, n in enumerate(self.shape) if a != axis])
        if mode == "max":
            return np.nanmax(np.where(np.isfinite(self.values), self.values, -np.inf), axis=axis)
        return np.nansum(self.values, axis=axis)

    def value_range(self) -> tuple[float, float]:
        """Minimum and maximum of the finite values; (0, 1) for an empty volume."""
        finite = self.values[np.isfinite(self.values)]
        if finite.size == 0:
            return 0.0, 1.0
        low, high = float(finite.min()), float(finite.max())
        if high <= low:
            high = low + 1.0
        return low, high

    def normalized(self) -> np.ndarray:
        """Values scaled to 0..1 over the finite range; voxels without data become 0."""
        low, high = self.value_range()
        norm = (self.values - low) / (high - low)
        return np.nan_to_num(np.clip(norm, 0.0, 1.0), nan=0.0)

    def brightest_along(self, samples: np.ndarray) -> int | None:
        """
        Pick the brightest of a set of sample points given in voxel-index space.

        Args:
            samples (np.ndarray): Points of shape (n, 3) in continuous voxel-index space
                (voxel ``i`` spans ``[i, i + 1)``).

        Returns:
            int | None: Position of the brightest sample, or None when no sample holds data.
        """
        if samples.size == 0:
            return None
        idx = np.floor(samples).astype(int)
        for axis, n in enumerate(self.shape):
            idx[:, axis] = np.clip(idx[:, axis], 0, n - 1)
        values = self.values[idx[:, 0], idx[:, 1], idx[:, 2]]
        if not np.isfinite(values).any():
            return None
        return int(np.nanargmax(values))


# ---------------------------------------------------------------------- gridding
def _levels(coords: np.ndarray, tolerance: float) -> np.ndarray:
    """
    Distinct levels of ``coords``: values closer than ``tolerance`` are one level.

    Measured readbacks scatter a little around each set point (a slow axis also repeats
    one readback many times). When most gaps between distinct sorted values are tiny and a
    few are large, the tolerance grows to 50 times their median, so each cloud of readbacks
    becomes one level at its mean.
    """
    ordered = np.sort(coords[np.isfinite(coords)])
    if ordered.size < 2:
        return ordered
    gaps = np.diff(ordered)
    threshold = tolerance
    distinct = gaps[gaps > tolerance]
    if distinct.size:
        jitter = 50.0 * float(np.median(distinct))
        if jitter < float(distinct.max()):
            threshold = jitter
    groups = np.cumsum(np.concatenate(([True], gaps > threshold))) - 1
    return np.bincount(groups, weights=ordered) / np.bincount(groups)


def _nearest_level_index(levels: np.ndarray, coords: np.ndarray) -> np.ndarray:
    """Index of the nearest entry of the sorted ``levels`` for each coordinate."""
    if levels.size == 1:
        return np.zeros(coords.shape, dtype=int)
    idx = np.clip(np.searchsorted(levels, coords), 1, levels.size - 1)
    nearer_left = np.abs(coords - levels[idx - 1]) <= np.abs(levels[idx] - coords)
    return np.where(nearer_left, idx - 1, idx)


def grid_from_points(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    values: np.ndarray,
    planned: np.ndarray | None = None,
    max_bins: int = 128,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """
    Put scattered scan points on a regular 3D grid.

    With ``planned`` positions (the scan's own position list, for example of a 3D grid
    scan) point ``i`` lands in the voxel of planned position ``i``, so a running scan fills
    a grid of its final size. Without them the measured positions are used: when they take
    few distinct levels per axis they form the grid directly, otherwise they are binned
    and averaged.

    Args:
        x (np.ndarray): Positions along the first axis.
        y (np.ndarray): Positions along the second axis.
        z (np.ndarray): Positions along the third axis.
        values (np.ndarray): Value per point.
        planned (np.ndarray | None): Planned positions of shape (n_planned, 3).
        max_bins (int): Bins per axis when the points have to be binned.

    Returns:
        tuple: The grid of shape (nx, ny, nz) with NaN in empty voxels, and the voxel
        centre coordinates per axis.
    """
    n = min(len(x), len(y), len(z), len(values))
    points = np.column_stack(
        [np.asarray(x, float)[:n], np.asarray(y, float)[:n], np.asarray(z, float)[:n]]
    )
    values = np.asarray(values, float)[:n]

    use_plan = planned is not None and len(planned) >= n and np.ndim(planned) == 2
    source = np.asarray(planned, float)[:, :3] if use_plan else points
    if source.shape[0] == 0:
        return np.full((1, 1, 1), np.nan), (np.zeros(1), np.zeros(1), np.zeros(1))

    axes = []
    indices = []
    for axis in range(3):
        coords = source[:, axis]
        span = float(np.nanmax(coords) - np.nanmin(coords)) if coords.size else 0.0
        levels = _levels(coords, tolerance=max(span, 1.0) * 1e-6)
        if use_plan or levels.size <= max_bins:
            idx = _nearest_level_index(levels, coords)
            axes.append(levels)
        else:
            edges = np.linspace(np.nanmin(coords), np.nanmax(coords), max_bins + 1)
            idx = np.clip(np.digitize(coords, edges) - 1, 0, max_bins - 1)
            axes.append(0.5 * (edges[:-1] + edges[1:]))
        indices.append(idx[:n])

    shape = tuple(a.size for a in axes)
    total = np.zeros(shape)
    count = np.zeros(shape)
    np.add.at(total, tuple(indices), values)
    np.add.at(count, tuple(indices), 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        grid = np.where(count > 0, total / count, np.nan)
    return grid, tuple(axes)

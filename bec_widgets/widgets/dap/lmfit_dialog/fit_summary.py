"""Qt-free view model for LMFit DAP summaries, shared by the QML and QWidget fit dialogs."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

FitQuality = Literal["good", "fair", "poor", "failed", "unknown"]

QUALITY_LABELS: dict[str, str] = {
    "good": "Good fit",
    "fair": "Fair fit",
    "poor": "Poor fit",
    "failed": "Fit failed",
    "unknown": "No R²",
}

# A parameter whose standard error is larger than its value is effectively unconstrained.
LOOSE_RELATIVE_ERROR = 1.0
STRONG_CORRELATION = 0.9


def format_number(value: Any, digits: int = 4) -> str:
    """Format a number with significant digits, switching to scientific notation for extremes.

    Args:
        value (Any): The value to format.
        digits (int): Number of significant digits.

    Returns:
        str: The formatted number, or an em dash when the value is missing or not numeric.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    if math.isnan(value):
        return "—"
    if math.isinf(value):
        return "∞" if value > 0 else "−∞"
    if value == 0:
        return "0"
    magnitude = abs(value)
    if magnitude < 1e-3 or magnitude >= 1e5:
        mantissa, exponent = f"{value:.{digits - 1}e}".split("e")
        mantissa = mantissa.rstrip("0").rstrip(".")
        return f"{mantissa}e{int(exponent)}".replace("-", "−")
    text = f"{value:.{digits}g}"
    if "e" in text:  # pragma: no cover - guarded by the magnitude check above
        text = f"{value:f}"
    return text.replace("-", "−")


def short_model_name(model: str) -> str:
    """Turn lmfit's 'Model(breit_wigner)' into 'breit_wigner'; composite models keep their form.

    Args:
        model (str): The model repr reported by lmfit.

    Returns:
        str: A short, readable model name.
    """
    if not model:
        return "Fit"
    return re.sub(r"Model\(([^)]*)\)", r"\1", model)


@dataclass
class FitParam:
    """One fitted parameter, ready for display."""

    name: str
    value: Any
    stderr: Any = None
    vary: bool = True
    minimum: Any = None
    maximum: Any = None
    initial: Any = None
    expr: str | None = None
    correlations: dict[str, float] = field(default_factory=dict)

    @property
    def value_text(self) -> str:
        """The formatted value."""
        return format_number(self.value)

    @property
    def stderr_text(self) -> str:
        """The formatted standard error, empty for fixed or derived parameters."""
        if not self.vary or self.expr:
            return ""
        return format_number(self.stderr)

    @property
    def relative_error(self) -> float | None:
        """The standard error relative to the value, or None if it cannot be computed."""
        if not isinstance(self.stderr, (int, float)) or not isinstance(self.value, (int, float)):
            return None
        if self.value == 0 or math.isnan(self.stderr) or math.isnan(self.value):
            return None
        return abs(self.stderr / self.value)

    @property
    def relative_error_text(self) -> str:
        """The relative error as a percentage."""
        rel = self.relative_error
        if rel is None or not self.vary:
            return ""
        if rel >= 10:
            return ">999%"
        return f"{rel * 100:.0f}%" if rel >= 0.01 else "<1%"

    @property
    def state(self) -> Literal["ok", "loose", "fixed", "derived", "unknown"]:
        """How well the parameter is determined."""
        if self.expr:
            return "derived"
        if not self.vary:
            return "fixed"
        if not isinstance(self.stderr, (int, float)) or math.isnan(self.stderr):
            return "unknown"
        rel = self.relative_error
        return "loose" if rel is not None and rel > LOOSE_RELATIVE_ERROR else "ok"

    @property
    def strong_correlations(self) -> list[tuple[str, float]]:
        """Correlations with other parameters above the strong threshold, strongest first."""
        strong = [
            (name, r)
            for name, r in (self.correlations or {}).items()
            if isinstance(r, (int, float)) and abs(r) >= STRONG_CORRELATION
        ]
        return sorted(strong, key=lambda item: -abs(item[1]))

    @property
    def tooltip(self) -> str:
        """A plain-text explanation of the parameter: bounds, start value and correlations."""
        lines = [self.name]
        if self.expr:
            lines.append(f"Derived from: {self.expr}")
        elif not self.vary:
            lines.append("Fixed during the fit")
        if self.state == "loose":
            lines.append("Poorly constrained: the error is larger than the value")
        bounds_known = self.minimum is not None or self.maximum is not None
        if bounds_known and not (
            _is_inf(self.minimum, negative=True) and _is_inf(self.maximum, negative=False)
        ):
            lines.append(f"Bounds: {format_number(self.minimum)} … {format_number(self.maximum)}")
        if isinstance(self.initial, (int, float)):
            lines.append(f"Initial value: {format_number(self.initial)}")
        strong = self.strong_correlations
        if strong:
            pairs = ", ".join(f"{name} ({format_number(r, 3)})" for name, r in strong)
            lines.append(f"Strongly correlated with {pairs}")
        return "\n".join(lines)

    @classmethod
    def from_lmfit(cls, raw: Any) -> FitParam:
        """Build a parameter from lmfit's serialized form.

        lmfit serializes a parameter as
        [name, value, vary, expr, min, max, brute_step, stderr, correl, init_value, user_data].
        A mapping with the same keys is accepted as well.

        Args:
            raw (Any): The serialized parameter.

        Returns:
            FitParam: The parsed parameter.
        """
        if isinstance(raw, dict):
            return cls(
                name=str(raw.get("name", "")),
                value=raw.get("value"),
                stderr=raw.get("stderr"),
                vary=bool(raw.get("vary", True)),
                minimum=raw.get("min"),
                maximum=raw.get("max"),
                initial=raw.get("init_value"),
                expr=raw.get("expr"),
                correlations=raw.get("correl") or {},
            )
        if not isinstance(raw, (list, tuple)) or not raw:
            raise TypeError(f"Unsupported parameter format: {raw!r}")
        raw = list(raw) + [None] * (11 - len(raw))
        return cls(
            name=str(raw[0]),
            value=raw[1],
            vary=True if raw[2] is None else bool(raw[2]),
            expr=raw[3] or None,
            minimum=raw[4],
            maximum=raw[5],
            stderr=raw[7],
            correlations=raw[8] or {},
            initial=raw[9],
        )


def _is_inf(value: Any, negative: bool) -> bool:
    if not isinstance(value, (int, float)) or not math.isinf(value):
        return value is None
    return (value < 0) == negative


@dataclass
class FitSummary:
    """A fit result reduced to what the dialog shows."""

    curve_id: str
    model: str = ""
    method: str = ""
    success: bool | None = None
    message: str = ""
    chisqr: Any = None
    redchi: Any = None
    rsquared: Any = None
    ndata: Any = None
    nvarys: Any = None
    nfev: Any = None
    params: list[FitParam] = field(default_factory=list)

    @property
    def model_name(self) -> str:
        """Short model name for the header."""
        return short_model_name(self.model)

    @property
    def quality(self) -> FitQuality:
        """A coarse verdict on the fit, driven by lmfit's success flag and R²."""
        if self.success is False:
            return "failed"
        if not isinstance(self.rsquared, (int, float)) or math.isnan(self.rsquared):
            return "unknown"
        if self.rsquared >= 0.95:
            return "good"
        if self.rsquared >= 0.8:
            return "fair"
        return "poor"

    @property
    def quality_label(self) -> str:
        """Readable label for the quality verdict."""
        return QUALITY_LABELS[self.quality]

    @property
    def details_text(self) -> str:
        """One line under the model name: method, points and evaluations."""
        parts = []
        if self.method:
            parts.append(self.method)
        if isinstance(self.ndata, int):
            parts.append(f"{self.ndata} points")
        if isinstance(self.nvarys, int):
            parts.append(f"{self.nvarys} free params")
        if isinstance(self.nfev, int):
            parts.append(f"{self.nfev} evaluations")
        return " · ".join(parts)

    @property
    def show_message(self) -> bool:
        """Whether lmfit's message is worth showing (it is noise when the fit succeeded)."""
        return bool(self.message) and (self.success is False or "succeeded" not in self.message)

    @property
    def metrics(self) -> list[tuple[str, str, str]]:
        """The headline metrics as (label, value, tooltip)."""
        return [
            ("R²", format_number(self.rsquared), "Coefficient of determination (1 is perfect)"),
            ("χ²ᵣ", format_number(self.redchi), "Reduced chi-square (≈1 for a good fit)"),
            ("χ²", format_number(self.chisqr), "Chi-square"),
        ]

    @property
    def loose_params(self) -> list[str]:
        """Names of parameters whose error exceeds their value."""
        return [p.name for p in self.params if p.state == "loose"]

    @classmethod
    def from_dap(cls, curve_id: str, data: dict | None) -> FitSummary:
        """Build a summary from the DAP 'fit_summary' dictionary.

        Args:
            curve_id (str): The curve the fit belongs to.
            data (dict | None): The fit summary as published by the LMFit DAP service.

        Returns:
            FitSummary: The parsed summary.
        """
        if not isinstance(data, dict):
            return cls(curve_id=curve_id)
        params = []
        for raw in data.get("params") or []:
            try:
                params.append(FitParam.from_lmfit(raw))
            except (TypeError, IndexError):
                continue
        success = data.get("success")
        return cls(
            curve_id=curve_id,
            model=str(data.get("model", "") or ""),
            method=str(data.get("method", "") or ""),
            success=None if success is None else bool(success),
            message=str(data.get("message", "") or ""),
            chisqr=data.get("chisqr"),
            redchi=data.get("redchi"),
            rsquared=data.get("rsquared"),
            ndata=data.get("ndata"),
            nvarys=data.get("nvarys"),
            nfev=data.get("nfev"),
            params=params,
        )

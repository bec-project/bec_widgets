# Waveform Widget Plotting Ruleset

The Waveform widget allows plotting data from scans generated within the BEC framework. Each scan produces a **scan item
**, which includes measurement data from various devices, as well as additional metadata (e.g., devices driving the
scan, such as `motor_x`, `motor_y`, etc.).

The rules described below define how data from different devices and scans can be plotted together, depending on the
selected `x_mode`.

---

## Types of Curves

- **Live Curves**
    - Continuously updated from the currently running scan.
    - Dynamically adapt based on live data.

- **History Curves**
    - Static curves representing data from a specific completed scan (e.g., scan 110).
    - Displayed only if compatible with the currently selected x-axis device.

---

## General Compatibility Rules

- Data from devices within **the same scan item** can always be plotted against each other, provided they have the same
  number of data points.
    - Example: plotting `detector_1` against `detector_2` from scan 110 to check signal correlation is valid.

- Data from **different scan items** cannot be plotted against each other.
    - Example: plotting x-data from `motor_x` in scan 110 against y-data from `detector_1` in scan 111 is not allowed.

---

## Specific Rules for Each `x_mode`

### 1. `x_mode='auto'` (default)

- Automatically determines the device for x-axis scaling from the currently running (live) scan.
- The primary device used for scaling is the first device listed in the current scan's `scan_report_devices` (usually a
  positioner in the case of step scans).
- **Live Curves**:
    - Always plotted against the selected x-axis device from the current scan.
- **History Curves**:
    - Each history curve is linked to a specific scan item with scan ID.
    - Waveform widget checks compatibility with the currently selected x-axis device from the live scan.
    - If the selected x-axis device data exists in the history curve’s original scan item, the curve is displayed.
    - If the selected x-axis device data does not exist in the original scan item, the history curve remains **hidden**
      until a compatible device is selected again.

_Example Scenario_:

- The live scan currently uses `motor_x` as the x-axis device. Any history curve will only be displayed if its original
  scan item contains data for `motor_x`. If not, the history curve is hidden.

---

### 2. `x_mode='timestamp'`

- X-axis scaling is based on timestamps from each data point.
- All curves, both live and history, are always compatible, as timestamps provide a universal and absolute reference for
  the x-axis.
- Curves from different scan items can appear simultaneously, regardless of the devices measured.

---

### 3. `x_mode='index'`

- X-axis scaling uses data point indices (0, 1, 2, ..., N-1).
- Allows plotting multiple curves of varying lengths in the same view.
- All curves are always compatible, as indices represent relative positions, independent of device or timestamp, it is
  up to the user to interpret the x-axis.

---

### 4. `x_mode='device'`

- User explicitly selects a device to scale the x-axis.
- The chosen device must exist in each curve’s respective scan item.
- **Live Curves**:
    - Continuously displayed if the selected device data is being measured in the current scan.
- **History Curves**:
    - Displayed only if the selected device exists in the scan item from which the history curve originates.
    - Remain **hidden** if the selected device is not present in the original scan item, reappearing only when a
      compatible device is chosen again.

---

## Key Technical Points

- Each curve stores its own independent x and y data sets (as it is defined by `pg.PlotDataItem`, allowing simultaneous
  plotting of multiple curves with different data lengths.
- Compatibility checks ensure that plotting meaningful comparisons is always possible, avoiding combinations of
  unrelated or non-compatible datasets.
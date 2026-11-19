"""
Small beam propagation simulation used as demo data for the VolumePlot widget.

A focusing optic (for example a Fresnel zone plate with a central stop) with astigmatism
in its pupil. Near the focus the field at defocus ``dz`` is the Fourier transform of the
pupil function times a defocus phase (scalar, paraxial Fraunhofer/Debye approach)::

    U(x, y; dz) = FT{ P(rho) * exp(i 2 pi W(rho, theta; dz)) }

    W = W20(dz) rho^2 + A rho^2 cos(2 theta),   W20(dz) = dz NA^2 / (2 lambda)  [waves]

Astigmatism splits the focus: the vertical direction focuses at dz = -2 A lambda / NA^2
(a horizontal line, the sagittal focus), the horizontal one at +2 A lambda / NA^2 (a
vertical line, the tangential focus), and halfway between lies the round disk of least
confusion.
"""

from __future__ import annotations

import numpy as np

from bec_widgets.widgets.plots.volume_plot.volume_data import VolumeData, VolumeMark


def focus_positions(wavelength: float, numerical_aperture: float, astigmatism: float):
    """
    Defocus of the sagittal focus, the disk of least confusion and the tangential focus.

    Args:
        wavelength (float): Wavelength in metres.
        numerical_aperture (float): Numerical aperture of the optic.
        astigmatism (float): Astigmatism coefficient A in waves.

    Returns:
        tuple[float, float, float]: Defocus in metres.
    """
    half_split = 2.0 * astigmatism * wavelength / numerical_aperture**2
    return -half_split, 0.0, half_split


def simulate_astigmatic_beam(
    wavelength: float = 1.0e-9,
    numerical_aperture: float = 2.5e-3,
    astigmatism: float = 1.0,
    central_stop: float = 0.25,
    coma: float = 0.0,
    z_range: float = 0.6e-3,
    n_z: int = 161,
    n_xy: int = 96,
    pupil_samples: int = 256,
    pupil_radius: int = 48,
) -> VolumeData:
    """
    Simulate the intensity of an astigmatic beam around its focus.

    The defaults describe a soft X-ray zone plate (1 nm, about 1.24 keV) with one wave of
    astigmatism: the two line foci lie 0.64 mm apart and the transverse pixel is 75 nm.

    Args:
        wavelength (float): Wavelength in metres.
        numerical_aperture (float): Numerical aperture of the optic.
        astigmatism (float): Astigmatism coefficient in waves (Zernike rho^2 cos 2theta).
        central_stop (float): Radius of the central stop as a fraction of the aperture.
        coma (float): Horizontal coma in waves, 0 for a pure astigmatic beam.
        z_range (float): Half range of the defocus in metres.
        n_z (int): Number of planes along the beam.
        n_xy (int): Transverse pixels kept around the axis.
        pupil_samples (int): FFT size; larger gives a wider field of view.
        pupil_radius (int): Aperture radius in FFT samples; larger gives finer pixels.

    Returns:
        VolumeData: Intensity of shape (n_xy, n_xy, n_z), axes x and y in micrometres and
        z (defocus) in millimetres, with the three foci as marks.
    """
    n = int(pupil_samples)
    u = (np.arange(n) - n // 2) / float(pupil_radius)
    px, py = np.meshgrid(u, u, indexing="ij")
    rho2 = px**2 + py**2
    pupil = ((rho2 <= 1.0) & (rho2 >= central_stop**2)).astype(float)
    # rho^2 cos(2 theta) = px^2 - py^2; the sign puts the horizontal-line focus first.
    aberration = -astigmatism * (px**2 - py**2) + coma * (3 * rho2 - 2) * px
    base = pupil * np.exp(2j * np.pi * aberration)

    z = np.linspace(-z_range, z_range, int(n_z))
    w20 = z * numerical_aperture**2 / (2.0 * wavelength)
    lo = n // 2 - n_xy // 2
    hi = lo + n_xy
    intensity = np.empty((n_xy, n_xy, z.size))
    for k, defocus in enumerate(w20):
        field = np.fft.fftshift(
            np.fft.fft2(np.fft.ifftshift(base * np.exp(2j * np.pi * defocus * rho2)))
        )
        intensity[:, :, k] = np.abs(field[lo:hi, lo:hi]) ** 2
    intensity /= intensity.max()

    pixel = wavelength * pupil_radius / (n * numerical_aperture)
    xy = (np.arange(n_xy) - n_xy // 2) * pixel * 1e6
    sagittal, least, tangential = focus_positions(wavelength, numerical_aperture, astigmatism)
    marks = [
        VolumeMark(axis=2, coordinate=sagittal * 1e3, label="Sagittal focus"),
        VolumeMark(axis=2, coordinate=least * 1e3, label="Disk of least confusion"),
        VolumeMark(axis=2, coordinate=tangential * 1e3, label="Tangential focus"),
    ]
    marks = [m for m in marks if abs(m.coordinate) <= z_range * 1e3]
    return VolumeData.from_array(
        intensity,
        x=xy,
        y=xy,
        z=z * 1e3,
        labels=("x", "y", "z"),
        units=("µm", "µm", "mm"),
        value_label="intensity",
        marks=marks,
        box_aspect=(1.0, 1.0, 4.0),
        up_axis=1,
    )

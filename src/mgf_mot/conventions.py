"""Explicit paper-to-pylcp convention translations for provisional MgF work."""

from __future__ import annotations

from enum import Enum

import numpy as np
from numpy.typing import NDArray


ComplexArray = NDArray[np.complex128]


class PaperHelicityTranslation(str, Enum):
    """Named interpretations of paper sigma labels at the pylcp beam boundary."""

    DIRECT_BEAM_RELATIVE = "direct_beam_relative"
    GLOBAL_INVERSION_DIAGNOSTIC = "global_inversion_diagnostic"


class GroundZeemanConvention(str, Enum):
    """Named interpretations of the raw XFmolecules.Xstate magnetic tensor."""

    RAW_XFMOLECULES = "raw_xfmolecules"
    PROJECT_ENERGY_SLOPE_CORRECTED = "project_energy_slope_corrected"


def paper_helicity_to_pylcp_pol(
    paper_label: str,
    *,
    translation: PaperHelicityTranslation = PaperHelicityTranslation.DIRECT_BEAM_RELATIVE,
) -> int:
    """Translate a preserved paper label to pylcp's beam-relative scalar helicity.

    The diagnostic inversion exists only to represent candidate Mapping B. It
    must never be selected without recording that explicit diagnostic mapping.
    """

    try:
        direct = {"sigma_plus": 1, "sigma_minus": -1}[paper_label]
    except KeyError as exc:
        raise ValueError(
            f"paper polarization must be explicit sigma_plus/sigma_minus, got {paper_label!r}"
        ) from exc
    if translation is PaperHelicityTranslation.DIRECT_BEAM_RELATIVE:
        return direct
    if translation is PaperHelicityTranslation.GLOBAL_INVERSION_DIAGNOSTIC:
        return -direct
    raise ValueError(f"unsupported paper-helicity translation {translation!r}")


def translate_xstate_ground_muq_for_pylcp(
    raw_muq: ComplexArray,
    *,
    convention: GroundZeemanConvention,
) -> ComplexArray:
    """Translate the raw Xstate tensor into pylcp Hamiltonian's ``mu_q`` input.

    pylcp constructs ``H = H0 - mu.B``. Under the project's documented energy
    convention, the raw Xstate tensor produces ground ``dE/dB`` signs opposite
    the source-tagged MgF g factors. The corrected mode therefore negates this
    tensor once at the Hamiltonian boundary. It does not alter the apparatus
    field, source g factors, excited tensor, or paper polarization labels.
    """

    tensor = np.asarray(raw_muq, dtype=np.complex128)
    if tensor.ndim != 3 or tensor.shape[0] != 3 or tensor.shape[1] != tensor.shape[2]:
        raise ValueError("raw Xstate mu_q must have shape (3,n,n)")
    if convention is GroundZeemanConvention.RAW_XFMOLECULES:
        return tensor.copy()
    if convention is GroundZeemanConvention.PROJECT_ENERGY_SLOPE_CORRECTED:
        return -tensor
    raise ValueError(f"unsupported ground Zeeman convention {convention!r}")

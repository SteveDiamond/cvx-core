"""
Load and parse the CVX-Core atom specifications.

This module provides the canonical representation of atoms from specs/atoms.yaml
that validators use to check library implementations.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class Curvature(Enum):
    CONSTANT = "constant"
    AFFINE = "affine"
    CONVEX = "convex"
    CONCAVE = "concave"
    UNKNOWN = "unknown"


class Sign(Enum):
    NONNEGATIVE = "nonnegative"
    NONPOSITIVE = "nonpositive"
    UNKNOWN = "unknown"
    ZERO = "zero"


class Monotonicity(Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    NONE = "none"


@dataclass
class AtomSpec:
    """Specification for a single atom."""

    name: str
    description: str
    curvature: Curvature
    sign: Sign
    arity: str  # "unary", "binary", "variadic"
    dcp_requires: Optional[str] = None  # e.g., "affine_arg"
    monotonicity: Optional[Monotonicity] = None
    parameters: list[dict] = field(default_factory=list)

    @property
    def requires_affine_arg(self) -> bool:
        return self.dcp_requires == "affine_arg"

    @property
    def requires_constant_arg(self) -> bool:
        return self.dcp_requires == "constant_arg"


@dataclass
class AtomSpecs:
    """Collection of all atom specifications."""

    affine_atoms: dict[str, AtomSpec]
    convex_atoms: dict[str, AtomSpec]
    concave_atoms: dict[str, AtomSpec]

    def get(self, name: str) -> Optional[AtomSpec]:
        """Get an atom spec by name."""
        return (
            self.affine_atoms.get(name)
            or self.convex_atoms.get(name)
            or self.concave_atoms.get(name)
        )

    def all_atoms(self) -> dict[str, AtomSpec]:
        """Get all atoms as a single dict."""
        return {**self.affine_atoms, **self.convex_atoms, **self.concave_atoms}


def _parse_curvature(raw: str | dict) -> Curvature:
    """Parse curvature from YAML."""
    if isinstance(raw, str):
        return Curvature(raw)
    # Complex curvature rules - default to the base curvature
    return Curvature.AFFINE


def _parse_sign(raw: str | dict) -> Sign:
    """Parse sign from YAML."""
    if isinstance(raw, str):
        if raw == "nonnegative":
            return Sign.NONNEGATIVE
        elif raw == "nonpositive":
            return Sign.NONPOSITIVE
        elif raw == "unknown":
            return Sign.UNKNOWN
        elif raw in ("from_value", "from_attributes", "preserve"):
            return Sign.UNKNOWN  # Context-dependent
    return Sign.UNKNOWN


def _parse_monotonicity(raw: Optional[str]) -> Optional[Monotonicity]:
    """Parse monotonicity from YAML."""
    if raw is None:
        return None
    if raw == "increasing":
        return Monotonicity.INCREASING
    elif raw == "decreasing":
        return Monotonicity.DECREASING
    elif raw == "none":
        return Monotonicity.NONE
    return None


def _parse_atom(name: str, data: dict, default_curvature: Curvature) -> AtomSpec:
    """Parse a single atom from YAML data."""
    curvature_raw = data.get("curvature", default_curvature.value)
    if isinstance(curvature_raw, dict):
        curvature = default_curvature
    else:
        curvature = Curvature(curvature_raw) if curvature_raw != "preserve" else default_curvature

    return AtomSpec(
        name=name,
        description=data.get("description", ""),
        curvature=curvature,
        sign=_parse_sign(data.get("sign", "unknown")),
        arity=data.get("arity", "unary"),
        dcp_requires=data.get("dcp_requires"),
        monotonicity=_parse_monotonicity(data.get("monotonicity")),
        parameters=data.get("parameters", []),
    )


def load_specs(specs_dir: Optional[Path] = None) -> AtomSpecs:
    """Load atom specifications from atoms.yaml."""
    if specs_dir is None:
        specs_dir = Path(__file__).parent.parent.parent / "specs"

    atoms_path = specs_dir / "atoms.yaml"
    with open(atoms_path) as f:
        data = yaml.safe_load(f)

    affine_atoms = {}
    convex_atoms = {}
    concave_atoms = {}

    # Parse affine atoms
    for name, atom_data in data.get("affine_atoms", {}).items():
        affine_atoms[name] = _parse_atom(name, atom_data, Curvature.AFFINE)

    # Parse convex atoms
    for name, atom_data in data.get("convex_atoms", {}).items():
        convex_atoms[name] = _parse_atom(name, atom_data, Curvature.CONVEX)

    # Parse concave atoms
    for name, atom_data in data.get("concave_atoms", {}).items():
        concave_atoms[name] = _parse_atom(name, atom_data, Curvature.CONCAVE)

    return AtomSpecs(
        affine_atoms=affine_atoms,
        convex_atoms=convex_atoms,
        concave_atoms=concave_atoms,
    )


if __name__ == "__main__":
    # Quick test
    specs = load_specs()
    print(f"Loaded {len(specs.all_atoms())} atoms")
    for name, atom in list(specs.all_atoms().items())[:5]:
        print(f"  {name}: {atom.curvature.value}, {atom.sign.value}")

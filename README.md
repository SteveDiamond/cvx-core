# CVX-Core

**Cross-language specifications and validation for convex optimization libraries.**

CVX-Core provides a unified foundation for the CVX* family of convex optimization libraries (cvxpy, cvxjs, cvxrust), including:

- **Canonical specifications** for atoms, DCP rules, and canonicalization
- **Cross-language validators** to ensure consistency across implementations
- **CVX file format** for portable problem definitions
- **Standard test suite** with reference optimization problems

## Why Validation Over Code Generation?

Each CVX library (cvxpy, cvxjs, cvxrust) has its own idiomatic architecture:

| Library | Architecture | Atom Definition |
|---------|-------------|-----------------|
| **cvxpy** | Class-based | Each atom is a class with methods like `is_convex()` |
| **cvxjs** | Centralized | Atoms are functions, curvature in one switch statement |
| **cvxrust** | Enum-based | Atoms are enum variants, curvature via match |

Code generation would force all libraries into the same pattern. Instead, CVX-Core:

1. **Defines the spec** - `atoms.yaml` is the source of truth for atom properties
2. **Validates implementations** - Each library is tested against the spec
3. **Catches inconsistencies** - CI ensures all libraries agree on curvature, sign, DCP rules

## Quick Start

### Running Validators

```bash
# Validate all languages
python validators/run_all.py

# Validate specific languages
python validators/run_all.py --languages python typescript

# Get detailed output
python validators/run_all.py --detailed

# JSON output for CI
python validators/run_all.py --json
```

### Example Output

```
======================================================================
CVX-CORE CROSS-LANGUAGE VALIDATION SUMMARY
======================================================================

Language                  Status     Passed     Total
-------------------------------------------------------
python/cvxpy              PASS       18         18
typescript/cvxjs          PASS       17         17
rust/cvxrust              PASS       15         15
-------------------------------------------------------

✓ All validators passed!
```

## Repository Structure

```
cvx-core/
├── specs/                    # Canonical specifications
│   ├── atoms.yaml           # Atom definitions with DCP properties
│   ├── curvature.yaml       # Curvature composition rules
│   ├── cones.yaml           # Cone types and canonicalization
│   └── problem.schema.json  # JSON schema for CVX files
│
├── validators/               # Cross-language validators
│   ├── run_all.py           # Unified test runner
│   ├── common/              # Shared spec loader
│   ├── python/              # cvxpy validator
│   ├── typescript/          # cvxjs validator
│   └── rust/                # cvxrust validator
│
├── format/                   # CVX file format
│   ├── spec.md              # Format specification
│   └── examples/            # Example .cvx files
│
├── tests/                   # Standard test problems
│   └── problems/            # Test problems by category
│
└── docs/                    # Documentation
```

## Specifications

### atoms.yaml

The canonical source of truth for atom properties:

```yaml
convex_atoms:
  norm2:
    description: "L2 norm: ||x||_2"
    curvature: convex
    sign: nonnegative
    shape: scalar
    dcp_requires: affine_arg    # Argument must be affine for DCP
    monotonicity: none          # Not monotonic
    canonicalization:
      type: soc
      aux_vars:
        - t: "scalar, nonnegative"
      constraints:
        - kind: soc
          t: t
          x: arg
      returns: t
```

### What Gets Validated

For each atom, validators check:

| Property | Description | Example |
|----------|-------------|---------|
| **Curvature** | Is the atom convex/concave/affine? | `norm2` → convex |
| **Sign** | Is the result nonnegative/nonpositive? | `norm2` → nonnegative |
| **DCP Requirements** | What curvature must arguments have? | `norm2` requires affine |
| **Composition** | Does convex(convex) work correctly? | `exp(sum_squares(x))` → convex |

### curvature.yaml

Defines how curvatures combine:

```yaml
addition:
  convex:
    convex: convex
    concave: unknown  # KEY: convex + concave = unknown
    affine: convex

composition:
  convex:
    increasing:
      convex: convex   # Increasing convex of convex = convex
      concave: unknown
```

## Writing a Validator

Each validator follows the same pattern:

```python
# 1. Load the spec
specs = load_specs()

# 2. For each atom in the spec
for atom_name, spec in specs.items():
    # 3. Create a test expression
    x = variable(5)
    expr = atom_func(x)

    # 4. Check curvature matches spec
    assert curvature(expr) == spec.curvature

    # 5. Check sign matches spec
    assert sign(expr) == spec.sign

    # 6. Check DCP requirements
    if spec.requires_affine_arg:
        convex_arg = sum_squares(x)  # Not affine
        bad_expr = atom_func(convex_arg)
        assert curvature(bad_expr) == UNKNOWN
```

## Supported Problem Classes

| Class | Description | Example Atoms |
|-------|-------------|---------------|
| **LP** | Linear Programming | sum, matmul |
| **QP** | Quadratic Programming | sum_squares, quad_form |
| **SOCP** | Second-Order Cone | norm2, quad_over_lin |
| **EXP** | Exponential Cone | exp, log, entropy |
| **POW** | Power Cone | power, sqrt |
| **SDP** | Semidefinite | lambda_max, nuclear_norm |

## CVX File Format

Portable problem definitions that work across all languages:

```json
{
  "format": "cvx",
  "version": "1.0",
  "name": "portfolio_optimization",

  "variables": {
    "w": { "shape": [10], "nonneg": true }
  },

  "parameters": {
    "mu": { "shape": [10], "data": "returns.npy" },
    "Sigma": { "shape": [10, 10], "psd": true }
  },

  "objective": {
    "sense": "maximize",
    "expression": "mu @ w - quad_form(w, Sigma)"
  },

  "constraints": ["sum(w) == 1", "w <= 0.3"]
}
```

## CI Integration

Add to your GitHub Actions workflow:

```yaml
name: CVX Validation
on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install pyyaml cvxpy

      - name: Run validators
        run: python validators/run_all.py --json
```

## Contributing

1. **Add new atoms**: Update `specs/atoms.yaml` with the atom's properties
2. **Update validators**: Add the atom to each language's validator
3. **Run validation**: `python validators/run_all.py`
4. **Add test problems**: Create `.cvx` files in `tests/problems/`

## Related Projects

- [cvxpy](https://github.com/cvxpy/cvxpy) - Python implementation
- [cvxjs](https://github.com/example/cvxjs) - TypeScript/JavaScript implementation
- [cvxrust](https://github.com/example/cvxrust) - Rust implementation

## License

Apache License 2.0

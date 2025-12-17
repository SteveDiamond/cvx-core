# CVX-Core

**Cross-language specifications, tools, and shared components for building convex optimization libraries.**

CVX-Core provides a unified foundation for the CVX* family of convex optimization libraries (cvxpy, cvxjs, cvxrust, etc.), including:

- **Shared specifications** for atoms, DCP rules, and canonicalization
- **CVX file format** for portable problem definitions
- **Code generators** for multiple target languages
- **Shared WASM solver builds** (Clarabel, HiGHS)
- **Cross-language test suite** with standard problems

## Quick Start

### Using the CVX File Format

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
    "Sigma": { "shape": [10, 10], "data": "covariance.npy", "psd": true },
    "gamma": { "value": 1.0 }
  },

  "objective": {
    "sense": "maximize",
    "expression": "mu @ w - gamma * quad_form(w, Sigma)"
  },

  "constraints": [
    "sum(w) == 1",
    "w <= 0.3"
  ]
}
```

### Loading in Different Languages

```python
# Python (cvxpy)
import cvxpy as cp
problem = cp.load("portfolio.cvx")
problem.solve()
print(problem.value)
```

```typescript
// TypeScript (cvxjs)
import { load } from 'cvxjs';
const problem = await load('portfolio.cvx');
const solution = await problem.solve();
console.log(solution.value);
```

```rust
// Rust (cvxrust)
use cvxrust::Problem;
let problem = Problem::load("portfolio.cvx")?;
let solution = problem.solve()?;
println!("{}", solution.value);
```

## Repository Structure

```
cvx-core/
├── specs/                    # Shared specifications
│   ├── atoms.yaml           # Atom definitions with DCP properties
│   ├── curvature.yaml       # Curvature composition rules
│   ├── cones.yaml           # Cone types and canonicalization
│   └── schema/              # JSON schemas for validation
│
├── format/                   # CVX file format
│   ├── spec.md              # Format specification
│   ├── typescript/          # TypeScript parser
│   ├── rust/                # Rust parser
│   ├── python/              # Python parser
│   └── examples/            # Example .cvx files
│
├── generators/               # Code generators
│   ├── typescript/          # Generate TS code from specs
│   ├── rust/                # Generate Rust code from specs
│   └── python/              # Generate Python code from specs
│
├── wasm/                    # Shared WASM solver builds
│   ├── clarabel/            # Clarabel WASM package
│   └── highs/               # HiGHS WASM package
│
├── tests/                   # Cross-language test suite
│   └── problems/            # Standard test problems (.cvx)
│
└── docs/                    # Documentation
```

## Specifications

### atoms.yaml

Defines all atoms (operations) with their DCP properties:

```yaml
convex_atoms:
  norm2:
    description: "L2 norm: ||x||_2"
    curvature: convex
    sign: nonnegative
    shape: scalar
    dcp_requires: affine_arg
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

### curvature.yaml

Defines curvature composition rules:

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

## Supported Problem Classes

| Class | Description | Example Atoms |
|-------|-------------|---------------|
| **LP** | Linear Programming | sum, matmul |
| **QP** | Quadratic Programming | sum_squares, quad_form |
| **SOCP** | Second-Order Cone | norm2, quad_over_lin |
| **EXP** | Exponential Cone | exp, log, entropy |
| **POW** | Power Cone | power, sqrt |
| **SDP** | Semidefinite | lambda_max, nuclear_norm |

## Expression DSL

The CVX format uses a simple infix expression DSL:

```
# Operators
+, -, *, /, @     # Arithmetic and matrix multiply
==, <=, >=       # Constraints

# Atoms
norm1(x), norm2(x), normInf(x)
sum(x), sum_squares(x)
quad_form(x, P), quad_over_lin(x, y)
abs(x), pos(x), neg(x)
maximum(a, b), minimum(a, b)
exp(x), log(x), entropy(x)
sqrt(x), power(x, p)
trace(X), diag(x), transpose(X)
vstack(a, b), hstack(a, b)

# Indexing
x[0], x[0:10], x[:]
```

## Test Suite

The `tests/problems/` directory contains standard optimization problems:

| Category | Problems |
|----------|----------|
| `lp/` | Basic LP, transportation, diet |
| `qp/` | Simple QP, portfolio, least squares |
| `socp/` | Norm minimization, robust regression, LASSO |
| `exp_cone/` | Maximum entropy, log-sum-exp |

Run the cross-language test suite:

```bash
python tests/runner.py --languages python,typescript,rust
```

## Code Generation

Generate language-specific code from specifications:

```bash
# Generate TypeScript expression types
python generators/typescript/generate.py --output ../cvxjs/src/generated/

# Generate Rust expression types
python generators/rust/generate.py --output ../cvxrust/src/generated/
```

## Contributing

1. Add new atoms to `specs/atoms.yaml`
2. Update curvature rules in `specs/curvature.yaml`
3. Add test problems to `tests/problems/`
4. Run the cross-language test suite

## Related Projects

- [cvxpy](https://github.com/cvxpy/cvxpy) - Python implementation
- [cvxjs](https://github.com/example/cvxjs) - TypeScript/JavaScript implementation
- [cvxrust](https://github.com/example/cvxrust) - Rust implementation

## License

MIT License

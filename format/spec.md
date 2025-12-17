# CVX Problem File Format Specification

**Version:** 1.0
**Status:** Draft
**Extension:** `.cvx` or `.cvx.json`

## Overview

The CVX format is a portable, human-readable file format for expressing convex optimization problems. It combines structured JSON for metadata and variable declarations with a simple infix expression DSL for objectives and constraints.

## Design Goals

1. **Human-readable** - Easy to write and read without special tools
2. **Expression-preserving** - Captures high-level problem structure, not just matrices
3. **DCP-aware** - Includes curvature/sign metadata for validation
4. **Portable** - Works across all CVX* implementations (cvxpy, cvxjs, cvxrust, etc.)
5. **Extensible** - Easy to add new atoms and data formats

## File Structure

```json
{
  "format": "cvx",
  "version": "1.0",
  "name": "problem_name",

  "variables": { ... },
  "parameters": { ... },
  "constants": { ... },

  "objective": { ... },
  "constraints": [ ... ],

  "metadata": { ... }
}
```

## Sections

### 1. Header

```json
{
  "format": "cvx",
  "version": "1.0",
  "name": "lasso_regression"
}
```

- `format`: Must be `"cvx"`
- `version`: Semantic version of the format (currently `"1.0"`)
- `name`: Optional human-readable problem name

### 2. Variables

Decision variables in the optimization problem.

```json
{
  "variables": {
    "x": { "shape": [100] },
    "y": { "shape": [50], "nonneg": true },
    "A": { "shape": [10, 10], "symmetric": true, "psd": true },
    "n": { "shape": [], "integer": true, "lower": 0, "upper": 10 }
  }
}
```

**Variable Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `shape` | `number[]` | Dimensions ([] for scalar, [n] for vector, [m,n] for matrix) |
| `nonneg` | `boolean` | Variable is >= 0 |
| `nonpos` | `boolean` | Variable is <= 0 |
| `lower` | `number` | Lower bound |
| `upper` | `number` | Upper bound |
| `integer` | `boolean` | Variable is integer |
| `binary` | `boolean` | Variable is in {0, 1} |
| `symmetric` | `boolean` | Matrix is symmetric |
| `psd` | `boolean` | Matrix is positive semidefinite |
| `nsd` | `boolean` | Matrix is negative semidefinite |

### 3. Parameters

Constant values that can be changed between solves (for Disciplined Parametrized Programming).

```json
{
  "parameters": {
    "A": { "shape": [50, 100], "data": "A.npy" },
    "b": { "shape": [50], "data": "b.npy" },
    "lambda": { "value": 0.1 },
    "P": {
      "shape": [10, 10],
      "data": [[1, 0.5], [0.5, 1]],
      "psd": true
    }
  }
}
```

**Parameter Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `shape` | `number[]` | Dimensions |
| `value` | `number` | Scalar value (for scalars) |
| `data` | `string` or `array` | File path or inline array |
| `nonneg` | `boolean` | All elements >= 0 |
| `psd` | `boolean` | Matrix is PSD |
| `nsd` | `boolean` | Matrix is NSD |

**Data File Formats:**

- `.npy` - NumPy binary format (dense)
- `.npz` - NumPy compressed (with `indices`, `indptr`, `values` for sparse)
- `.csv` - Comma-separated values
- `.json` - JSON array (inline or separate file)
- Base64-encoded inline data with `"data": "base64:..."`

### 4. Constants

Named constant values used in expressions.

```json
{
  "constants": {
    "ones_n": { "shape": [100], "value": 1 },
    "eye_10": { "shape": [10, 10], "identity": true },
    "target": { "shape": [50], "data": "target.csv" }
  }
}
```

### 5. Objective

```json
{
  "objective": {
    "sense": "minimize",
    "expression": "sum_squares(A @ x - b) + lambda * norm1(x)"
  }
}
```

- `sense`: Either `"minimize"` or `"maximize"`
- `expression`: Expression string using the CVX expression DSL

### 6. Constraints

```json
{
  "constraints": [
    "sum(x) == 1",
    "x >= 0",
    "A @ x <= b",
    "norm2(x) <= 10",
    { "expression": "x[0:10] >= 0.1", "name": "min_allocation" }
  ]
}
```

Constraints can be:
- Simple strings with comparison operators (`==`, `<=`, `>=`)
- Objects with `expression` and optional `name` fields

### 7. Metadata

Optional metadata about the problem.

```json
{
  "metadata": {
    "description": "L1-regularized least squares regression",
    "author": "Example User",
    "created": "2024-01-15",
    "tags": ["regression", "lasso", "sparse"],
    "expected_optimal": 12.345,
    "solution_file": "solution.npy"
  }
}
```

## Expression DSL Grammar

### Tokens

```
NUMBER     := [0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?
IDENTIFIER := [a-zA-Z_][a-zA-Z0-9_]*
OPERATOR   := + | - | * | / | @ | == | <= | >= | < | >
DELIMITER  := ( | ) | [ | ] | , | :
```

### Grammar (EBNF)

```ebnf
constraint   = expr ("==" | "<=" | ">=") expr

expr         = term (('+' | '-') term)*

term         = unary (('*' | '/' | '@') unary)*

unary        = '-' unary | power

power        = primary ('**' NUMBER)?

primary      = atom '(' args ')'
             | IDENTIFIER '[' slices ']'
             | IDENTIFIER
             | NUMBER
             | '(' expr ')'

atom         = 'norm1' | 'norm2' | 'normInf' | 'sum' | 'sum_squares'
             | 'quad_form' | 'quad_over_lin' | 'abs' | 'pos' | 'neg'
             | 'maximum' | 'minimum' | 'exp' | 'log' | 'entropy'
             | 'sqrt' | 'power' | 'trace' | 'diag' | 'transpose'
             | 'vstack' | 'hstack' | 'reshape'

args         = expr (',' expr)*

slices       = slice (',' slice)*

slice        = expr ':' expr     -- range
             | expr              -- single index
             | ':'               -- all
```

### Operator Precedence (highest to lowest)

1. `()` - Parentheses, function calls
2. `[]` - Indexing
3. `**` - Power
4. `-` - Unary negation
5. `@` - Matrix multiplication
6. `*`, `/` - Multiplication, division
7. `+`, `-` - Addition, subtraction
8. `==`, `<=`, `>=` - Comparison

### Atoms

| Atom | Signature | Description |
|------|-----------|-------------|
| `norm1(x)` | vector -> scalar | L1 norm |
| `norm2(x)` | vector -> scalar | L2 norm |
| `normInf(x)` | vector -> scalar | Infinity norm |
| `abs(x)` | any -> same | Absolute value (element-wise) |
| `sum(x)` | any -> scalar | Sum of all elements |
| `sum(x, axis)` | matrix -> vector | Sum along axis |
| `sum_squares(x)` | vector -> scalar | Sum of squared elements |
| `quad_form(x, P)` | vector, matrix -> scalar | Quadratic form x'Px |
| `quad_over_lin(x, y)` | vector, scalar -> scalar | ||x||^2 / y |
| `pos(x)` | any -> same | max(x, 0) |
| `neg(x)` | any -> same | max(-x, 0) |
| `maximum(a, b, ...)` | scalars -> scalar | Element-wise maximum |
| `minimum(a, b, ...)` | scalars -> scalar | Element-wise minimum |
| `exp(x)` | any -> same | Exponential (element-wise) |
| `log(x)` | any -> same | Natural log (element-wise) |
| `entropy(x)` | any -> same | -x * log(x) (element-wise) |
| `sqrt(x)` | any -> same | Square root (element-wise) |
| `power(x, p)` | any, scalar -> same | x^p (element-wise) |
| `trace(X)` | matrix -> scalar | Matrix trace |
| `diag(x)` | vector -> matrix or matrix -> vector | Diagonal |
| `transpose(X)` | matrix -> matrix | Transpose |
| `vstack(a, b, ...)` | matrices -> matrix | Vertical stack |
| `hstack(a, b, ...)` | matrices -> matrix | Horizontal stack |
| `reshape(x, m, n)` | any -> [m, n] | Reshape |

## Complete Example

```json
{
  "format": "cvx",
  "version": "1.0",
  "name": "portfolio_optimization",

  "variables": {
    "w": { "shape": [10], "nonneg": true }
  },

  "parameters": {
    "mu": { "shape": [10], "data": "expected_returns.npy" },
    "Sigma": { "shape": [10, 10], "data": "covariance.npy", "psd": true },
    "gamma": { "value": 1.0 }
  },

  "objective": {
    "sense": "maximize",
    "expression": "mu @ w - gamma * quad_form(w, Sigma)"
  },

  "constraints": [
    "sum(w) == 1",
    "w >= 0",
    "w <= 0.3"
  ],

  "metadata": {
    "description": "Mean-variance portfolio optimization (Markowitz)",
    "tags": ["finance", "portfolio", "quadratic"]
  }
}
```

## Validation

Parsers should validate:

1. **Structure**: All required fields present, correct types
2. **Shapes**: Expression shapes are compatible
3. **DCP**: Objective and constraints satisfy DCP rules
4. **References**: All identifiers reference declared variables/parameters/constants
5. **Data**: External data files exist and have correct shapes

## Cross-Language API

Each CVX* implementation should provide:

```
# Python
problem = cvxpy.load("problem.cvx")
problem.solve()
problem.save("solved.cvx")

// TypeScript
const problem = await cvx.load("problem.cvx");
const solution = await problem.solve();
await problem.save("solved.cvx");

// Rust
let problem = cvx::load("problem.cvx")?;
let solution = problem.solve()?;
problem.save("solved.cvx")?;
```

## Version History

- **1.0** (2024): Initial specification

# CVX-Core Validation Vision

## The Problem

The CVX ecosystem spans multiple languages—Python (cvxpy), TypeScript (cvxjs), and Rust (cvxrust). Each library implements the same mathematical concepts: atoms, curvature analysis, sign tracking, and DCP composition rules. But without a shared source of truth, inconsistencies creep in:

- Does `exp(convex_expr)` return convex or unknown?
- Is `quad_over_lin` nonnegative or just unknown sign?
- Does `minimum(concave, concave)` correctly return concave?

A user writing `norm2(x)` should get identical DCP behavior whether they're in Python, TypeScript, or Rust. Today, there's no guarantee of that.

## Why Not Code Generation?

The obvious solution is code generation: define atoms once in YAML, generate language-specific code. We rejected this approach for several reasons:

### 1. Architectural Incompatibility

Each library evolved its own idiomatic design:

| Library | Pattern | Curvature Lives In |
|---------|---------|-------------------|
| cvxpy | Class hierarchy | Methods on each atom class |
| cvxjs | Tagged unions | Centralized switch statement |
| cvxrust | Enum + impl | Match expression on Expr |

Generated code would either:
- Force all libraries into one pattern (destroying idiomatic code)
- Require three complex, divergent templates (maintenance nightmare)

### 2. Existing Codebases

cvxpy has 10+ years of development. cvxjs and cvxrust are newer but established. Code generation would require massive rewrites, breaking backward compatibility and losing years of battle-tested edge case handling.

### 3. Customization Needs

Each library has language-specific concerns:
- cvxpy integrates with NumPy's broadcasting
- cvxjs handles JavaScript's type coercion
- cvxrust leverages ownership for zero-copy operations

Generated code can't anticipate these needs.

## The Validation Approach

Instead of generating implementations, we validate them. The spec becomes a **test oracle**, not a code template.

```
┌─────────────────────────────────────────────────────────────┐
│                     specs/atoms.yaml                        │
│                   (Source of Truth)                         │
│                                                             │
│  norm2:                                                     │
│    curvature: convex                                        │
│    sign: nonnegative                                        │
│    dcp_requires: affine_arg                                 │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │   cvxpy     │     │   cvxjs     │     │  cvxrust    │
   │  validator  │     │  validator  │     │  validator  │
   └─────────────┘     └─────────────┘     └─────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │  x = var(5) │     │  x = var(5) │     │  x = var(5) │
   │  e = norm2  │     │  e = norm2  │     │  e = norm2  │
   │  check(e)   │     │  check(e)   │     │  check(e)   │
   └─────────────┘     └─────────────┘     └─────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                    ┌─────────────────┐
                    │  Unified Report │
                    │  18/18 ✓        │
                    │  17/17 ✓        │
                    │  15/15 ✓        │
                    └─────────────────┘
```

### Benefits

1. **Libraries stay idiomatic** - Each implementation can use natural patterns for its language

2. **Catches real bugs** - If cvxjs says `exp(convex)` is convex but cvxrust says unknown, the validator catches it

3. **Documents intent** - The spec becomes living documentation: "norm2 SHOULD be convex"

4. **Incremental adoption** - Validate one atom at a time; no big-bang migration

5. **CI integration** - Run on every PR to prevent regressions

## What We Validate

### Level 1: Basic Properties

For each atom, verify:

```python
# Curvature
assert curvature(norm2(x)) == CONVEX

# Sign
assert sign(norm2(x)) == NONNEGATIVE

# Shape
assert shape(norm2(x)) == SCALAR
```

### Level 2: DCP Composition

Verify that DCP rules are enforced correctly:

```python
x = variable(5)

# norm2 requires affine argument
assert curvature(norm2(x)) == CONVEX           # ✓ x is affine
assert curvature(norm2(sum_squares(x))) == UNKNOWN  # ✓ rejected

# exp is increasing, so exp(convex) should be convex
assert curvature(exp(sum_squares(x))) == CONVEX  # Composition rule
```

### Level 3: Numerical Consistency

Verify that atoms compute the same values:

```python
x_val = [1, 2, 3, 4, 5]

# All libraries should agree on numerical result
assert cvxpy_norm2(x_val) ≈ 7.416198...
assert cvxjs_norm2(x_val) ≈ 7.416198...
assert cvxrust_norm2(x_val) ≈ 7.416198...
```

### Level 4: Problem-Level Validation

Verify that solving the same `.cvx` problem yields consistent results:

```python
# portfolio.cvx defines a mean-variance optimization
cvxpy_result = solve_with_cvxpy("portfolio.cvx")
cvxjs_result = solve_with_cvxjs("portfolio.cvx")
cvxrust_result = solve_with_cvxrust("portfolio.cvx")

assert abs(cvxpy_result.value - cvxjs_result.value) < 1e-6
assert abs(cvxpy_result.value - cvxrust_result.value) < 1e-6
```

## The Specification Format

### atoms.yaml

Each atom is fully specified:

```yaml
convex_atoms:
  norm2:
    description: "L2 norm: ||x||_2 = sqrt(sum(x_i^2))"

    # DCP properties
    curvature: convex
    sign: nonnegative
    dcp_requires: affine_arg

    # Monotonicity (for composition rules)
    monotonicity:
      nonneg: increasing   # Increasing when arg >= 0
      nonpos: decreasing   # Decreasing when arg <= 0

    # Shape inference
    arity: unary
    shape: scalar

    # Canonicalization to conic form
    canonicalization:
      type: soc
      aux_vars:
        - t: {shape: scalar, nonneg: true}
      constraints:
        - kind: soc
          t: t
          x: arg
      returns: t
```

### curvature.yaml

Composition rules are explicit:

```yaml
# How curvatures combine under addition
addition:
  constant: {constant: constant, affine: affine, convex: convex, concave: concave}
  affine: {affine: affine, convex: convex, concave: concave}
  convex: {convex: convex, concave: unknown}  # KEY: convex + concave = unknown
  concave: {concave: concave}

# How curvatures compose (f(g(x)))
composition:
  convex:
    increasing: {affine: convex, convex: convex, concave: unknown}
    decreasing: {affine: convex, convex: unknown, concave: convex}
  concave:
    increasing: {affine: concave, convex: unknown, concave: concave}
    decreasing: {affine: concave, convex: concave, concave: unknown}
```

## Handling Discrepancies

When validation fails, we have a decision to make:

### 1. Spec Bug
The spec is wrong. Update `atoms.yaml`.

```yaml
# Before: incorrect
neg:
  curvature: affine  # This is negation: -x

# After: clarified
negation:
  curvature: affine  # -x

neg_part:
  curvature: convex  # max(-x, 0)
```

### 2. Implementation Bug
A library is wrong. File an issue, fix, re-validate.

### 3. Naming Mismatch
Same concept, different names. Add aliases to the validator.

```python
ATOM_ALIASES = {
    "neg": ["neg_part", "negPart"],  # cvxpy uses neg, cvxjs uses negPart
    "norm2": ["norm", "euclidean_norm"],
}
```

### 4. Intentional Divergence
A library intentionally differs (e.g., stricter DCP rules). Document it.

```yaml
norm2:
  curvature: convex
  notes:
    cvxrust: "Also accepts convex args when monotonicity allows"
```

## Roadmap

### Phase 1: Foundation (Current)
- [x] Spec loader for atoms.yaml
- [x] Python validator for cvxpy
- [x] TypeScript validator for cvxjs
- [x] Rust validator for cvxrust
- [x] Unified test runner

### Phase 2: Coverage
- [ ] Validate all 40+ atoms in spec
- [ ] Add composition rule validation
- [ ] Add shape inference validation
- [ ] Numerical consistency checks

### Phase 3: CI Integration
- [ ] GitHub Actions workflow for cvx-core
- [ ] PR checks for cvxpy/cvxjs/cvxrust
- [ ] Automated issue creation for failures

### Phase 4: Problem-Level
- [ ] CVX file format parser validation
- [ ] Cross-language solve result comparison
- [ ] Benchmark problem suite

### Phase 5: Community
- [ ] Public dashboard showing validation status
- [ ] Contributing guide for new atoms
- [ ] Spec versioning and deprecation policy

## Design Principles

### 1. Spec is Descriptive, Not Prescriptive
The spec describes what atoms SHOULD do, not how to implement them. Libraries are free to use any internal representation.

### 2. Validate Behavior, Not Code
We test observable behavior (curvature of expressions), not implementation details (class hierarchy, memory layout).

### 3. Fail Loudly
Any discrepancy should fail CI. Silent inconsistencies are worse than noisy failures.

### 4. Incremental Progress
It's okay to validate 20 atoms today and 40 tomorrow. Partial validation is better than no validation.

### 5. Trust But Verify
We trust library maintainers to implement correctly, but verify with automated tests. Trust doesn't scale; automation does.

## Conclusion

The CVX ecosystem serves researchers, engineers, and students who expect mathematical correctness. A user shouldn't need to know which language they're using to trust that `norm2(x)` is convex and nonnegative.

Validation gives us that guarantee without forcing architectural uniformity. Each library can evolve independently while maintaining semantic consistency. The spec becomes a contract, and validators are the enforcement mechanism.

This is how we scale correctness across languages.

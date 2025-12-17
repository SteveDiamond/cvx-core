/**
 * Validate cvxjs implementation against CVX-Core specifications.
 *
 * This validator tests that cvxjs's atoms behave according to the
 * canonical specifications in specs/atoms.yaml.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

// Import cvxjs (assumes it's built and available)
import {
  variable,
  constant,
  Curvature,
  curvature,
  Sign,
  sign,
  // Affine atoms
  sum,
  reshape,
  transpose,
  trace,
  diag,
  vstack,
  hstack,
  // Convex atoms
  norm1,
  norm2,
  normInf,
  abs,
  pos,
  negPart,
  maximum,
  minimum,
  sumSquares,
  quadForm,
  quadOverLin,
  exp,
  log,
  entropy,
  sqrt,
  power,
} from 'cvxjs';

// Types for the spec
interface AtomSpec {
  name: string;
  description: string;
  curvature: string;
  sign: string;
  arity: string;
  dcp_requires?: string;
}

interface ValidationCheck {
  name: string;
  passed: boolean;
  message: string;
}

interface ValidationResult {
  atomName: string;
  passed: boolean;
  checks: ValidationCheck[];
}

// Mapping from spec atom names to cvxjs functions
const ATOM_MAP: Record<string, (arg: any, arg2?: any) => any> = {
  // Affine atoms
  sum: (x) => sum(x),
  reshape: (x) => reshape(x, [1, 5]),
  transpose: (x) => transpose(x),
  trace: (x) => trace(x),
  diag: (x) => diag(x),
  vstack: (x) => vstack(x, variable(5)),
  hstack: (x) => hstack(x, variable(5)),
  // Convex atoms
  norm1: (x) => norm1(x),
  norm2: (x) => norm2(x),
  normInf: (x) => normInf(x),
  abs: (x) => abs(x),
  pos: (x) => pos(x),
  negPart: (x) => negPart(x),
  maximum: (x) => maximum(x, variable(5)),
  sumSquares: (x) => sumSquares(x),
  quadForm: (x) => quadForm(x, constant([[1, 0, 0, 0, 0], [0, 1, 0, 0, 0], [0, 0, 1, 0, 0], [0, 0, 0, 1, 0], [0, 0, 0, 0, 1]])),
  quadOverLin: (x) => {
    const y = variable(1, { nonneg: true });
    return quadOverLin(x, y);
  },
  exp: (x) => exp(x),
  // Concave atoms
  log: (x) => log(x),
  entropy: (x) => entropy(x),
  sqrt: (x) => sqrt(x),
  minimum: (x) => minimum(x, variable(5)),
  power: (x) => power(x, 0.5), // sqrt equivalent
};

// Atoms that need matrix input
const MATRIX_ATOMS = new Set(['trace', 'transpose']);

function loadSpecs(): Map<string, AtomSpec> {
  const specsPath = path.join(__dirname, '..', '..', 'specs', 'atoms.yaml');
  const content = fs.readFileSync(specsPath, 'utf-8');
  const data = yaml.load(content) as any;

  const specs = new Map<string, AtomSpec>();

  // Parse affine atoms
  for (const [name, atomData] of Object.entries(data.affine_atoms || {})) {
    const ad = atomData as any;
    specs.set(name, {
      name,
      description: ad.description || '',
      curvature: typeof ad.curvature === 'string' ? ad.curvature : 'affine',
      sign: typeof ad.sign === 'string' ? ad.sign : 'unknown',
      arity: ad.arity || 'unary',
      dcp_requires: ad.dcp_requires,
    });
  }

  // Parse convex atoms
  for (const [name, atomData] of Object.entries(data.convex_atoms || {})) {
    const ad = atomData as any;
    specs.set(name, {
      name,
      description: ad.description || '',
      curvature: 'convex',
      sign: typeof ad.sign === 'string' ? ad.sign : 'unknown',
      arity: ad.arity || 'unary',
      dcp_requires: ad.dcp_requires,
    });
  }

  // Parse concave atoms
  for (const [name, atomData] of Object.entries(data.concave_atoms || {})) {
    const ad = atomData as any;
    specs.set(name, {
      name,
      description: ad.description || '',
      curvature: 'concave',
      sign: typeof ad.sign === 'string' ? ad.sign : 'unknown',
      arity: ad.arity || 'unary',
      dcp_requires: ad.dcp_requires,
    });
  }

  return specs;
}

function createTestVariable(atomName: string) {
  if (MATRIX_ATOMS.has(atomName)) {
    return variable([3, 3]);
  }
  return variable(5);
}

function checkCurvature(expr: any, expected: string): ValidationCheck {
  const actual = curvature(expr);

  let passed = false;
  if (expected === 'constant') {
    passed = actual === Curvature.Constant;
  } else if (expected === 'affine') {
    passed = actual === Curvature.Affine || actual === Curvature.Constant;
  } else if (expected === 'convex') {
    passed =
      actual === Curvature.Convex ||
      actual === Curvature.Affine ||
      actual === Curvature.Constant;
  } else if (expected === 'concave') {
    passed =
      actual === Curvature.Concave ||
      actual === Curvature.Affine ||
      actual === Curvature.Constant;
  } else {
    passed = true; // Unknown is always acceptable
  }

  return {
    name: 'curvature',
    passed,
    message: `expected ${expected}, got ${actual}`,
  };
}

function checkSign(expr: any, expected: string): ValidationCheck {
  const actual = sign(expr);

  let passed = false;
  if (expected === 'nonnegative') {
    passed = actual === Sign.Nonnegative || actual === Sign.Zero;
  } else if (expected === 'nonpositive') {
    passed = actual === Sign.Nonpositive || actual === Sign.Zero;
  } else if (expected === 'zero') {
    passed = actual === Sign.Zero;
  } else {
    passed = true; // Unknown sign is always acceptable
  }

  return {
    name: 'sign',
    passed,
    message: `expected ${expected}, got ${actual}`,
  };
}

function validateAtom(atomName: string, spec: AtomSpec): ValidationResult {
  const checks: ValidationCheck[] = [];

  // Check if atom exists
  if (!(atomName in ATOM_MAP)) {
    checks.push({
      name: 'exists',
      passed: false,
      message: `atom '${atomName}' not mapped to cvxjs`,
    });
    return { atomName, passed: false, checks };
  }
  checks.push({ name: 'exists', passed: true, message: 'atom exists in cvxjs' });

  // Create test expression
  let expr;
  try {
    const x = createTestVariable(atomName);
    expr = ATOM_MAP[atomName]!(x);
    checks.push({ name: 'creates_expr', passed: true, message: 'expression created' });
  } catch (e) {
    checks.push({
      name: 'creates_expr',
      passed: false,
      message: `could not create expression: ${e}`,
    });
    return { atomName, passed: false, checks };
  }

  // Check curvature
  checks.push(checkCurvature(expr, spec.curvature));

  // Check sign
  checks.push(checkSign(expr, spec.sign));

  const allPassed = checks.every((c) => c.passed);
  return { atomName, passed: allPassed, checks };
}

function validateAll(specs: Map<string, AtomSpec>): ValidationResult[] {
  const results: ValidationResult[] = [];

  for (const atomName of Object.keys(ATOM_MAP)) {
    const spec = specs.get(atomName);
    if (!spec) {
      // Atom exists in cvxjs but not in spec - might use different name
      continue;
    }
    results.push(validateAtom(atomName, spec));
  }

  return results;
}

function printResults(results: ValidationResult[]): void {
  const passed = results.filter((r) => r.passed).length;
  const total = results.length;

  console.log('\n' + '='.repeat(60));
  console.log(`CVXJS Validation Results: ${passed}/${total} atoms passed`);
  console.log('='.repeat(60) + '\n');

  // Print failures first
  const failures = results.filter((r) => !r.passed);
  if (failures.length > 0) {
    console.log('FAILURES:');
    console.log('-'.repeat(40));
    for (const result of failures) {
      console.log(`\n  ${result.atomName}:`);
      for (const check of result.checks) {
        if (!check.passed) {
          console.log(`    FAIL ${check.name}: ${check.message}`);
        }
      }
    }
  }

  // Print successes
  const successes = results.filter((r) => r.passed);
  if (successes.length > 0) {
    console.log(`\nPASSED (${successes.length}):`);
    console.log('-'.repeat(40));
    for (const result of successes) {
      console.log(`  ${result.atomName}`);
    }
  }

  console.log();
}

async function main() {
  console.log('Loading CVX-Core specifications...');
  const specs = loadSpecs();
  console.log(`Loaded ${specs.size} atom specifications`);

  console.log('\nValidating cvxjs implementation...');
  const results = validateAll(specs);

  printResults(results);

  // Exit with error code if any failures
  const failures = results.filter((r) => !r.passed);
  process.exit(failures.length);
}

main().catch(console.error);

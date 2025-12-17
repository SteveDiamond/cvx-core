//! Validate cvxrust implementation against CVX-Core specifications.
//!
//! This validator tests that cvxrust's atoms behave according to the
//! canonical specifications in specs/atoms.yaml.

use std::collections::HashMap;
use std::fs;
use std::path::Path;

use cvxrust::prelude::*;
use serde::Deserialize;

/// Specification for a single atom from atoms.yaml
#[derive(Debug, Clone, Deserialize)]
struct AtomSpec {
    #[serde(default)]
    description: String,
    #[serde(default)]
    curvature: CurvatureSpec,
    #[serde(default)]
    sign: String,
    #[serde(default)]
    arity: String,
    #[serde(default)]
    dcp_requires: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
#[serde(untagged)]
enum CurvatureSpec {
    Simple(String),
    Complex(HashMap<String, serde_yaml::Value>),
    #[default]
    Unknown,
}

impl CurvatureSpec {
    fn as_str(&self) -> &str {
        match self {
            CurvatureSpec::Simple(s) => s.as_str(),
            _ => "unknown",
        }
    }
}

/// Root structure of atoms.yaml
#[derive(Debug, Deserialize)]
struct AtomsYaml {
    #[serde(default)]
    affine_atoms: HashMap<String, AtomSpec>,
    #[serde(default)]
    convex_atoms: HashMap<String, AtomSpec>,
    #[serde(default)]
    concave_atoms: HashMap<String, AtomSpec>,
}

/// Result of a single validation check
#[derive(Debug)]
struct ValidationCheck {
    name: String,
    passed: bool,
    message: String,
}

/// Result of validating a single atom
#[derive(Debug)]
struct ValidationResult {
    atom_name: String,
    passed: bool,
    checks: Vec<ValidationCheck>,
}

impl ValidationResult {
    fn failed_checks(&self) -> Vec<&ValidationCheck> {
        self.checks.iter().filter(|c| !c.passed).collect()
    }
}

/// Load atom specifications from atoms.yaml
fn load_specs(specs_dir: &Path) -> HashMap<String, (AtomSpec, &'static str)> {
    let atoms_path = specs_dir.join("atoms.yaml");
    let content = fs::read_to_string(&atoms_path).expect("Failed to read atoms.yaml");
    let data: AtomsYaml = serde_yaml::from_str(&content).expect("Failed to parse atoms.yaml");

    let mut specs = HashMap::new();

    for (name, mut spec) in data.affine_atoms {
        if matches!(spec.curvature, CurvatureSpec::Unknown) {
            spec.curvature = CurvatureSpec::Simple("affine".to_string());
        }
        specs.insert(name, (spec, "affine"));
    }

    for (name, mut spec) in data.convex_atoms {
        spec.curvature = CurvatureSpec::Simple("convex".to_string());
        specs.insert(name, (spec, "convex"));
    }

    for (name, mut spec) in data.concave_atoms {
        spec.curvature = CurvatureSpec::Simple("concave".to_string());
        specs.insert(name, (spec, "concave"));
    }

    specs
}

/// Create a test expression for the given atom
fn create_test_expr(atom_name: &str, x: &Expr) -> Option<Expr> {
    match atom_name {
        // Affine atoms
        "sum" => Some(sum(x)),
        "reshape" => Some(reshape(x, &[1, 5])),
        "transpose" => Some(transpose(x)),
        "trace" => {
            let m = variable([3, 3]);
            Some(trace(&m))
        }
        "diag" => Some(diag(x)),
        "vstack" => {
            let y = variable(5);
            Some(vstack(vec![x.clone(), y]))
        }
        "hstack" => {
            let y = variable(5);
            Some(hstack(vec![x.clone(), y]))
        }

        // Convex atoms
        "norm1" => Some(norm1(x)),
        "norm2" => Some(norm2(x)),
        "normInf" => Some(norm_inf(x)),
        "abs" => Some(abs(x)),
        "pos" => Some(pos(x)),
        "neg" | "negPart" => Some(neg_part(x)),
        "maximum" => {
            let y = variable(5);
            Some(max2(x, &y))
        }
        "sum_squares" | "sumSquares" => Some(sum_squares(x)),
        "quad_form" | "quadForm" => {
            let p = constant(nalgebra::DMatrix::identity(5, 5));
            Some(quad_form(x, &p))
        }
        "exp" => Some(exp(x)),

        // Concave atoms
        "log" => Some(log(x)),
        "entropy" => Some(entropy(x)),
        "sqrt" => Some(sqrt(x)),
        "minimum" => {
            let y = variable(5);
            Some(min2(x, &y))
        }
        "power" => Some(power(x, 0.5)), // sqrt equivalent

        _ => None,
    }
}

/// Check if expression curvature matches expected
fn check_curvature(expr: &Expr, expected: &str) -> ValidationCheck {
    let curv = expr.curvature();
    let actual = match curv {
        Curvature::Constant => "constant",
        Curvature::Affine => "affine",
        Curvature::Convex => "convex",
        Curvature::Concave => "concave",
        Curvature::Unknown => "unknown",
    };

    let passed = match expected {
        "constant" => curv.is_constant(),
        "affine" => curv.is_affine(),
        "convex" => curv.is_convex(),
        "concave" => curv.is_concave(),
        _ => true, // Unknown is always acceptable
    };

    ValidationCheck {
        name: "curvature".to_string(),
        passed,
        message: format!("expected {}, got {}", expected, actual),
    }
}

/// Check if expression sign matches expected
fn check_sign(expr: &Expr, expected: &str) -> ValidationCheck {
    let s = expr.sign();
    let actual = match s {
        cvxrust::dcp::Sign::Nonnegative => "nonnegative",
        cvxrust::dcp::Sign::Nonpositive => "nonpositive",
        cvxrust::dcp::Sign::Zero => "zero",
        cvxrust::dcp::Sign::Unknown => "unknown",
    };

    let passed = match expected {
        "nonnegative" => matches!(s, cvxrust::dcp::Sign::Nonnegative | cvxrust::dcp::Sign::Zero),
        "nonpositive" => matches!(s, cvxrust::dcp::Sign::Nonpositive | cvxrust::dcp::Sign::Zero),
        "zero" => matches!(s, cvxrust::dcp::Sign::Zero),
        _ => true, // Unknown is always acceptable
    };

    ValidationCheck {
        name: "sign".to_string(),
        passed,
        message: format!("expected {}, got {}", expected, actual),
    }
}

/// Validate a single atom against its specification
fn validate_atom(atom_name: &str, spec: &AtomSpec, category: &str) -> ValidationResult {
    let mut checks = Vec::new();

    // Create test variable
    let x = variable(5);

    // Create test expression
    let expr = match create_test_expr(atom_name, &x) {
        Some(e) => {
            checks.push(ValidationCheck {
                name: "exists".to_string(),
                passed: true,
                message: "atom exists in cvxrust".to_string(),
            });
            e
        }
        None => {
            checks.push(ValidationCheck {
                name: "exists".to_string(),
                passed: false,
                message: format!("atom '{}' not implemented in cvxrust", atom_name),
            });
            return ValidationResult {
                atom_name: atom_name.to_string(),
                passed: false,
                checks,
            };
        }
    };

    // Check curvature
    let expected_curv = if category == "affine" {
        "affine"
    } else {
        spec.curvature.as_str()
    };
    checks.push(check_curvature(&expr, expected_curv));

    // Check sign
    checks.push(check_sign(&expr, &spec.sign));

    let all_passed = checks.iter().all(|c| c.passed);
    ValidationResult {
        atom_name: atom_name.to_string(),
        passed: all_passed,
        checks,
    }
}

/// Validate all atoms in cvxrust
fn validate_all(specs: &HashMap<String, (AtomSpec, &str)>) -> Vec<ValidationResult> {
    // List of atoms we want to validate (ones implemented in cvxrust)
    let atoms_to_validate = vec![
        "sum",
        "reshape",
        "transpose",
        "trace",
        "diag",
        "vstack",
        "hstack",
        "norm1",
        "norm2",
        "normInf",
        "abs",
        "pos",
        "negPart",
        "maximum",
        "sum_squares",
        "quad_form",
        "exp",
        "log",
        "entropy",
        "sqrt",
        "minimum",
        "power",
    ];

    let mut results = Vec::new();

    for atom_name in atoms_to_validate {
        if let Some((spec, category)) = specs.get(atom_name) {
            results.push(validate_atom(atom_name, spec, category));
        }
    }

    results
}

/// Print validation results
fn print_results(results: &[ValidationResult]) {
    let passed = results.iter().filter(|r| r.passed).count();
    let total = results.len();

    println!("\n{}", "=".repeat(60));
    println!("CVXRUST Validation Results: {}/{} atoms passed", passed, total);
    println!("{}\n", "=".repeat(60));

    // Print failures first
    let failures: Vec<_> = results.iter().filter(|r| !r.passed).collect();
    if !failures.is_empty() {
        println!("FAILURES:");
        println!("{}", "-".repeat(40));
        for result in failures {
            println!("\n  {}:", result.atom_name);
            for check in result.failed_checks() {
                println!("    FAIL {}: {}", check.name, check.message);
            }
        }
    }

    // Print successes
    let successes: Vec<_> = results.iter().filter(|r| r.passed).collect();
    if !successes.is_empty() {
        println!("\nPASSED ({}):", successes.len());
        println!("{}", "-".repeat(40));
        for result in successes {
            println!("  {}", result.atom_name);
        }
    }

    println!();
}

fn main() {
    println!("Loading CVX-Core specifications...");

    // Find specs directory (relative to cvx-core root)
    let specs_dir = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .join("specs");

    let specs = load_specs(&specs_dir);
    println!("Loaded {} atom specifications", specs.len());

    println!("\nValidating cvxrust implementation...");
    let results = validate_all(&specs);

    print_results(&results);

    // Exit with error code if any failures
    let failures = results.iter().filter(|r| !r.passed).count();
    std::process::exit(failures as i32);
}

#!/usr/bin/env python3
"""
Synthetic CORE Validation Dataset Generator

Generates test cases with known ground truth for QA testing.
"""

import json
import random
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

random.seed(42)  # Reproducible


@dataclass
class CORECoordinates:
    what: float
    how: float
    where: float
    why: float
    who: float
    when: float
    valence: str
    abstraction: str
    epistemic: str
    temporal: str
    structural: str


@dataclass
class ValidationCase:
    id: str
    domain: str
    expected_type: str
    coordinates: CORECoordinates
    variant_type: str  # canonical, noisy, boundary, ambiguous, strong
    notes: str = ""


# Domain Templates (Ground Truth)
TEMPLATES = {
    "Technical Documentation": {
        "API Reference": {
            "what": 0.95, "how": 0.6, "where": 0.8, "why": 0.3, "who": 0.2, "when": 0.2,
            "valence": "neutral", "abstraction": "concrete", "epistemic": "known",
            "temporal": "present", "structural": "atomic"
        },
        "Tutorial": {
            "what": 0.7, "how": 0.95, "where": 0.5, "why": 0.6, "who": 0.2, "when": 0.8,
            "valence": "good", "abstraction": "concrete", "epistemic": "known",
            "temporal": "present", "structural": "composite"
        },
        "Concept": {
            "what": 0.85, "how": 0.4, "where": 0.3, "why": 0.9, "who": 0.1, "when": 0.2,
            "valence": "neutral", "abstraction": "abstract", "epistemic": "known",
            "temporal": "present", "structural": "relational"
        },
        "Example": {
            "what": 0.9, "how": 0.85, "where": 0.5, "why": 0.3, "who": 0.2, "when": 0.4,
            "valence": "good", "abstraction": "concrete", "epistemic": "known",
            "temporal": "present", "structural": "composite"
        },
        "Troubleshooting": {
            "what": 0.8, "how": 0.85, "where": 0.6, "why": 0.7, "who": 0.2, "when": 0.5,
            "valence": "bad", "abstraction": "concrete", "epistemic": "known",
            "temporal": "present", "structural": "composite"
        },
    },
    "Software Development Changelogs": {
        "Decision": {
            "what": 0.85, "how": 0.5, "where": 0.5, "why": 0.75, "who": 0.4, "when": 0.6,
            "valence": "good", "abstraction": "concrete", "epistemic": "known",
            "temporal": "past", "structural": "atomic"
        },
        "Implementation": {
            "what": 0.6, "how": 0.95, "where": 0.7, "why": 0.5, "who": 0.4, "when": 0.8,
            "valence": "good", "abstraction": "concrete", "epistemic": "known",
            "temporal": "past", "structural": "composite"
        },
        "Bug Report": {
            "what": 0.85, "how": 0.4, "where": 0.7, "why": 0.8, "who": 0.3, "when": 0.7,
            "valence": "bad", "abstraction": "concrete", "epistemic": "known",
            "temporal": "past", "structural": "atomic"
        },
        "Pattern": {
            "what": 0.4, "how": 0.9, "where": 0.3, "why": 0.85, "who": 0.2, "when": 0.5,
            "valence": "good", "abstraction": "abstract", "epistemic": "known",
            "temporal": "present", "structural": "relational"
        },
        "Architecture Decision": {
            "what": 0.85, "how": 0.5, "where": 0.6, "why": 0.9, "who": 0.6, "when": 0.7,
            "valence": "good", "abstraction": "abstract", "epistemic": "known",
            "temporal": "past", "structural": "composite"
        },
    },
    "Legal Documents": {
        "Statute": {
            "what": 0.9, "how": 0.3, "where": 0.5, "why": 0.4, "who": 0.6, "when": 0.5,
            "valence": "neutral", "abstraction": "abstract", "epistemic": "known",
            "temporal": "present", "structural": "atomic"
        },
        "Precedent": {
            "what": 0.85, "how": 0.3, "where": 0.4, "why": 0.75, "who": 0.7, "when": 0.7,
            "valence": "mixed", "abstraction": "concrete", "epistemic": "known",
            "temporal": "past", "structural": "atomic"
        },
        "Obligation": {
            "what": 0.9, "how": 0.4, "where": 0.5, "why": 0.5, "who": 0.9, "when": 0.7,
            "valence": "neutral", "abstraction": "concrete", "epistemic": "known",
            "temporal": "future", "structural": "atomic"
        },
        "Argument": {
            "what": 0.5, "how": 0.4, "where": 0.3, "why": 0.95, "who": 0.4, "when": 0.3,
            "valence": "neutral", "abstraction": "abstract", "epistemic": "hypothetical",
            "temporal": "present", "structural": "relational"
        },
    },
    "Personal Journal": {
        "Daily Event": {
            "what": 0.7, "how": 0.4, "where": 0.6, "why": 0.4, "who": 0.5, "when": 0.9,
            "valence": "neutral", "abstraction": "concrete", "epistemic": "known",
            "temporal": "past", "structural": "atomic"
        },
        "Reflection": {
            "what": 0.5, "how": 0.3, "where": 0.4, "why": 0.9, "who": 0.4, "when": 0.6,
            "valence": "mixed", "abstraction": "abstract", "epistemic": "hypothetical",
            "temporal": "present", "structural": "relational"
        },
        "Relationship Entry": {
            "what": 0.5, "how": 0.3, "where": 0.4, "why": 0.9, "who": 0.85, "when": 0.6,
            "valence": "mixed", "abstraction": "abstract", "epistemic": "hypothetical",
            "temporal": "present", "structural": "relational"
        },
        "Goal": {
            "what": 0.8, "how": 0.7, "where": 0.4, "why": 0.6, "who": 0.3, "when": 0.85,
            "valence": "good", "abstraction": "concrete", "epistemic": "hypothetical",
            "temporal": "future", "structural": "atomic"
        },
    },
}


def add_noise(value: float, noise_level: float = 0.1) -> float:
    """Add controlled noise to a coordinate value."""
    noise = random.uniform(-noise_level, noise_level)
    return max(0.0, min(1.0, value + noise))


def generate_canonical(domain: str, type_name: str, template: Dict) -> CORECoordinates:
    """Generate exact template values."""
    return CORECoordinates(**template)


def generate_noisy(domain: str, type_name: str, template: Dict) -> CORECoordinates:
    """Generate template with ±0.05-0.10 noise."""
    coords = template.copy()
    for key in ["what", "how", "where", "why", "who", "when"]:
        coords[key] = add_noise(coords[key], noise_level=random.uniform(0.05, 0.10))
    return CORECoordinates(**coords)


def generate_boundary(domain: str, type_name: str, template: Dict) -> CORECoordinates:
    """Generate weaker signals (reduce by 15-25%)."""
    coords = template.copy()
    for key in ["what", "how", "where", "why", "who", "when"]:
        reduction = random.uniform(0.15, 0.25)
        coords[key] = max(0.0, coords[key] * (1 - reduction))
    return CORECoordinates(**coords)


def generate_strong(domain: str, type_name: str, template: Dict) -> CORECoordinates:
    """Generate amplified signals (increase by 5-10%)."""
    coords = template.copy()
    for key in ["what", "how", "where", "why", "who", "when"]:
        boost = random.uniform(0.05, 0.10)
        coords[key] = min(1.0, coords[key] * (1 + boost))
    return CORECoordinates(**coords)


def generate_ambiguous(domain: str, type_name: str, template: Dict,
                       all_types: Dict[str, Dict]) -> CORECoordinates:
    """Generate coordinates between two types."""
    # Pick another type from same domain
    other_types = [t for t in all_types.keys() if t != type_name]
    if not other_types:
        return generate_noisy(domain, type_name, template)

    other_type = random.choice(other_types)
    other_template = all_types[other_type]

    # Blend 60/40
    coords = template.copy()
    for key in ["what", "how", "where", "why", "who", "when"]:
        coords[key] = 0.6 * coords[key] + 0.4 * other_template[key]

    return CORECoordinates(**coords)


def generate_validation_set() -> List[ValidationCase]:
    """Generate complete validation set."""
    cases = []
    case_id = 1

    for domain, types in TEMPLATES.items():
        for type_name, template in types.items():
            # Generate 5 variants per type
            variants = [
                ("canonical", generate_canonical, "Exact template values"),
                ("noisy", generate_noisy, "Template ± 5-10% noise"),
                ("boundary", generate_boundary, "Reduced signals (15-25%)"),
                ("strong", generate_strong, "Amplified signals (5-10%)"),
                ("ambiguous", lambda d, t, tmp: generate_ambiguous(d, t, tmp, types),
                 "Blended with another type"),
            ]

            for variant_type, generator, notes in variants:
                coords = generator(domain, type_name, template)

                case = ValidationCase(
                    id=f"test_{case_id:03d}",
                    domain=domain,
                    expected_type=type_name,
                    coordinates=coords,
                    variant_type=variant_type,
                    notes=notes
                )
                cases.append(case)
                case_id += 1

    return cases


def main():
    """Generate and save validation set."""
    print("Generating synthetic validation set...")
    cases = generate_validation_set()

    # Convert to JSON
    output = {
        "metadata": {
            "total_cases": len(cases),
            "domains": list(TEMPLATES.keys()),
            "types_per_domain": {d: list(t.keys()) for d, t in TEMPLATES.items()},
            "variant_types": ["canonical", "noisy", "boundary", "strong", "ambiguous"],
            "seed": 42
        },
        "test_cases": [
            {
                **asdict(case),
                "coordinates": asdict(case.coordinates)
            }
            for case in cases
        ]
    }

    # Save to file
    output_file = "validation-set.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Generated {len(cases)} test cases")
    print(f"📄 Saved to {output_file}")

    # Print summary
    print("\n📊 Distribution:")
    for domain in TEMPLATES.keys():
        domain_cases = [c for c in cases if c.domain == domain]
        print(f"  {domain}: {len(domain_cases)} cases")
        for type_name in TEMPLATES[domain].keys():
            type_cases = [c for c in domain_cases if c.expected_type == type_name]
            print(f"    - {type_name}: {len(type_cases)}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate the RCPP OWL 2 structure and HermiT inferred artifact."""
from pathlib import Path

from pyshacl import validate
from rdflib import Graph, OWL, RDF

HERE = Path(__file__).resolve().parent

final = Graph().parse(HERE / "rcpp-owl-final.ttl", format="turtle")
inferred = Graph().parse(HERE / "rcpp-owl-inferred.ttl", format="turtle")
owl2_shapes = Graph().parse(HERE / "owl2-shapes.ttl", format="turtle")

inferred_only = set(inferred) - set(final)
functional = {
    subject
    for subject, predicate, obj in inferred_only
    if predicate == RDF.type and obj == OWL.FunctionalProperty
}
if len(functional) != 5:
    raise SystemExit(
        f"[ERROR] expected 5 inferred functional properties, found {len(functional)}"
    )

conforms, _, report = validate(
    final,
    shacl_graph=owl2_shapes,
    inference="rdfs",
)
if not conforms:
    raise SystemExit(f"[ERROR] OWL 2 structural SHACL\n{report}")
print("[PASS] OWL 2 structural SHACL conforms: rcpp-owl-final.ttl")

print(
    "[OK] OWL 2 structural SHACL and inferred artifact check passed; "
    f"final={len(final)}, inferred={len(inferred)}, "
    f"inferred-functional={len(functional)}"
)

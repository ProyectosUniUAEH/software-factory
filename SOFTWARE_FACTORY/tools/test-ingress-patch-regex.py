#!/usr/bin/env python3
"""Unit checks for ingress patch regex (blank-line tolerant)."""
import re
import sys

# Mirror of AppDeployer._INGRESS_PATCH_RE
INGRESS_PATCH_RE = re.compile(
    r'^([ ]*)(?:#[^\n]*\n\s*)?- target:\s*\n'
    r'(?:[ \t]*\n)*'
    r'\s+kind:\s*Ingress\s*\n'
    r'(?:[ \t]*\n)*'
    r'\s+name:\s*([\w-]+)\s*\n'
    r'(?:[ \t]*\n)*'
    r'\s+patch:\s*\|-\s*\n'
    r'((?:[ \t]*\n|[ \t]+.*\n)*)',
    re.MULTILINE,
)

SAMPLE_SPACED = """apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
patches:
  - target:

      kind: Ingress

      name: lab-react

    patch: |-

      - op: replace

        path: /spec/rules/0/host

        value: staging-lab-react.example.com

      - op: replace

        path: /spec/tls/0/hosts/0

        value: staging-lab-react.example.com
"""

SAMPLE_COMPACT = """patches:
  - target:
      kind: Ingress
      name: lab-react
    patch: |-
      - op: replace
        path: /spec/rules/0/host
        value: staging-lab-react.example.com
"""


def main():
    for label, sample in (("spaced", SAMPLE_SPACED), ("compact", SAMPLE_COMPACT)):
        m = INGRESS_PATCH_RE.search(sample)
        assert m, f"no match for {label}"
        assert m.group(2) == "lab-react", m.group(2)
        body = m.group(3) or ""
        assert "op: replace" in body, body
        assert "staging-lab-react.example.com" in body, body
        # Full block replace must consume host lines (no leftovers)
        rebuilt = sample[: m.start()] + "REPLACED\n" + sample[m.end() :]
        assert "op: replace" not in rebuilt, f"leftover ops in {label}: {rebuilt}"
        print(f"OK {label}")
    print("ALL_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

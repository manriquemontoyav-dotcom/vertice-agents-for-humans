# Public Candidate Checklist

The gate evaluates exactly 38 checks. A failed check makes the result `RED`.

## Package and security

- Candidate directory exists, is nonempty, and remains within size limits.
- No symlinks, Git history, caches, environment files, databases, private
  material, key files, common credential patterns, or oversized files.

## Official submission surface

- Root README and MIT or Apache-2.0 license.
- Architecture document with Mermaid or a rendered architecture image.
- Installation, execution, and testing instructions.
- Dependency manifest declaring Strands Agents.
- GitHub Actions workflow.
- A usable UI entrypoint and Python source importing Strands.

## Judge comprehension

- README identifies VÉRTICE, Agents for Humans, and the approved tagline.
- Problem, audience, impact, features, architecture, installation, running,
  and testing sections are present.
- Strands intervention/interrupt use is explained.
- Exact-action binding and replay/mutation defense are explained.
- `REAL`, `SIMULATED`, and `REPLAY` classifications are explicit.

## Provenance, licensing, and truthfulness

- Human and AI-assisted contributions are distinguished.
- Pre-existing work disclosure is explicit.
- Third-party notices cover Strands.
- Security/privacy documentation exists.
- No unresolved drafting markers, placeholder URLs, unsupported patent claims,
  production-readiness claims, or prize-guarantee claims remain.

## Required follow-on gates

This checklist cannot replace:

1. `REAL_STRANDS APPLICATION_E2E` evidence from the exact candidate.
2. Browser E2E against the same process and exact source.
3. CI on the exact commit used for the video.
4. Human review of the public repository and Devpost submission.

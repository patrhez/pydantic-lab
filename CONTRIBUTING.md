# Contribution Rules

## Write clear English

Use ASD-STE100-inspired language for most prose. This is a writing target, not a claim of certified compliance.

- Give each sentence one main purpose. Use active voice and short paragraphs.
- Use one term for one concept. Keep necessary technical names such as checkpoint and tool call.
- State conditions before actions. Prefer direct verbs to abstract nouns.
- Do not invent terms, add promotional claims, or repeat the same requirement across guides.
- Explain why a design exists. Mark untested behavior as planned.

## Keep documents aligned

The [specification](docs/specification.md) defines requirements. Learning guides explain those requirements. Verified code and tests establish implemented behavior. A guide must not claim that a proposed design already works.

When code changes, update the affected guide and the [implementation status](docs/implementation-status.md) in the same commit. If a requirement changes, update the specification and [decision record](docs/decisions.md). Update both the Excalidraw source and its rendered image when a diagram changes.

Before a documentation commit, check local links, requirement coverage, code references, diagrams, spelling, and whitespace. Review semantics manually; a link checker cannot prove design consistency.

## Commit changes

Use Conventional Commits 1.0.0 for every commit:

```text
docs: describe agent execution and recovery
feat(cli): add queue input during a run
fix(runtime): reject an expired approval
```

Use an imperative English subject. Add a scope only when it identifies a clear component. Do not add unsupported test claims or unrelated changes. Preserve normal Git hooks and signing settings.

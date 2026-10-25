# Repository Instructions

- Write all repository content in English, including documentation, code, comments, configuration descriptions, test names, logs, and UI text.
- This is a standalone Pydantic AI learning lab. Do not depend on sibling repositories or their shared packages at runtime.
- Read `docs/specification.md` before implementation. Its status must distinguish proposed defaults from confirmed requirements.
- Prefer public Pydantic AI and Pydantic AI Harness capabilities. Verify APIs against the pinned versions before implementing adapters; do not depend on private CLAI internals.
- Keep framework behavior visible and document the responsibility boundary between framework capabilities and application orchestration.
- Do not begin feature implementation until the specification has been reviewed and approved by the owner.
- Preserve unrelated changes and never print or commit credentials.
- Run unit tests, integration tests, and authorized live DeepSeek smoke tests before declaring implementation complete.
- Use Conventional Commits 1.0.0 for every commit, with an imperative English subject.
- Keep documentation and implementation aligned in the same change. Follow `CONTRIBUTING.md` for writing and review.

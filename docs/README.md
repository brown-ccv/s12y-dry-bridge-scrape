# Documentation Structure

This directory contains all project documentation, plans, and architectural decisions.

## Structure

```
docs/
├── constitution.md           # Code style guide and project principles
├── flavor.md                # Interaction style guide
└── plans/                   # Project plans and tasks
    └── 001-simplify-retry-logic/
        ├── plan.md          # High-level plan and approach
        └── tasks.md         # Detailed task breakdown
```

## Plans

Each plan gets its own numbered directory with a descriptive slug:

- `001-simplify-retry-logic/` - Replaced metadata-based retry with database gap detection

### Plan Naming Convention

Plans are numbered sequentially with a descriptive slug:
- Format: `NNN-descriptive-slug/`
- Example: `001-simplify-retry-logic/`
- Example: `002-add-authentication-layer/`
- Example: `003-optimize-database-queries/`

### Plan Contents

Each plan directory should contain:
- `plan.md` - High-level overview, approach, and benefits
- `tasks.md` - Atomic, testable tasks with verification steps
- Any supporting documents or diagrams (optional)

## Core Documents

### constitution.md

Defines the project's coding standards, style preferences, and architectural principles. All code changes should follow these guidelines.

### flavor.md

Defines the interaction style for AI assistance. Maintains the Captain/Engineering Officer dynamic while keeping technical work professional.

## Usage

When starting a new feature or refactoring:

1. Create a new plan directory: `docs/plans/NNN-your-feature-slug/`
2. Write a `plan.md` describing the approach
3. Break it down into tasks in `tasks.md`
4. Reference `constitution.md` to ensure consistency
5. Execute tasks incrementally with testing

This structure helps maintain project history and provides context for future work.

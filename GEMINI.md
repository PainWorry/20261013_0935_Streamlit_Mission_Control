# Workspace Guidelines & Communication Invariants

## 1. Transparency & Status Reporting Invariant
Whenever providing intermediate feedback, dispatching background subagents, scheduling timers, or executing multi-step tasks:

1. **Explicit Current Action (What you are doing)**:
   - State clearly and concisely the exact action currently being performed (e.g., *"Running automated verification suite"*, *"Invoking C-Suite subagent for rubric evaluation"*, *"Writing code changes to module X"*).
   - Never leave the user guessing what background process is active.

2. **Explicit Expected Completion / Milestone (When you will report back)**:
   - Always state the trigger, milestone, or estimated timeframe when you will return with the final result or next update (e.g., *"I will report back as soon as the subagent finishes (estimated ~30–45 seconds)"*, *"Next update after test execution completes"*).

3. **UI Transparency Principle**:
   - Because background tool calls, timers, and subagents are not always visually conspicuous in the user's UI, every message handed off to the user while work is pending must explicitly bridge this visibility gap.

---

## 2. Enterprise Proposal & Architecture Invariant
When developing system architecture proposals, executive trade-off benchmarks, FinOps budget models, or C-Suite technical deliverables:
- **Activate Custom Skill**: Always follow the standards defined in [`.agents/skills/faang-architect-proposal/SKILL.md`](.agents/skills/faang-architect-proposal/SKILL.md).
- **Core Principles Enforced by Skill**:
  1. Native Mermaid diagrams over raw ASCII art.
  2. Numerical C-Suite comparison scores out of 100 with clear executive verdicts.
  3. FinOps 3-tier sensitivity overrun buffers (Baseline, +25% Buffer, +50% Surge).
  4. Regional vs. Global Cloud data residency evaluation for executive guidance.

---

## 3. Automated Bug & Remediation Changelog Invariant (FAANG Hybrid Two-Tier Standard)
Whenever any bug, functional defect, regression, or architectural vulnerability is identified, investigated, or remediated:
1. **Mandatory Automatic Logging**:
   - The AI assistant MUST immediately create or append the issue to `CHANGELOG.md` in the root of the active project repository.
   - Zero user prompt required — this is an autonomous, non-negotiable invariant.
2. **Hybrid Two-Tier Structure Required**:
   - **Tier 1 (Executive Summary Canvas)**: A concise tabular overview for CEO/CTO with Columns: `Incident ID`, `Timestamp`, `Severity (P0-P3)`, `Component`, and `Business Impact / One-line Resolution`.
   - **Tier 2 (Granular Architectural Root Cause Analysis - FAANG/Google SRE Standard)**:
     - `Incident Summary & Symptoms`: Clear description of what the user experienced.
     - `Technical Root Cause (RCA)`: Deep dive into the failure mechanics (e.g. WebSocket teardown, race conditions, storage collision, state machine flaws).
     - `Remediation & Architecture Changes`: Specific files, functions, and diff logic altered.
     - `Verification & Invariant Guardrails`: Automated or manual test procedures to ensure zero regression.

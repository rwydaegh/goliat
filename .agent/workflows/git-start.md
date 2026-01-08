---
description: Start a feature
---

# GOLIAT Workflow: Start

This command initiates the development workflow for a new feature or fix.

## Core Principle: Writing Style

** this is a critical instruction for you.** All text you generate (issues, commits, PRs) must follow the "nonchalantly professional" style.

-   **Be concise and direct.** Use an economy of words. Get straight to the point.
-   **Sound like a senior developer.** Confident, intelligent, and efficient. Avoid AI-like verbosity, apologies, or overly formal language.
-   **Focus on the essentials.** It's okay to be brief, even to the point of vagueness if the context is clear to the user. Correct grammar, but don't obsess over punctuation.
-   **Issue Tense**: Always write issues in the present or future tense.

## Step 1: Define the Task (Create an Issue)

Before any code is written, we must define the task. I will create a GitHub issue that clearly outlines the goal.

**My Process for Creating a Good Issue:**

1.  **Ask Clarifying Questions (CRITICAL ROO INSTRUCTION):**
    *   My primary goal is to fully understand the task before creating an issue. I **must** ask you questions to fill in any gaps.
    *   I will **not** guess implementation details or make assumptions.
    *   I will ask about the Goal, Acceptance Criteria, Scope, and Examples.

2.  **Draft the Issue and Select Labels**:
    *   **Title**: Based on your answers, I will create a title following **Conventional Commits** format: `feat(scope): description` or `fix(scope): description`.
    *   **Body**: I will write a clear description to a temporary `.txt` file. This file will be used as the issue body. I will show you the content before creating the issue.
    *   **Labels**: I will determine the appropriate labels from the list below and confirm them with you.
    *   **Assignee**: I will always assign the issue to `rwydaegh`.

3.  **Execution**: Once you approve the drafted content and labels, I will use the `gh issue create --body-file <file>.txt` command to post it to the repository. I will delete the temporary file immediately after.

### Standard Issue Body Structure

A clear, concise summary of the goal.

-   **Acceptance Criteria**: A short list of what must be true for the task to be considered complete.
-   **Scope**: Briefly outline what is and is not included.
-   **Example**: If applicable, a quick code snippet or usage example. This is very optional and can be skipped if it's difficult to provide.

### Available Labels

-   **Type**: `bug`, `documentation`, `enhancement`, `question`, `refactor`, `testing`, `ci/cd`
-   **Status**: `status: in progress`, `status: blocked`
-   **Priority**: `priority: critical`, `priority: high`, `priority: medium`, `priority: low`
-   **Area**: `area: near-field`, `area: far-field`, `area: config`, `area: setup`, `area: simulation`, `area: results`, `area: analysis`, `area: gui`
-   **Interface**: `interface:Sim4Life`, `interface:oSPARC`, `interface:PySide6`

## Step 2: Create a Branch

Once the issue is created and we have a clear goal, I will create a dedicated branch for this work.

**My Process for Creating a Branch:**
1.  **Naming**: I will use a descriptive naming convention: `feat/<short-description>` or `fix/<short-description>`. I will **always** specify a custom branch name when using `gh issue develop` (e.g., `gh issue develop <issue-number> --name feat/<short-description>`) rather than accepting the default branch name.
2.  **Linking**: I will link the branch directly to the issue.
3.  **Execution**: I will use the `gh issue develop` command with a custom branch name.

After completing these steps, I will notify you that the setup is complete, and we can begin the development work on the new branch. I will also verify that I am on the correct branch before proceeding with any work.

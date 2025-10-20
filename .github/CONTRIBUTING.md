# Contributing to GOLIAT

Contributions are welcome. This guide outlines the process.

## Core Principles

-   **Code Style**: We use `black` for formatting and `flake8` for linting. Run `black .` before committing.
-   **Testing**: New features require corresponding tests. Run `pytest` to validate your changes.
-   **Commits**: Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (`feat:`, `fix:`, etc.).

## Workflow for Internal Contributors

This is the standard workflow for those with write access.

1.  **Open an Issue**: Define the task in an issue. A clear goal is essential. Appropriate labels (`bug`, `enhancement`, `area: near-field`, etc.) will be assigned to categorize the work.
2.  **Create a Branch**: Create a branch from the `master` branch, linked to the issue.
    -   Name it `feature/<description>` or `fix/<description>`.
3.  **Develop**: Make your changes. Commit logically.
4.  **Open a Pull Request**: When ready, open a PR against the `master` branch. Reference the issue in the description (e.g., `Closes #42`).
5.  **Merge**: Once CI passes, use **Squash and Merge**. This keeps the `master` history clean. The branch will be deleted after merging.
6.  **Clean Up**: Pull the latest `master` and delete your local branch.

## Workflow for External Contributors

Follow this process if you do not have write access.

1.  **Fork the Repository**: Create a personal fork.
2.  **Clone Your Fork**:
    ```bash
    git clone https://github.com/YOUR_USERNAME/goliat.git
    cd goliat
    ```
3.  **Create a Branch**:
    ```bash
    git checkout -b feature/my-cool-feature
    ```
4.  **Develop**: Make your changes, following the core principles.
5.  **Push to Your Fork**:
    ```bash
    git push -u origin feature/my-cool-feature
    ```
6.  **Open a Pull Request**: Open a PR from your fork to the `rwydaegh/goliat` `master` branch. Provide a clear description of your changes.

---

Thank you for contributing.

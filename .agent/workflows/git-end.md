---
description: End the feature
---

# GOLIAT Workflow: End

This command finalizes the development workflow for a feature or fix.

## Core Principle: Writing Style

**this is a critical instruction for you.** All text you generate (issues, commits, PRs) must follow the "nonchalantly professional" style.

-   **Be concise and direct.** Use an economy of words. Get straight to the point.
-   **Sound like a senior developer.** Confident, intelligent, and efficient. Avoid AI-like verbosity, apologies, or overly formal language.
-   **Focus on the essentials.** It's okay to be brief, even to the point of vagueness if the context is clear to the user. Correct grammar, but don't obsess over punctuation.

## Step 1: Pre-Commit Checks

Before committing, I will run pre-commit checks to ensure code quality and formatting.

**My Process for Pre-Commit Checks:**
1.  **Run Pre-Commit**: I will execute `python -m pre_commit run --all-files` to check all files in the repository.
2.  **Stage Changes**: If the pre-commit hooks modify any files, I will automatically stage them.

## Step 2: Review and Commit Changes

First, I will analyze all the changes made on the current branch.

**My Process for Committing:**
1.  **Verify Branch**: Before committing, I will run `git branch --show-current` to ensure I am not on the `master` branch.
2.  **Analyze Diff**: I will run `git diff` to get a complete picture of all modifications. I will intelligently cluster these changes to understand the scope of the feature or fix.
2.  **Check for Unstaged Files**: I will look for any files that should potentially be added to `.gitignore` (e.g., large data files, logs) and ask for your confirmation before proceeding.
3.  **Write Commit Message**: I will create a file named `commit_message.txt`. The message will follow the **Conventional Commits** standard. The first line (title) **must** start with the type, scope, and issue number, like `feat(scope): Title (#<issue-number>)`. The body will reference the issues it closes.
4.  **Stage and Commit**: I will stage all approved files and then create the commit using the specific command to ensure correct authorship:
    ```bash
    git commit --author="rwydaegh" -F commit_message.txt
    ```
5.  **Clean Up**: Delete the `commit_message.txt` file after the commit.

## Step 3: Keep Branch Updated

To avoid merge conflicts and keep the history clean, I will regularly update my feature branch.

**My Process for Updating the Branch:**
1.  **Rebase on Master**: I will use `git pull --rebase origin master` to update my branch. This avoids unnecessary merge commits.

## Step 4: Create and Merge Pull Request

With the work committed, I will create and automatically merge a Pull Request. This is a modern, efficient approach that streamlines the process.

**My Process for Creating and Merging a PR:**
1.  **Create and Auto-Merge PR**: I will use a single `gh pr create` command. This command will:
    *   Automatically push the current branch to the remote repository.
    *   Create the pull request with a title and body that links to and closes the original issue.
    *   Set the PR to "auto-merge" as soon as all CI checks have passed.
    *   Use the "Squash and Merge" strategy.
    *   Delete the branch after merging.

    ```bash
    gh pr create --title "feat(scope): Title" --body "Closes #<issue-number>"
    gh pr merge <pr-number> --squash --delete-branch
    ```
2.  **Monitor Status**: I will monitor the PR's status using `gh pr checks` to ensure a successful merge.

## Step 5: Clean Up Local Environment

Finally, I will clean up the local repository to complete the cycle.

**My Process for Cleaning Up:**
1.  **Switch to Master**: I will check out the `master` branch.
2.  **Pull Changes**: I will pull the latest version of `master` using rebase to maintain a clean history.
3.  **Delete Local Branch**: I will delete the now-merged local feature branch.
    ```bash
    git checkout master
    git pull --rebase
    git branch -d <branch-name>
    ```

After these steps, the workflow is complete, and the repository is ready for the next task.

## Step 6: Documentation Review

As a final step, I will review the documentation to ensure it remains consistent with any changes I've made.

**My Process for Documentation Review:**
1.  **Read Docs**: I will recursively read the `docs/` directory and the [`configs/config_documentation.md`](configs/documentation.md) file.
2.  **Assess Changes**: I will determine if any modifications to the documentation are necessary based on the code changes. My focus will be on readability and essential information, avoiding pedantic or overly verbose updates.
3.  **Apply and Label**: If changes are made, I will commit them and ensure a `docs` label is added to the pull request. It's also possible that no changes are needed.

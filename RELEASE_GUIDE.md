# Release Guide for v1.0

This guide walks through releasing GOLIAT v1.0. **DO NOT execute these commands yet** - review and prepare first.

## Pre-Release Checklist

Before creating the release, ensure:

- [ ] All code changes are committed to main branch
- [ ] Tests pass locally (`pytest`)
- [ ] Documentation builds successfully (`mkdocs serve`)
- [ ] CHANGELOG.md is updated with release notes
- [ ] Version numbers are consistent (if you have a `__version__` in code)
- [ ] GitHub Actions are enabled in repository settings

## Step-by-Step Release Process

### 1. Update CHANGELOG.md

Edit `CHANGELOG.md` to move items from `[Unreleased]` to `[1.0.0]` with today's date:

```markdown
## [1.0.0] - 2024-01-14

### Added
- Comprehensive documentation site with MkDocs
- GitHub Actions for CI/CD (testing, linting, docs deployment)
- Pre-commit hooks for code quality
- Issue and PR templates
...
```

### 2. Commit Changelog Update

```bash
git add CHANGELOG.md
git commit -m "chore: Prepare v1.0.0 release"
git push origin main
```

### 3. Create and Push Git Tag

```bash
# Create annotated tag (recommended for releases)
git tag -a v1.0.0 -m "Release version 1.0.0

Initial stable release of GOLIAT with:
- Automated EMF dosimetry simulations
- Near-field and far-field support
- Cloud execution via oSPARC
- Comprehensive documentation
- CI/CD workflows"

# Push tag to GitHub
git push origin v1.0.0
```

**Important**: The tag MUST start with `v` (e.g., `v1.0.0`) to trigger the release workflow!

### 4. Automatic Release Creation

Once you push the tag, the `.github/workflows/release.yml` workflow will automatically:
1. Detect the new tag
2. Generate a changelog from git commits since the last tag (or all commits if first release)
3. Create a GitHub Release with:
   - Release title: v1.0.0
   - Auto-generated changelog
   - Manual changelog from CHANGELOG.md
   - Draft: false (published immediately)

### 5. Verify Release

After pushing the tag:
1. Go to GitHub Actions tab - watch the "Release" workflow run
2. Once complete, go to Releases page: `https://github.com/rwydaegh/goliat/releases`
3. You should see "v1.0.0" release with full notes

### 6. Optional: Announce Release

After release is live:
- Update README badge (if you want a "Latest Release" badge)
- Announce in Discussions or relevant channels
- Share with collaborators

## Alternative: Creating Release Manually

If you prefer manual control or want to test first:

```bash
# Create tag locally (don't push yet)
git tag -a v1.0.0 -m "Release v1.0.0"

# Review the tag
git show v1.0.0

# When ready, push
git push origin v1.0.0
```

Or create release entirely through GitHub UI:
1. Go to Releases page → "Create a new release"
2. Click "Choose a tag" → Type "v1.0.0" → "Create new tag on publish"
3. Fill in release title and notes
4. Click "Publish release"

This will also trigger the release workflow.

## Troubleshooting

### Release workflow didn't trigger
- Check that tag name starts with `v` (case-sensitive)
- Verify `.github/workflows/release.yml` exists and is valid
- Check repository Actions settings (must be enabled)

### Want to delete/redo a release
```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin :refs/tags/v1.0.0

# Delete GitHub Release (do manually on GitHub)
# Then recreate tag and push again
```

### Testing the release workflow
Create a test tag first:
```bash
git tag -a v0.9.0-rc1 -m "Release candidate 1"
git push origin v0.9.0-rc1
```

Watch if workflow triggers correctly, then delete test release.

## Post-Release Tasks

After v1.0.0 is released:
- [ ] Update CHANGELOG.md to add `[Unreleased]` section at top
- [ ] Consider adding a release badge to README
- [ ] Tag any related documentation versions
- [ ] Archive old development branches if needed

## Quick Command Summary

```bash
# Complete release in 3 commands:
git add CHANGELOG.md
git commit -m "chore: Prepare v1.0.0 release"
git push origin main

git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Then wait for GitHub Actions to create the release automatically!
```

---

**Ready to release?** Review this guide, test locally, then execute when you're confident!

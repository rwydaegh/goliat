# Contributing to GOLIAT

Thank you for your interest in contributing to GOLIAT! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/goliat.git
   cd goliat
   ```
3. **Set up the development environment**:
   ```bash
   # Ensure Sim4Life Python is in PATH (see README)
   source .bashrc

   # Install dependencies
   pip install -r requirements.txt

   # Install development tools
   pip install black flake8 isort pytest pre-commit

   # Set up pre-commit hooks
   pre-commit install
   ```

## Development Workflow

### Branching Strategy

- `main`/`master`: Stable release branch
- `develop`: Development branch (if used)
- Feature branches: `feature/your-feature-name`
- Bug fixes: `bugfix/issue-description`
- Hotfixes: `hotfix/critical-fix`

### Making Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes** following our code style (see below)

3. **Test your changes**:
   ```bash
   # Run tests
   pytest

   # Run linters
   black --check .
   flake8 .
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   Use clear, descriptive commit messages:
   - `Add feature: description`
   - `Fix bug: description`
   - `Update docs: description`
   - `Refactor: description`

5. **Push to your fork**:
   ```bash
   git push origin feature/my-new-feature
   ```

6. **Create a Pull Request** on GitHub

## Code Style Guidelines

### Python Style

We follow [PEP 8](https://pep8.org/) with some modifications:

- **Formatter**: [Black](https://black.readthedocs.io/) (line length: 120)
- **Import sorting**: [isort](https://pycqa.github.io/isort/)
- **Linter**: [Flake8](https://flake8.pycqa.org/)

Run formatters before committing:
```bash
black .
isort .
```

### Code Conventions

- Use type hints where possible:
  ```python
  def process_data(config: Config, phantom_name: str) -> Dict[str, Any]:
      ...
  ```

- Write docstrings for all public functions/classes (Google style):
  ```python
  def calculate_sar(field_data: np.ndarray, conductivity: float) -> float:
      """Calculate SAR from field data.

      Args:
          field_data: Electric field magnitude array.
          conductivity: Tissue conductivity (S/m).

      Returns:
          SAR value in W/kg.
      """
      ...
  ```

- Use meaningful variable names:
  ```python
  # Good
  phantom_setup = PhantomSetup(config, "thelonious", logger, logger)

  # Avoid
  ps = PhantomSetup(c, "thelonious", l, l)
  ```

- Keep functions focused (single responsibility)
- Use `_log()` from `LoggingMixin` with appropriate `log_type`

## Testing

### Writing Tests

- Place tests in `tests/` directory
- Name test files `test_*.py`
- Use pytest fixtures for reusable setup
- Mock external dependencies (e.g., Sim4Life API)

Example:
```python
def test_config_inheritance(dummy_configs):
    config = Config(dummy_configs["base_dir"], "near_field_config.json")
    assert config.get_setting("study_type") == "near_field"
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_config.py

# With coverage
pytest --cov=src
```

## Documentation

### Updating Docs

- Documentation is in `docs/` using MkDocs
- Use Markdown with proper formatting
- Add code examples where helpful
- Update `mkdocs.yml` nav if adding new pages

Build docs locally:
```bash
mkdocs serve  # Visit http://127.0.0.1:8000
```

### Docstring Style

Use Google-style docstrings:
```python
def my_function(param1: str, param2: int) -> bool:
    """Brief description.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: If param2 is negative.
    """
```

## Pull Request Process

1. **Ensure all tests pass** and code is formatted
2. **Update documentation** if adding/changing features
3. **Add tests** for new functionality
4. **Update CHANGELOG.md** under `[Unreleased]`
5. **Fill out the PR template** completely
6. **Link related issues** (e.g., "Closes #123")

### PR Review Checklist

Reviewers will check:
- [ ] Code follows style guidelines
- [ ] Tests pass and coverage is adequate
- [ ] Documentation is updated
- [ ] CHANGELOG is updated
- [ ] No merge conflicts
- [ ] Commit messages are clear

## Reporting Issues

Use GitHub Issues with the appropriate template:
- **Bug Report**: For unexpected behavior
- **Feature Request**: For new features or enhancements

Provide:
- Clear description
- Steps to reproduce (for bugs)
- Environment details (OS, Python/Sim4Life versions)
- Logs or screenshots
- Minimal config to reproduce

## Code of Conduct

This project adheres to the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Questions?

- **Documentation**: https://rwydaegh.github.io/goliat/
- **Issues**: https://github.com/rwydaegh/goliat/issues
- **Discussions**: Use GitHub Discussions for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License (see [LICENSE](LICENSE)).

---

Thank you for contributing to GOLIAT! 🎉

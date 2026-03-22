# 🤝 Contributing to AI Testing Agent

**Thank you for your interest in contributing!** 🎉

We love contributions from the community. Whether you're fixing a bug, adding a feature, or improving documentation, every contribution helps make AI Testing Agent better for everyone.

---

## 📋 Table of Contents

- [Ways to Contribute](#-ways-to-contribute)
- [Getting Started](#-getting-started)
- [Development Guidelines](#-development-guidelines)
- [Pull Request Process](#-pull-request-process)
- [Code of Conduct](#-code-of-conduct)
- [Areas We Need Help](#-areas-we-need-help)
- [Questions?](#-questions)

---

## 🌟 Ways to Contribute

There are many ways to contribute to AI Testing Agent:

### 🐛 Report Bugs
Found a bug? Please [open an issue](https://github.com/yourusername/ai-testing-agent/issues/new?template=bug_report.md) with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)
- Error messages or logs

### 💡 Suggest Features
Have an idea? We'd love to hear it! [Open a feature request](https://github.com/yourusername/ai-testing-agent/issues/new?template=feature_request.md) with:
- Clear description of the feature
- Why it would be useful
- Example use cases
- Possible implementation approach (optional)

### 📝 Improve Documentation
Documentation improvements are always welcome:
- Fix typos or unclear explanations
- Add examples or tutorials
- Improve API documentation
- Translate documentation

### 🔀 Submit Code Changes
Code contributions follow our [pull request process](#-pull-request-process):
- Bug fixes
- New features
- Performance improvements
- Code refactoring
- Test improvements

### ⭐ Star the Repository
A simple star helps us grow and shows your support!

### 📢 Spread the Word
Share AI Testing Agent with others:
- Write a blog post
- Tweet about it
- Present at a meetup
- Recommend to colleagues

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **Git**
- **pip** or **pipenv**

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:

# Clone your fork
git clone https://github.com/YOUR_USERNAME/ai-testing-agent.git
cd ai-testing-agent

# Add upstream remote
git remote add upstream https://github.com/yourusername/ai-testing-agent.git

# Verify remotes
git remote -v
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (including development tools)
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If available

# Or install in development mode
pip install -e .
```

**Development Dependencies:**
```bash
# Install testing and linting tools
pip install pytest pytest-cov black flake8 mypy isort
```

### 3. Verify Setup

```bash
# Run tests to ensure everything works
pytest tests/ -v

# Run the CLI
python cli.py --help

# Try a basic command
python cli.py usage
```

---

## 💻 Development Guidelines

### Code Style

We follow PEP 8 and use automated tools to maintain code quality.

#### **Formatting**
```bash
# Format code with Black (line length: 100)
black . --line-length 100

# Sort imports with isort
isort .
```

#### **Linting**
```bash
# Check code style
flake8 . --max-line-length 100

# Type checking
mypy ai_testing_agent.py
```

#### **Style Guidelines**
- Use **Black** for automatic formatting
- Follow **PEP 8** naming conventions
- Add **type hints** for function parameters and returns
- Write **clear docstrings** (Google style)
- Keep functions focused and small (<50 lines ideally)
- Use meaningful variable names

**Example:**
```python
def generate_test_cases(requirements: str, max_cases: int = 10) -> List[Dict[str, Any]]:
    """
    Generate test cases from requirements.
    
    Args:
        requirements: Requirements text to analyze
        max_cases: Maximum number of test cases to generate
        
    Returns:
        List of test case dictionaries with id, name, and description
        
    Raises:
        ValueError: If requirements is empty
    """
    if not requirements:
        raise ValueError("Requirements cannot be empty")
    
    # Implementation here
    return test_cases
```

### Testing

We maintain high test coverage to ensure code quality.

#### **Writing Tests**
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=ai_testing_agent --cov-report=html

# Run specific test file
pytest tests/test_agent.py -v

# Run specific test
pytest tests/test_agent.py::test_parse_requirements -v
```

#### **Test Guidelines**
- Write tests for **all new features**
- Maintain **80%+ code coverage**
- Use **pytest fixtures** for reusable test data
- Name tests descriptively: `test_<function>_<scenario>_<expected_result>`
- Test both success and failure cases
- Mock external dependencies (API calls, file I/O)

**Example Test:**
```python
import pytest
from ai_testing_agent import AITestingAgent

def test_parse_requirements_with_valid_input():
    """Test that valid requirements are parsed correctly."""
    agent = AITestingAgent()
    requirements = "Feature: User login"
    
    result = agent.parse_requirements(requirements)
    
    assert result is not None
    assert 'features' in result
    assert len(result['features']) > 0

def test_parse_requirements_with_empty_input():
    """Test that empty requirements raise ValueError."""
    agent = AITestingAgent()
    
    with pytest.raises(ValueError, match="Requirements cannot be empty"):
        agent.parse_requirements("")
```

### Documentation

Good documentation helps users and contributors alike.

#### **Update Documentation When:**
- Adding new features
- Changing existing functionality
- Fixing bugs that affect user-facing behavior
- Adding new dependencies or requirements

#### **Documentation Guidelines**
- Update **README.md** for major features
- Add **docstrings** to all public functions/classes
- Update **CHANGELOG.md** with your changes
- Add **examples** for new features
- Keep documentation **clear and concise**

#### **Docstring Example:**
```python
class AITestingAgent:
    """
    Autonomous AI agent for test automation.
    
    This agent automates the entire testing workflow from requirements
    to test execution and reporting.
    
    Attributes:
        api_key: Anthropic API key for Claude AI
        output_dir: Directory for generated tests and reports
        
    Example:
        >>> agent = AITestingAgent()
        >>> result = agent.run_autonomous(requirements_text)
        >>> print(f"Generated {result['test_cases']} test cases")
    """
```

### Commit Messages

Write clear, descriptive commit messages following conventional commits.

#### **Format:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

#### **Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

#### **Examples:**
```bash
feat(agent): Add support for PDF requirements parsing

Implemented PDF parsing using PyPDF2 library. Users can now
provide requirements in PDF format.

Closes #123
```

```bash
fix(cli): Correct usage stats display in session summary

The usage percentage was showing incorrectly in the stats output.
Fixed calculation to properly handle session tracking.

Fixes #456
```

---

## 🔀 Pull Request Process

### 1. Create a Branch

```bash
# Update your fork
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Write code following our [style guidelines](#code-style)
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

```bash
# Run tests
pytest tests/ -v

# Check code style
black . --check
flake8 .

# Verify everything works
python cli.py run example_requirements.txt
```

### 3. Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "feat: Add support for YAML requirements"

# Push to your fork
git push origin feature/your-feature-name
```

### 4. Submit Pull Request

1. Go to the [repository on GitHub](https://github.com/yourusername/ai-testing-agent)
2. Click "Pull Requests" → "New Pull Request"
3. Click "compare across forks"
4. Select your fork and branch
5. Fill out the PR template:
   - **Title:** Clear, descriptive title
   - **Description:** What changes you made and why
   - **Related Issues:** Link any related issues
   - **Testing:** How you tested your changes
   - **Screenshots:** If UI changes
   - **Checklist:** Complete the checklist

### 5. Code Review

- Respond to feedback promptly
- Make requested changes
- Push updates to the same branch
- Request re-review when ready

### 6. Merge

Once approved, a maintainer will merge your PR. Thank you for contributing! 🎉

---

## 📜 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for everyone.

### Our Standards

**Expected behavior:**
- Be respectful and constructive
- Use welcoming and inclusive language
- Focus on what's best for the community
- Show empathy towards others
- Give and receive feedback gracefully

**Unacceptable behavior:**
- Harassment or discriminatory language
- Trolling or insulting comments
- Personal or political attacks
- Publishing private information
- Unprofessional conduct

### Enforcement

Instances of unacceptable behavior may be reported via [GitHub Issues](https://github.com/dannicolau7/ai-testing-agent/issues). All complaints will be reviewed and investigated.

---

## 🎯 Areas We Need Help

Looking to contribute but not sure where to start? Here are areas where we'd love help:

### 🌐 High Priority

- **Multi-language Support**
  - Support for Java test generation
  - JavaScript/TypeScript support
  - Support for other testing frameworks (JUnit, Jest, etc.)

- **Better CLI UX**
  - Interactive mode for requirement input
  - Progress bars for long operations
  - Better error messages
  - Colored output

- **Report Templates**
  - More HTML themes
  - PDF report generation
  - Customizable report templates
  - Dashboard/metrics view

### 📚 Medium Priority

- **Documentation**
  - Video tutorials
  - More code examples
  - Best practices guide
  - Troubleshooting guide
  - API documentation improvements

- **Testing**
  - Integration tests
  - End-to-end tests
  - Performance benchmarks
  - More test fixtures

- **Examples**
  - Real-world examples
  - Industry-specific examples (e-commerce, fintech, etc.)
  - CI/CD integration examples
  - Docker examples

### 🔌 Low Priority (But Still Welcome!)

- **Framework Integrations**
  - GitHub Actions integration
  - GitLab CI templates
  - Jenkins pipeline examples
  - Azure DevOps integration

- **Quality of Life**
  - VS Code extension
  - PyCharm plugin
  - Shell completions (bash, zsh)
  - Configuration file support

- **Performance**
  - Faster test generation
  - Parallel test execution
  - Caching mechanisms
  - Memory optimization

### 🐛 Always Needed

- Bug fixes (check [open issues](https://github.com/yourusername/ai-testing-agent/issues?q=is%3Aissue+is%3Aopen+label%3Abug))
- Documentation improvements
- Test coverage improvements
- Code cleanup and refactoring

**Don't see something you want to work on?** [Open an issue](https://github.com/yourusername/ai-testing-agent/issues/new) to discuss it!

---

## ❓ Questions?

### Get Help

- **GitHub Issues:** [Report bugs or request features](https://github.com/dannicolau7/ai-testing-agent/issues)
- **GitHub Discussions:** [Ask questions and share ideas](https://github.com/dannicolau7/ai-testing-agent/discussions)
- **Stack Overflow:** Tag questions with `ai-testing-agent`

### Resources

- [README](README.md) - Project overview
- [Documentation](docs/README.md) - Full documentation
- [License](LICENSE) - MIT License
- [Code of Conduct](#-code-of-conduct) - Community guidelines

---

## 📝 License

By contributing to AI Testing Agent, you agree that your contributions will be licensed under the **MIT License**.

This means:
- Your code will be open source
- Others can use, modify, and distribute it
- You retain copyright of your contributions
- The project can use your contributions freely

See the [LICENSE](LICENSE) file for full details.

---

## 🙏 Recognition

Contributors are recognized in several ways:

- Listed in [CONTRIBUTORS.md](CONTRIBUTORS.md)
- Mentioned in release notes
- Tagged in release announcements
- Featured on our website (major contributions)

---

## 🎉 Thank You!

Your contributions make AI Testing Agent better for everyone. Whether it's code, documentation, bug reports, or spreading the word, every contribution is valued.

**Happy coding!** 🚀

---

<div align="center">

Made with ❤️ by the AI Testing Agent Community

[Star on GitHub](https://github.com/dannicolau7/ai-testing-agent) • [Report Bug](https://github.com/dannicolau7/ai-testing-agent/issues) • [Request Feature](https://github.com/dannicolau7/ai-testing-agent/issues)

</div>

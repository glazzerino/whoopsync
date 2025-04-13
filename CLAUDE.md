# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands
- Setup: `python -m venv venv && source venv/bin/activate && pip install -e .`
- Run tests: `pytest`
- Run single test: `pytest test_file.py::test_function`
- Lint: `flake8 *.py`
- Type check: `mypy *.py`

## Code Style Guidelines
- **Formatting**: Use Black for automatic formatting with 88 character line length
- **Linting**: Follow PEP 8 style guidelines, enforced by flake8
- **Type Annotations**: Use strict typing with mypy
- **Imports**: Group imports: standard library, third-party, local; sort alphabetically within groups
- **Naming**: 
  - Use snake_case for variables, functions, methods
  - Use CamelCase for classes
  - Use UPPER_CASE for constants
- **Error Handling**: Always use specific exceptions with descriptive messages
- **Docstrings**: Google style docstrings for all public functions, classes, and methods

## Project Structure
This project works with the Whoop API to sync and manipulate Whoop health data locally.
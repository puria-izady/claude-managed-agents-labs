# Bug-fixer sample repo

A tiny Python project with **one planted bug** and a failing test. It exists so
Lab 12 (Bug-Fixer Agent That Opens a Pull Request) has a real, self-contained
repo to work against: the agent reproduces the failure, fixes the minimum code,
opens a PR.

## Use this template (do not fork)

Click the green **Use this template** button at the top of this repo on GitHub
and create a copy under **your own account**. You need a repo you own so you can:

- mint a fine-grained token scoped to it, and
- let the agent push a branch and open a PR into it.

Forking works too, but "Use this template" gives you a clean history and no
upstream link, which is what the lab expects.

## What is in here

```
src/math.py          factorial() with a planted off-by-one bug
tests/test_math.py   four tests; test_factorial_five fails until you fix it
pyproject.toml       puts the repo root on sys.path for pytest
```

## Reproduce the bug locally (optional)

```bash
pip install pytest
pytest
```

You should see `test_factorial_five` fail with `assert 24 == 120`. The other
three tests pass. The bug is a single-character off-by-one in `src/math.py`;
the lab's agent will find and fix it for you.

## Then run Lab 12

Point the lab at your copy of this repo (`GITHUB_REPO_URL`) and run it. The
agent clones, runs pytest to reproduce the failure, edits `src/math.py`,
confirms the tests go green, and opens a pull request with the fix.

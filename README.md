# Claude Managed Agents — Labs

Hands-on lab specs and runnable reference code for the *Mastering Claude
Managed Agents* Udemy course.

<!-- TODO: add the Udemy course link once published -->

## What's in here

```
lab_NN_*.md   lab specs — the step-by-step instructions you follow
code/         runnable reference implementation for each lab
```

Each lab has a `lab_NN_*.md` spec (the authoritative walkthrough) and a
matching `code/lab_NN_*/` folder with the code you end up with at the end of
the lab. Setup notes live in [`code/README.md`](code/README.md).

## Labs

| # | Lab |
|---|---|
| 1 | Console agent |
| 2 | First Python session |
| 3 | Research agent |
| 4 | Data-science environment |
| 5 | Streaming REPL |
| 6 | Linear/Slack via MCP + Vault |
| 7 | Human-in-the-loop |
| 8 | Financial analyst (`xlsx`) |
| 9 | DCF with outcome rubric |
| 10 | Customer-support memory |
| 11 | Research → Write → Fact-check |
| 12 | Bug-fixer that opens a PR |
| 13 | Capstone: personal research agent |

## Getting started

```bash
cd code
./setup_uv.sh
cp .env.example .env
# edit .env with your own ANTHROPIC_API_KEY and any lab-specific keys
```

See [`code/README.md`](code/README.md) for the full setup, per-lab env vars,
and how to run each lab as a script or notebook.

## License

MIT, see [LICENSE](LICENSE). The lab code is reference material for learning
purposes: adapt it freely for your own projects.

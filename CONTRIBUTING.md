# Contributing to nano-ai

## Quick start

```bash
git clone https://github.com/axelmitschidev/nano-ai.git
cd nano-ai
./setup.sh
```

## Workflow

1. Fork the repo
2. Create a branch from `dev`: `git checkout -b feat/my-feature dev`
3. Make your changes
4. Push and open a PR against `dev` (not `main`)

`main` is production. All work goes through `dev` first.

## Adding a tool

1. Create `app/tools/my_tool.py`
2. Write your functions (return strings)
3. Add a `register_tools()` function that calls `registry.register()`
4. Import and call it in `app/tools/__init__.py`

See existing tools for examples.

## Code style

- Run `ruff check app/` before pushing
- Keep functions short and focused
- Type hints on function signatures
- Docstrings on modules, not every function

## Architecture rules

- **Single Responsibility** — one concern per file
- **Open/Closed** — extend via registry, don't modify core
- **No framework dependencies** — stdlib + httpx + playwright only
- Tools must return strings (the LLM reads them)
- All file operations sandboxed to `app/workspace/`

"""Static analysis tests for readmegen.py marimo cell structure.

Checks that no marimo cell errors are present:
  - multiple-definitions: a name is defined (imported or assigned) in more than one cell
  - missing-definitions: a cell parameter is not returned by any other cell
"""
import ast
from collections import defaultdict


def parse_cells(source: str):
    """Return a list of dicts describing each @app.cell function.

    Each dict has:
      - lineno: int
      - params: list[str]   -- declared function parameters (excluding 'self')
      - definitions: set[str] -- names defined (imported / assigned at top scope)
                                  excluding names starting with '_'
      - returns: set[str]   -- names in the return tuple/value
    """
    tree = ast.parse(source)
    cells = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        decs = [ast.unparse(d) for d in node.decorator_list]
        if not any("app.cell" in d for d in decs):
            continue

        params = [a.arg for a in node.args.args if a.arg not in ("self",)]

        definitions: set[str] = set()
        for stmt in node.body:
            for n in ast.walk(stmt):
                if isinstance(n, ast.Import):
                    for alias in n.names:
                        name = alias.asname or alias.name.split(".")[0]
                        if not name.startswith("_"):
                            definitions.add(name)
                elif isinstance(n, ast.ImportFrom):
                    for alias in n.names:
                        name = alias.asname or alias.name
                        if not name.startswith("_"):
                            definitions.add(name)
                elif isinstance(n, ast.Assign):
                    for target in n.targets:
                        if isinstance(target, ast.Name) and not target.id.startswith("_"):
                            definitions.add(target.id)
                elif isinstance(n, (ast.AnnAssign,)):
                    if isinstance(n.target, ast.Name) and not n.target.id.startswith("_"):
                        definitions.add(n.target.id)

        returns: set[str] = set()
        # look for the last return statement
        for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                val = stmt.value
                if isinstance(val, ast.Tuple):
                    for elt in val.elts:
                        if isinstance(elt, ast.Name):
                            returns.add(elt.id)
                elif isinstance(val, ast.Name):
                    returns.add(val.id)
                # also handle calls like mo.md(content) — treat them as no named return
                break

        cells.append(
            {
                "lineno": node.lineno,
                "params": params,
                "definitions": definitions,
                "returns": returns,
            }
        )

    return cells


def test_no_multiple_definitions():
    """No name should be defined (imported/assigned) in more than one cell."""
    with open("readmegen.py") as fh:
        source = fh.read()

    cells = parse_cells(source)
    definition_cells: dict[str, list[int]] = defaultdict(list)
    for cell in cells:
        for name in cell["definitions"]:
            definition_cells[name].append(cell["lineno"])

    conflicts = {k: v for k, v in definition_cells.items() if len(v) > 1}
    assert not conflicts, (
        "critical[multiple-definitions]: the following variables are defined in "
        f"more than one cell:\n"
        + "\n".join(f"  '{k}' in cells at lines {v}" for k, v in conflicts.items())
    )


def test_no_missing_definitions():
    """Every cell parameter must be returned by at least one other cell."""
    with open("readmegen.py") as fh:
        source = fh.read()

    cells = parse_cells(source)

    # collect all names ever returned across all cells
    all_returns: set[str] = set()
    for cell in cells:
        all_returns.update(cell["returns"])

    missing: list[tuple[int, str]] = []
    for cell in cells:
        for param in cell["params"]:
            if param not in all_returns:
                missing.append((cell["lineno"], param))

    assert not missing, (
        "critical[missing-definitions]: the following cell parameters are not "
        "returned by any cell:\n"
        + "\n".join(f"  '{name}' used in cell at line {lineno}" for lineno, name in missing)
    )


if __name__ == "__main__":
    import sys

    failed = 0
    for test_fn in [test_no_multiple_definitions, test_no_missing_definitions]:
        try:
            test_fn()
            print(f"PASS  {test_fn.__name__}")
        except AssertionError as exc:
            print(f"FAIL  {test_fn.__name__}\n      {exc}")
            failed += 1
    sys.exit(failed)

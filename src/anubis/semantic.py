"""Semantic diff detection using AST analysis."""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from .models import SemanticOperation


@dataclass
class Symbol:
    """A code symbol (function, class, variable)."""

    name: str
    kind: str  # "function", "class", "method", "variable"
    line: int
    signature: str | None = None


def extract_python_symbols(content: str) -> list[Symbol]:
    """Extract symbols from Python source code."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    symbols = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = ", ".join(arg.arg for arg in node.args.args)
            symbols.append(Symbol(
                name=node.name,
                kind="function",
                line=node.lineno,
                signature=f"def {node.name}({args})",
            ))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(
                getattr(base, "id", getattr(base, "attr", "?"))
                for base in node.bases
            )
            symbols.append(Symbol(
                name=node.name,
                kind="class",
                line=node.lineno,
                signature=f"class {node.name}({bases})" if bases else f"class {node.name}",
            ))

    return symbols


def extract_js_symbols(content: str) -> list[Symbol]:
    """Extract symbols from JavaScript/TypeScript using regex (simple approach)."""
    symbols = []

    # Function declarations
    for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", content):
        name, args = match.groups()
        line = content[:match.start()].count("\n") + 1
        symbols.append(Symbol(
            name=name,
            kind="function",
            line=line,
            signature=f"function {name}({args})",
        ))

    # Arrow functions assigned to const/let
    for match in re.finditer(r"(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>", content):
        name = match.group(1)
        line = content[:match.start()].count("\n") + 1
        symbols.append(Symbol(
            name=name,
            kind="function",
            line=line,
            signature=f"const {name} = (...) =>",
        ))

    # Class declarations
    for match in re.finditer(r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?", content):
        name, base = match.groups()
        line = content[:match.start()].count("\n") + 1
        sig = f"class {name} extends {base}" if base else f"class {name}"
        symbols.append(Symbol(
            name=name,
            kind="class",
            line=line,
            signature=sig,
        ))

    return symbols


def extract_symbols(filepath: str, content: str) -> list[Symbol]:
    """Extract symbols from source code based on file extension."""
    ext = Path(filepath).suffix.lower()

    if ext == ".py":
        return extract_python_symbols(content)
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        return extract_js_symbols(content)
    else:
        return []


def detect_semantic_operations(
    filepath: str,
    old_content: str | None,
    new_content: str | None,
) -> list[SemanticOperation]:
    """Detect semantic operations between old and new versions of a file."""
    operations = []

    if old_content is None and new_content is not None:
        # New file
        symbols = extract_symbols(filepath, new_content)
        for sym in symbols:
            operations.append(SemanticOperation(
                op_type=f"add_{sym.kind}",
                target=f"{filepath}:{sym.name}",
                details={"signature": sym.signature, "line": sym.line},
            ))
        return operations

    if old_content is not None and new_content is None:
        # Deleted file
        symbols = extract_symbols(filepath, old_content)
        for sym in symbols:
            operations.append(SemanticOperation(
                op_type=f"delete_{sym.kind}",
                target=f"{filepath}:{sym.name}",
                details={"signature": sym.signature},
            ))
        return operations

    if old_content is None or new_content is None:
        return operations

    # Compare symbols
    old_symbols = {s.name: s for s in extract_symbols(filepath, old_content)}
    new_symbols = {s.name: s for s in extract_symbols(filepath, new_content)}

    old_names = set(old_symbols.keys())
    new_names = set(new_symbols.keys())

    # Added symbols
    for name in new_names - old_names:
        sym = new_symbols[name]
        operations.append(SemanticOperation(
            op_type=f"add_{sym.kind}",
            target=f"{filepath}:{name}",
            details={"signature": sym.signature, "line": sym.line},
        ))

    # Removed symbols
    for name in old_names - new_names:
        sym = old_symbols[name]
        operations.append(SemanticOperation(
            op_type=f"delete_{sym.kind}",
            target=f"{filepath}:{name}",
            details={"signature": sym.signature},
        ))

    # Modified symbols (same name, different signature)
    for name in old_names & new_names:
        old_sym = old_symbols[name]
        new_sym = new_symbols[name]
        if old_sym.signature != new_sym.signature:
            operations.append(SemanticOperation(
                op_type=f"modify_{new_sym.kind}",
                target=f"{filepath}:{name}",
                details={
                    "old_signature": old_sym.signature,
                    "new_signature": new_sym.signature,
                    "line": new_sym.line,
                },
            ))

    # Detect potential renames (removed + added with similar signatures)
    removed = [old_symbols[n] for n in old_names - new_names]
    added = [new_symbols[n] for n in new_names - old_names]

    for old_sym in removed:
        for new_sym in added:
            if old_sym.kind == new_sym.kind:
                # Simple heuristic: same kind, similar line numbers
                if abs(old_sym.line - new_sym.line) < 5:
                    operations.append(SemanticOperation(
                        op_type="rename",
                        target=f"{filepath}:{old_sym.name}",
                        details={
                            "old_name": old_sym.name,
                            "new_name": new_sym.name,
                            "kind": old_sym.kind,
                        },
                    ))
                    break

    return operations


def analyze_diff_semantics(
    changed_files: list[tuple[str, str | None, str | None]],
) -> list[SemanticOperation]:
    """Analyze semantic changes across multiple files.

    Args:
        changed_files: List of (filepath, old_content, new_content) tuples

    Returns:
        List of semantic operations detected
    """
    all_operations = []

    for filepath, old_content, new_content in changed_files:
        operations = detect_semantic_operations(filepath, old_content, new_content)
        all_operations.extend(operations)

    return all_operations

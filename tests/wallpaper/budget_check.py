#!/usr/bin/env python3
"""Budget gate. Exit 0 = within budget, 1 = over.

elif is represented in Python's AST as a nested If inside orelse. An if/elif/elif
chain therefore measures as depth 3 while reading as depth 1. Collapsing those is
correcting the instrument, not relaxing the budget — real nesting still counts.
"""
import ast, sys

FILE_MAX, FUNC_MAX, DEPTH_MAX = 150, 40, 3
BLOCK = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
fails = []

def depth(node, d=0):
    worst = d
    for child in ast.iter_child_nodes(node):
        nd = d + 1 if isinstance(child, BLOCK) else d
        # an elif: the If is the sole element of the parent If's orelse -> same level
        if isinstance(node, ast.If) and isinstance(child, ast.If) and node.orelse == [child]:
            nd = d
        worst = max(worst, depth(child, nd))
    return worst

for path in sys.argv[1:]:
    src = open(path).read()
    tree = ast.parse(src)
    n = len(src.splitlines())
    print(f"{path}: {n} lines (max {FILE_MAX}) {'PASS' if n <= FILE_MAX else 'FAIL'}")
    if n > FILE_MAX:
        fails.append(f"{path} is {n} lines")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ln = node.end_lineno - node.lineno + 1
            if ln > FUNC_MAX:
                fails.append(f"{path}:{node.name} is {ln} lines")
            print(f"  fn {node.name}: {ln} (max {FUNC_MAX}) {'PASS' if ln <= FUNC_MAX else 'FAIL'}")
    d = depth(tree)
    print(f"  max nesting: {d} (max {DEPTH_MAX}) {'PASS' if d <= DEPTH_MAX else 'FAIL'}")
    if d > DEPTH_MAX:
        fails.append(f"{path} nests {d} deep")

print("\nBUDGET FAIL: " + "; ".join(fails) if fails else "\nBUDGETS PASS")
sys.exit(1 if fails else 0)

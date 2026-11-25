"""Show that app.py changes since Phase 0 are presentation-only: strip layout wrappers and compare ASTs per function."""
import ast, difflib, sys

def st_call(node, attr):
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == attr
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "st")

class Normalize(ast.NodeTransformer):
    def visit_With(self, node):
        self.generic_visit(node)
        items = [i for i in node.items if not (st_call(i.context_expr, "container") or st_call(i.context_expr, "spinner"))]
        if not items:
            return node.body
        node.items = items
        return node
    def visit_Expr(self, node):
        c = node.value
        if isinstance(c, ast.Call) and ((isinstance(c.func, ast.Name) and c.func.id == "panel_title") or st_call(c, "divider")):
            return None
        return self.generic_visit(node)
    def visit_For(self, node):
        self.generic_visit(node)
        it = node.iter
        if (isinstance(it, ast.Call) and isinstance(it.func, ast.Name) and it.func.id == "enumerate" and len(it.args) == 1
                and isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2):
            node.target, node.iter = node.target.elts[1], it.args[0]
        return node
    def visit_Name(self, node):
        if node.id == "GOLD":
            node.id = "ACCENT"   # chart colour token only
        return node

def load(path):
    tree = Normalize().visit(ast.parse(open(path).read()))
    ast.fix_missing_locations(tree)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    module = [n for n in tree.body if not isinstance(n, ast.FunctionDef)]
    return funcs, module

old_f, old_m = load(sys.argv[1]); new_f, new_m = load(sys.argv[2])
same = [n for n in old_f if n in new_f and ast.dump(old_f[n]) == ast.dump(new_f[n])]
changed = [n for n in old_f if n in new_f and ast.dump(old_f[n]) != ast.dump(new_f[n])]
print("functions identical after removing layout wrappers:", len(same))
print("changed:", changed)
print("added:", [n for n in new_f if n not in old_f], " removed:", [n for n in old_f if n not in new_f])
for n in changed:
    if n == "page_overview":
        continue
    d = list(difflib.unified_diff(ast.unparse(old_f[n]).splitlines(), ast.unparse(new_f[n]).splitlines(), lineterm="", n=0))
    print(f"--- {n}: {len(d)} diff lines"); print("\n".join(d[:40]))
d = list(difflib.unified_diff([ast.unparse(x) for x in old_m], [ast.unparse(x) for x in new_m], lineterm="", n=0))
print("--- module level:"); print("\n".join(l[:220] for l in d[:60]))

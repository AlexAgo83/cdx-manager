"""Every option a parser declares must reach what that parser returns.

The failure this prevents shipped once. `--failover` was added to the `cdx run`
schema, to the usage string, to the mutually-exclusive declaration in
`cdx schema`, and to the conflict check - but not to the returned dict. It
parsed, validated and documented while doing nothing at all. No error, no
failing unit test; an integration test caught it by chance.

item_070 measured why only that parser could fail this way: `_parse_set_args`
builds its result by comprehension over a key tuple, so adding an option
returns it, while `_parse_run_args` and its neighbours return explicit literals
where a key can simply be forgotten.

This reads the source rather than calling the parsers, because the point is to
catch a key that is never referenced - which no amount of exercising the parser
would reveal, since the missing key produces no behaviour to observe.
"""

import ast
import os
import unittest

CLI_ARGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "cli_args.py")

# Keys a parser consumes rather than returns, deliberately. `json` is read as a
# guard and re-derived by callers; positionals are returned under another name.
CONSUMED_NOT_RETURNED = {"json", "names", "all"}


def _schema_keys(node):
    """The `key` of every option in a `_parse_flag_args` schema literal."""
    keys = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Dict):
            continue
        for k, v in zip(sub.keys, sub.values):
            if not isinstance(k, ast.Constant) or not str(k.value).startswith("--"):
                continue
            if not isinstance(v, ast.Dict):
                continue
            for spec_k, spec_v in zip(v.keys, v.values):
                if isinstance(spec_k, ast.Constant) and spec_k.value == "key" and isinstance(spec_v, ast.Constant):
                    keys.add(spec_v.value)
    return keys


def _schema_nodes(node):
    """The schema dict literals themselves, so they can be excluded below."""
    found = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Dict):
            continue
        if any(isinstance(k, ast.Constant) and str(k.value).startswith("--") for k in sub.keys):
            found.append(sub)
    return found


def _referenced_names(node):
    """String constants used anywhere *outside* the schema that declares them.

    Excluding the schema is the whole point: a key mentioned only in its own
    declaration is exactly the defect being looked for. Otherwise deliberately
    generous - a key reached through a tuple, a comprehension, a dict literal or
    a lookup all count, because the question is whether the option is used at
    all, not how.
    """
    excluded = {id(sub) for schema in _schema_nodes(node) for sub in ast.walk(schema)}
    return {
        sub.value for sub in ast.walk(node)
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and id(sub) not in excluded
    }


def _delegates_whole_dict(node):
    """Whether the parsed dict travels whole, rather than key by key.

    Two shapes count: handing it to another function, and returning it
    directly. Both carry every key by construction, so a key absent from this
    function's own text is still delivered.

    `_parse_history_args` passes `parsed` to `_parse_history_period`, which
    consumes `since`, `from` and `to` there. Those keys are used, just not by
    name here, and flagging them would train the reader to ignore this test.

    Passing a subscript (`parsed["power"]`) is not delegation: the key is named,
    so it is still visible. That is what keeps the check strong for
    `_parse_run_args`, which subscripts but never delegates.
    """
    target = None
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assign) and isinstance(sub.value, ast.Call):
            func = sub.value.func
            if isinstance(func, ast.Name) and func.id == "_parse_flag_args":
                if sub.targets and isinstance(sub.targets[0], ast.Name):
                    target = sub.targets[0].id
    if not target:
        return False
    for sub in ast.walk(node):
        # Returning the dict whole carries every key by construction, which is
        # how `_parse_update_args` delivers `--yes` to commands/maintenance.
        if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Name) and sub.value.id == target:
            return True
        if isinstance(sub, ast.Call):
            for arg in sub.args:
                if isinstance(arg, ast.Name) and arg.id == target:
                    return True
    return False


class ParserAgreementTests(unittest.TestCase):
    def test_every_declared_option_is_referenced_by_its_parser(self):
        tree = ast.parse(open(CLI_ARGS, encoding="utf-8").read())
        checked = 0
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("_parse_"):
                continue
            declared = _schema_keys(node)
            if not declared:
                continue
            if _delegates_whole_dict(node):
                continue
            checked += 1
            referenced = _referenced_names(node)
            forgotten = sorted(declared - referenced - CONSUMED_NOT_RETURNED)
            self.assertEqual(
                forgotten, [],
                f"{node.name} declares {forgotten} in its schema and never uses them again: "
                "the flag would parse, validate and do nothing.",
            )
        # Guard the guard: if the schemas move somewhere this cannot see, the
        # test would pass by finding nothing to check.
        self.assertGreaterEqual(checked, 5, "found too few schema-bearing parsers to trust this test")

    def test_the_check_catches_the_failover_regression(self):
        """The exact shape of the defect, as source this test is run against."""
        source = '''
def _parse_example_args(args):
    parsed = _parse_flag_args(args, {
        "--detach": {"key": "detach", "type": "bool", "default": False},
        "--failover": {"key": "failover", "type": "bool", "default": False},
    }, USAGE)
    return {"detach": parsed["detach"]}
'''
        node = ast.parse(source).body[0]

        declared = _schema_keys(node)
        forgotten = declared - _referenced_names(node) - CONSUMED_NOT_RETURNED

        self.assertEqual(declared, {"detach", "failover"})
        self.assertEqual(forgotten, {"failover"})

#!/usr/bin/env python3

import ast
import json
import sys
from pathlib import Path


# ============================================================
# Utility functions
# ============================================================

def call_name(node):
    """Return a readable name for a function or method call."""

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parts = []
        current = node

        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        if isinstance(current, ast.Name):
            parts.append(current.id)

        return ".".join(reversed(parts))

    return None


def expression_text(node):
    """Convert an AST expression back to Python source."""

    try:
        return ast.unparse(node)
    except AttributeError:
        return "<expression>"


def literal_value(node):
    """Return a Python literal if the AST node contains one."""

    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        return None


# ============================================================
# Static expression resolver
# ============================================================

# ============================================================
# Static expression resolver - Version 3.1
# ============================================================

class ExpressionResolver:
    """
    Resolve simple module-level expressions without executing
    application code.

    Supported examples:

        BASE = "/home/user"
        FILE = BASE + "/file.txt"

        ROOT = Path("/home/user")
        DATA = ROOT / "data"

        DB = os.path.join(ROOT, "activities.db")

        DB = Path(__file__).parent / "activities.db"

        DB = str(Path("/tmp") / "test.db")
    """

    def __init__(self, assignments):

        self.assignments = assignments
        self.cache = {}
        self.resolving = set()

    # --------------------------------------------------------
    # Public resolver
    # --------------------------------------------------------

    def resolve_name(self, name):

        if name in self.cache:
            return self.cache[name]

        if name not in self.assignments:
            return None

        if name in self.resolving:
            return None

        self.resolving.add(name)

        try:
            result = self.resolve_node(
                self.assignments[name]
            )
        finally:
            self.resolving.remove(name)

        self.cache[name] = result

        return result

    # --------------------------------------------------------
    # AST node resolver
    # --------------------------------------------------------

    def resolve_node(self, node):

        if node is None:
            return None

        # ----------------------------------------------------
        # Literal constants
        # ----------------------------------------------------

        if isinstance(node, ast.Constant):

            return node.value

        # ----------------------------------------------------
        # Variable reference
        # ----------------------------------------------------

        if isinstance(node, ast.Name):

            # We cannot know the actual runtime value of
            # __file__, but we can represent it symbolically.
            if node.id == "__file__":
                return "__FILE__"

            return self.resolve_name(
                node.id
            )

        # ----------------------------------------------------
        # Path(...)
        # ----------------------------------------------------

        if isinstance(node, ast.Call):

            name = call_name(node.func)

            # -----------------------------------------------
            # Path(...)
            # -----------------------------------------------

            if name in (
                "Path",
                "pathlib.Path"
            ):

                if not node.args:
                    return None

                value = self.resolve_node(
                    node.args[0]
                )

                if value is not None:
                    return str(value)

                return None

            # -----------------------------------------------
            # str(...)
            # -----------------------------------------------

            if name == "str":

                if len(node.args) == 1:

                    value = self.resolve_node(
                        node.args[0]
                    )

                    if value is not None:
                        return str(value)

                return None

            # -----------------------------------------------
            # os.path.join(...)
            # -----------------------------------------------

            if name in (
                "os.path.join",
                "posixpath.join",
                "ntpath.join"
            ):

                parts = []

                for argument in node.args:

                    value = self.resolve_node(
                        argument
                    )

                    if value is None:
                        return None

                    parts.append(
                        str(value)
                    )

                if not parts:
                    return None

                return str(
                    Path(parts[0]).joinpath(
                        *parts[1:]
                    )
                )

            # -----------------------------------------------
            # os.path.dirname(...)
            # -----------------------------------------------

            if name in (
                "os.path.dirname",
                "posixpath.dirname",
                "ntpath.dirname"
            ):

                if len(node.args) != 1:
                    return None

                value = self.resolve_node(
                    node.args[0]
                )

                if value is None:
                    return None

                return str(
                    Path(str(value)).parent
                )

            # -----------------------------------------------
            # os.path.abspath(...)
            # -----------------------------------------------

            if name in (
                "os.path.abspath",
                "posixpath.abspath",
                "ntpath.abspath"
            ):

                if len(node.args) != 1:
                    return None

                value = self.resolve_node(
                    node.args[0]
                )

                if value is None:
                    return None

                # Don't claim that a runtime-relative path is
                # an actual absolute path.
                if value == "__FILE__":
                    return "__FILE_ABSPATH__"

                return str(
                    Path(str(value)).absolute()
                )

            # -----------------------------------------------
            # Path(...).resolve() etc.
            #
            # These are handled in Attribute below when
            # statically possible.
            # -----------------------------------------------

        # ----------------------------------------------------
        # Attribute expressions
        #
        # Examples:
        #
        # Path(...).parent
        # Path(...).name
        # Path(...).stem
        # ----------------------------------------------------

        if isinstance(node, ast.Attribute):

            attribute = node.attr

            base = self.resolve_node(
                node.value
            )

            if base is None:
                return None

            base_path = Path(
                str(base)
            )

            if attribute == "parent":
                return str(base_path.parent)

            if attribute == "name":
                return base_path.name

            if attribute == "stem":
                return base_path.stem

            if attribute == "suffix":
                return base_path.suffix

            if attribute == "parent":
                return str(base_path.parent)

        # ----------------------------------------------------
        # Binary operations
        # ----------------------------------------------------

        if isinstance(node, ast.BinOp):

            left = self.resolve_node(
                node.left
            )

            right = self.resolve_node(
                node.right
            )

            if left is None or right is None:
                return None

            # -----------------------------------------------
            # String concatenation
            # -----------------------------------------------

            if isinstance(
                node.op,
                ast.Add
            ):

                try:
                    return left + right

                except TypeError:

                    try:
                        return str(left) + str(right)

                    except Exception:
                        return None

            # -----------------------------------------------
            # Path joining
            # -----------------------------------------------

            if isinstance(
                node.op,
                ast.Div
            ):

                try:

                    return str(
                        Path(
                            str(left)
                        ) / str(right)
                    )

                except Exception:

                    return None

        # ----------------------------------------------------
        # f-string
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.JoinedStr
        ):

            pieces = []

            for value in node.values:

                if isinstance(
                    value,
                    ast.Constant
                ):

                    pieces.append(
                        str(value.value)
                    )

                elif isinstance(
                    value,
                    ast.FormattedValue
                ):

                    resolved = self.resolve_node(
                        value.value
                    )

                    if resolved is None:
                        return None

                    pieces.append(
                        str(resolved)
                    )

                else:

                    return None

            return "".join(pieces)

        # ----------------------------------------------------
        # Conditional expression
        #
        # Only resolve when the condition itself can be
        # evaluated safely.
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.IfExp
        ):

            condition = literal_value(
                node.test
            )

            if condition is True:
                return self.resolve_node(
                    node.body
                )

            if condition is False:
                return self.resolve_node(
                    node.orelse
                )

        return None

# ============================================================
# Function Analyzer
# ============================================================

class FunctionAnalyzer(ast.NodeVisitor):

    def __init__(self, function_name, parameters):

        self.function_name = function_name
        self.parameters = set(parameters)

        self.calls = []

        self.names_read = set()
        self.names_written = set()

        self.global_declarations = set()

        self.file_operations = []
        self.template_operations = []
        self.database_operations = []

    # --------------------------------------------------------
    # Function calls
    # --------------------------------------------------------

    def visit_Call(self, node):

        name = call_name(node.func)

        if name:

            self.calls.append({
                "name": name,
                "line": node.lineno
            })

        # ----------------------------------------------------
        # open(...)
        # ----------------------------------------------------

        if name == "open":

            argument = None

            if node.args:
                argument = expression_text(
                    node.args[0]
                )

            self.file_operations.append({
                "operation": "open",
                "line": node.lineno,
                "path_expression": argument
            })

        # ----------------------------------------------------
        # Path(...)
        # ----------------------------------------------------

        elif name in (
            "Path",
            "pathlib.Path"
        ):

            argument = None

            if node.args:
                argument = expression_text(
                    node.args[0]
                )

            self.file_operations.append({
                "operation": "Path",
                "line": node.lineno,
                "path_expression": argument
            })

        # ----------------------------------------------------
        # render_template(...)
        # ----------------------------------------------------

        elif name == "render_template":

            template = None

            if node.args:

                value = literal_value(
                    node.args[0]
                )

                if value is not None:
                    template = value
                else:
                    template = expression_text(
                        node.args[0]
                    )

            self.template_operations.append({
                "template": template,
                "line": node.lineno
            })

        # ----------------------------------------------------
        # sqlite3.connect(...)
        # ----------------------------------------------------

        elif name == "sqlite3.connect":

            database = None

            if node.args:
                database = expression_text(
                    node.args[0]
                )

            self.database_operations.append({
                "operation": "connect",
                "line": node.lineno,
                "database_expression": database
            })

        self.generic_visit(node)

    # --------------------------------------------------------
    # Variable reads/writes
    # --------------------------------------------------------

    def visit_Name(self, node):

        if isinstance(node.ctx, ast.Load):

            self.names_read.add(
                node.id
            )

        elif isinstance(
            node.ctx,
            (ast.Store, ast.Del)
        ):

            self.names_written.add(
                node.id
            )

        self.generic_visit(node)

    # --------------------------------------------------------
    # global statement
    # --------------------------------------------------------

    def visit_Global(self, node):

        for name in node.names:

            self.global_declarations.add(
                name
            )

        self.generic_visit(node)

    # --------------------------------------------------------
    # Do not analyze nested functions as part of this function
    # --------------------------------------------------------

    def visit_FunctionDef(self, node):
        return

    def visit_AsyncFunctionDef(self, node):
        return

    def visit_Lambda(self, node):
        return

# ============================================================
# Flask Route Analyzer
# ============================================================

class RouteAnalyzer(ast.NodeVisitor):

    ROUTE_METHODS = {
        "get": "GET",
        "post": "POST",
        "put": "PUT",
        "delete": "DELETE",
        "patch": "PATCH",
        "options": "OPTIONS",
    }

    def __init__(self):

        self.routes = []

    def visit_FunctionDef(self, node):

        self.inspect_function(node)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):

        self.inspect_function(node)

        self.generic_visit(node)

    def inspect_function(self, node):

        for decorator in node.decorator_list:

            route = self.extract_route(
                decorator
            )

            if route:

                self.routes.append({
                    "route": route["route"],
                    "methods": route["methods"],
                    "function": node.name,
                    "line": node.lineno
                })

    def extract_route(self, decorator):

        if not isinstance(
            decorator,
            ast.Call
        ):
            return None

        if not isinstance(
            decorator.func,
            ast.Attribute
        ):
            return None

        decorator_name = decorator.func.attr

        # ----------------------------------------------------
        # @app.route(...)
        # ----------------------------------------------------

        if decorator_name == "route":

            route = None

            if decorator.args:

                route = literal_value(
                    decorator.args[0]
                )

                if route is None:

                    route = expression_text(
                        decorator.args[0]
                    )

            methods = []

            for keyword in decorator.keywords:

                if keyword.arg == "methods":

                    value = literal_value(
                        keyword.value
                    )

                    if isinstance(
                        value,
                        (list, tuple)
                    ):

                        methods = list(value)

                    elif value is not None:

                        methods = [value]

            if not methods:
                methods = ["GET"]

            return {
                "route": route,
                "methods": methods
            }

        # ----------------------------------------------------
        # @app.get(...)
        # @app.post(...)
        # etc.
        # ----------------------------------------------------

        if decorator_name in self.ROUTE_METHODS:

            route = None

            if decorator.args:

                route = literal_value(
                    decorator.args[0]
                )

                if route is None:

                    route = expression_text(
                        decorator.args[0]
                    )

            return {
                "route": route,
                "methods": [
                    self.ROUTE_METHODS[
                        decorator_name
                    ]
                ]
            }

        return None


# ============================================================
# Main Analyzer
# ============================================================

class PythonAnalyzer:

    def __init__(self, source_file):

        self.source_file = Path(
            source_file
        )

        self.source = None
        self.tree = None

        self.functions = {}
        self.routes = []

        self.module_globals = set()

        self.module_assignments = {}

        self.resolver = None

        self.imports = []

    # --------------------------------------------------------
    # Load source
    # --------------------------------------------------------

    def load(self):

        self.source = (
            self.source_file.read_text(
                encoding="utf-8"
            )
        )

        self.tree = ast.parse(
            self.source,
            filename=str(
                self.source_file
            )
        )

    # --------------------------------------------------------
    # Main analysis
    # --------------------------------------------------------

    def analyze(self):

        self.load()

        self.find_imports()

        self.find_module_assignments()

        self.find_functions()

        self.find_routes()

        self.resolver = ExpressionResolver(
            self.module_assignments
        )

        self.resolve_global_usage()

        return self.build_report()

    # ========================================================
    # Imports
    # ========================================================

    def find_imports(self):

        for node in ast.walk(
            self.tree
        ):

            if isinstance(
                node,
                ast.Import
            ):

                for alias in node.names:

                    self.imports.append({
                        "type": "import",
                        "module": alias.name,
                        "name": None,
                        "alias": alias.asname,
                        "line": node.lineno
                    })

            elif isinstance(
                node,
                ast.ImportFrom
            ):

                for alias in node.names:

                    self.imports.append({
                        "type": "from",
                        "module": node.module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "line": node.lineno
                    })

    # ========================================================
    # Module-level assignments
    # ========================================================

    def find_module_assignments(self):

        for node in self.tree.body:

            if isinstance(
                node,
                ast.Assign
            ):

                for target in node.targets:

                    self.collect_assignment(
                        target,
                        node.value
                    )

            elif isinstance(
                node,
                ast.AnnAssign
            ):

                if node.value is not None:

                    self.collect_assignment(
                        node.target,
                        node.value
                    )

    def collect_assignment(
        self,
        target,
        value
    ):

        if isinstance(
            target,
            ast.Name
        ):

            self.module_globals.add(
                target.id
            )

            self.module_assignments[
                target.id
            ] = value

        elif isinstance(
            target,
            (ast.Tuple, ast.List)
        ):

            for element in target.elts:

                self.collect_assignment(
                    element,
                    value
                )

    # ========================================================
    # Functions
    # ========================================================

    def find_functions(self):

        for node in ast.walk(
            self.tree
        ):

            if not isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef
                )
            ):
                continue

            parameters = []

            arguments = node.args

            for arg in arguments.posonlyargs:
                parameters.append(arg.arg)

            for arg in arguments.args:
                parameters.append(arg.arg)

            for arg in arguments.kwonlyargs:
                parameters.append(arg.arg)

            if arguments.vararg:
                parameters.append(
                    arguments.vararg.arg
                )

            if arguments.kwarg:
                parameters.append(
                    arguments.kwarg.arg
                )

            analyzer = FunctionAnalyzer(
                node.name,
                parameters
            )

            for statement in node.body:

                analyzer.visit(
                    statement
                )

            self.functions[
                node.name
            ] = {
                "name": node.name,
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno
                ),
                "parameters": parameters,
                "calls": analyzer.calls,
                "names_read": sorted(
                    analyzer.names_read
                ),
                "names_written": sorted(
                    analyzer.names_written
                ),
                "global_declarations": sorted(
                    analyzer.global_declarations
                ),
                "file_operations": (
                    analyzer.file_operations
                ),
                "template_operations": (
                    analyzer.template_operations
                ),
                "database_operations": (
                    analyzer.database_operations
                )
            }

    # ========================================================
    # Routes
    # ========================================================

    def find_routes(self):

        analyzer = RouteAnalyzer()

        analyzer.visit(
            self.tree
        )

        self.routes = analyzer.routes

    # ========================================================
    # Global usage
    # ========================================================

    def resolve_global_usage(self):

        for function in self.functions.values():

            parameters = set(
                function["parameters"]
            )

            names_read = set(
                function["names_read"]
            )

            names_written = set(
                function["names_written"]
            )

            explicit_globals = set(
                function[
                    "global_declarations"
                ]
            )

            # ------------------------------------------------
            # Names read from module scope
            # ------------------------------------------------

            global_reads = (
                names_read
                & self.module_globals
            ) - parameters

            # ------------------------------------------------
            # Names written to module scope
            # ------------------------------------------------

            global_writes = (
                names_written
                & self.module_globals
            ) - parameters

            # ------------------------------------------------
            # Explicit global declarations
            # ------------------------------------------------

            global_reads |= (
                explicit_globals
                & names_read
            )

            global_writes |= (
                explicit_globals
                & names_written
            )

            function[
                "global_reads"
            ] = sorted(
                global_reads
            )

            function[
                "global_writes"
            ] = sorted(
                global_writes
            )

            # ------------------------------------------------
            # Resolved values
            # ------------------------------------------------

            resolved = {}

            for name in (
                global_reads
                | global_writes
            ):

                value = self.resolver.resolve_name(
                    name
                )

                if value is not None:

                    resolved[name] = value

            function[
                "resolved_globals"
            ] = resolved

    # ========================================================
    # Local function calls
    # ========================================================

    def local_function_calls(
        self,
        function_name
    ):

        function = self.functions.get(
            function_name
        )

        if not function:
            return []

        result = []

        for call in function["calls"]:

            name = call["name"]

            if name in self.functions:

                if name not in result:

                    result.append(name)

        return result

    # ========================================================
    # Direct functions
    # ========================================================

    def direct_functions(
        self,
        function_name
    ):

        return self.local_function_calls(
            function_name
        )

    # ========================================================
    # Recursive dependency collection
    # ========================================================

    def collect_indirect_functions(
        self,
        function_name,
        visited=None
    ):

        if visited is None:

            visited = set()

        direct = self.direct_functions(
            function_name
        )

        result = []

        for function in direct:

            if function in visited:
                continue

            visited.add(function)

            children = (
                self.collect_indirect_functions(
                    function,
                    visited
                )
            )

            for child in children:

                if child not in result:
                    result.append(child)

            if function not in result:
                result.append(function)

        return result

    # ========================================================
    # Call tree
    # ========================================================

    def build_call_tree(
        self,
        function_name,
        ancestors=None
    ):

        if ancestors is None:

            ancestors = set()

        if function_name not in self.functions:

            return {
                "function": function_name,
                "line": None,
                "calls": []
            }

        function = self.functions[
            function_name
        ]

        if function_name in ancestors:

            return {
                "function": function_name,
                "line": function["line"],
                "recursive": True,
                "calls": []
            }

        new_ancestors = set(
            ancestors
        )

        new_ancestors.add(
            function_name
        )

        calls = []

        for child in self.direct_functions(
            function_name
        ):

            calls.append(
                self.build_call_tree(
                    child,
                    new_ancestors
                )
            )

        return {
            "function": function_name,
            "line": function["line"],
            "calls": calls
        }

    # ========================================================
    # Handler dependencies
    # ========================================================

    def handler_dependencies(
        self,
        function_name
    ):

        direct = self.direct_functions(
            function_name
        )

        indirect = (
            self.collect_indirect_functions(
                function_name
            )
        )

        # Remove direct functions from indirect list
        indirect_only = [
            name
            for name in indirect
            if name not in direct
        ]

        all_functions = [
            function_name
        ] + indirect

        global_reads = set()
        global_writes = set()

        files = []
        templates = []
        databases = []

        for name in all_functions:

            function = self.functions.get(
                name
            )

            if not function:
                continue

            global_reads.update(
                function["global_reads"]
            )

            global_writes.update(
                function["global_writes"]
            )

            files.extend(
                function[
                    "file_operations"
                ]
            )

            templates.extend(
                function[
                    "template_operations"
                ]
            )

            databases.extend(
                function[
                    "database_operations"
                ]
            )

        # ----------------------------------------------------
        # Resolved global values
        # ----------------------------------------------------

        resolved_globals = {}

        for name in (
            global_reads
            | global_writes
        ):

            value = self.resolver.resolve_name(
                name
            )

            if value is not None:

                resolved_globals[name] = value

        return {

            "direct_functions": direct,

            "indirect_functions": indirect_only,

            "all_functions": all_functions,

            "call_tree": self.build_call_tree(
                function_name
            ),

            "global_state": {

                "read": sorted(
                    global_reads
                    - global_writes
                ),

                "write": sorted(
                    global_writes
                    - global_reads
                ),

                "read_write": sorted(
                    global_reads
                    & global_writes
                ),

                "resolved": resolved_globals
            },

            "files": files,

            "templates": templates,

            "databases": databases
        }

    # ========================================================
    # Complete report
    # ========================================================

    def build_report(self):

        handlers = []

        for route in self.routes:

            function_name = route[
                "function"
            ]

            dependencies = (
                self.handler_dependencies(
                    function_name
                )
            )

            handlers.append({

                "route": route["route"],

                "methods": route[
                    "methods"
                ],

                "function": function_name,

                "line": route["line"],

                "dependencies": dependencies

            })

        # ----------------------------------------------------
        # Global variable details
        # ----------------------------------------------------

        global_details = []

        for name in sorted(
            self.module_globals
        ):

            value = self.resolver.resolve_name(
                name
            )

            global_details.append({

                "name": name,

                "line": self.find_global_line(
                    name
                ),

                "resolved_value": value

            })

        return {

            "source_file": str(
                self.source_file
            ),

            "python_version": (
                f"{sys.version_info.major}."
                f"{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),

            "imports": self.imports,

            "module_globals": global_details,

            "functions": list(
                self.functions.values()
            ),

            "routes": self.routes,

            "handlers": handlers
        }

    # ========================================================
    # Find global variable source line
    # ========================================================

    def find_global_line(
        self,
        name
    ):

        for node in self.tree.body:

            if isinstance(
                node,
                ast.Assign
            ):

                for target in node.targets:

                    if (
                        isinstance(
                            target,
                            ast.Name
                        )
                        and target.id == name
                    ):

                        return node.lineno

            elif isinstance(
                node,
                ast.AnnAssign
            ):

                if (
                    isinstance(
                        node.target,
                        ast.Name
                    )
                    and node.target.id == name
                ):

                    return node.lineno

        return None


# ============================================================
# Human-readable report
# ============================================================

def print_report(report):

    print()
    print("=" * 80)
    print("FLASK APPLICATION AST ANALYSIS - VERSION 3")
    print("=" * 80)

    print()
    print("SOURCE")
    print("-" * 80)
    print(report["source_file"])

    # --------------------------------------------------------
    # URL handlers
    # --------------------------------------------------------

    print()
    print("URL HANDLERS")
    print("-" * 80)

    for handler in report["handlers"]:

        print()
        print(
            f'{handler["route"]} '
            f'→ {handler["function"]}() '
            f'(line {handler["line"]})'
        )

        print(
            "    Methods: "
            + ", ".join(
                handler["methods"]
            )
        )

        deps = handler[
            "dependencies"
        ]

        # ----------------------------------------------------
        # Direct functions
        # ----------------------------------------------------

        print()
        print("    Direct functions:")

        if deps[
            "direct_functions"
        ]:

            for function in deps[
                "direct_functions"
            ]:

                print(
                    f"        {function}()"
                )

        else:

            print("        None")

        # ----------------------------------------------------
        # Indirect functions
        # ----------------------------------------------------

        print()
        print("    Indirect functions:")

        if deps[
            "indirect_functions"
        ]:

            for function in deps[
                "indirect_functions"
            ]:

                print(
                    f"        {function}()"
                )

        else:

            print("        None")

        # ----------------------------------------------------
        # Global state
        # ----------------------------------------------------

        print()
        print("    Global state:")

        global_state = deps[
            "global_state"
        ]

        if global_state["read"]:

            for name in global_state[
                "read"
            ]:

                print(
                    f"        READ       {name}"
                )

        if global_state["write"]:

            for name in global_state[
                "write"
            ]:

                print(
                    f"        WRITE      {name}"
                )

        if global_state[
            "read_write"
        ]:

            for name in global_state[
                "read_write"
            ]:

                print(
                    f"        READ/WRITE {name}"
                )

        if (
            not global_state["read"]
            and not global_state["write"]
            and not global_state["read_write"]
        ):

            print("        None")

        # ----------------------------------------------------
        # Resolved globals
        # ----------------------------------------------------

        if global_state[
            "resolved"
        ]:

            print()
            print(
                "    Resolved global values:"
            )

            for name, value in (
                global_state[
                    "resolved"
                ].items()
            ):

                print(
                    f"        {name} = {value}"
                )

        # ----------------------------------------------------
        # Files
        # ----------------------------------------------------

        print()
        print("    File operations:")

        if deps["files"]:

            for item in deps["files"]:

                print(
                    f'        '
                    f'{item["operation"]}: '
                    f'{item["path_expression"]} '
                    f'(line {item["line"]})'
                )

        else:

            print("        None")

        # ----------------------------------------------------
        # Templates
        # ----------------------------------------------------

        print()
        print("    Templates:")

        if deps["templates"]:

            for item in deps[
                "templates"
            ]:

                print(
                    f'        '
                    f'{item["template"]} '
                    f'(line {item["line"]})'
                )

        else:

            print("        None")

        # ----------------------------------------------------
        # Databases
        # ----------------------------------------------------

        print()
        print("    Databases:")

        if deps["databases"]:

            for item in deps[
                "databases"
            ]:

                print(
                    f'        '
                    f'{item["operation"]}: '
                    f'{item["database_expression"]} '
                    f'(line {item["line"]})'
                )

        else:

            print("        None")

        # ----------------------------------------------------
        # Call tree
        # ----------------------------------------------------

        print()
        print("    Call tree:")

        print_call_tree(
            deps["call_tree"],
            indent=8
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(
        f'Routes:          '
        f'{len(report["routes"])}'
    )

    print(
        f'Functions:       '
        f'{len(report["functions"])}'
    )

    print(
        f'Module globals:  '
        f'{len(report["module_globals"])}'
    )

    print(
        f'Imports:         '
        f'{len(report["imports"])}'
    )


# ============================================================
# Print call tree
# ============================================================

def print_call_tree(
    tree,
    indent=0
):

    prefix = " " * indent

    print(
        f'{prefix}{tree["function"]}() '
        f'(line {tree["line"]})'
    )

    for child in tree.get(
        "calls",
        []
    ):

        print_call_tree(
            child,
            indent + 4
        )


# ============================================================
# Main
# ============================================================

def main():

    if len(sys.argv) not in (
        2,
        3
    ):

        print(
            "Usage:"
        )

        print(
            "    python "
            "devdocs_generator/analyzer.py "
            "<python-file> "
            "[output-json]"
        )

        print()
        print(
            "Example:"
        )

        print(
            "    python "
            "devdocs_generator/analyzer.py "
            "dailylog_server_websoc.py "
            "devdocs_generator/output/analysis.json"
        )

        sys.exit(1)

    source_file = Path(
        sys.argv[1]
    )

    if not source_file.exists():

        print(
            f"ERROR: File not found:\n"
            f"    {source_file}"
        )

        sys.exit(1)

    if source_file.suffix != ".py":

        print(
            "ERROR: Input file must have "
            ".py extension."
        )

        sys.exit(1)

    analyzer = PythonAnalyzer(
        source_file
    )

    try:

        report = analyzer.analyze()

    except SyntaxError as error:

        print()
        print(
            "ERROR: Python syntax error"
        )

        print()
        print(error)

        sys.exit(1)

    print_report(
        report
    )

    # --------------------------------------------------------
    # Optional JSON output
    # --------------------------------------------------------

    if len(sys.argv) == 3:

        output_file = Path(
            sys.argv[2]
        )

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        output_file.write_text(
            json.dumps(
                report,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print()
        print(
            "JSON report written to:"
        )

        print(
            f"    {output_file}"
        )


if __name__ == "__main__":
    main()

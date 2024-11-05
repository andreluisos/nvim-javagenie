from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_java as tsjava
from tree_sitter import Language, Node, Parser, Query, Tree
from pynvim.api.nvim import Nvim
from utils.logging import Logging


class TreesitterUtils:
    def __init__(
        self,
        nvim: Nvim,
        java_basic_types: list[tuple],
        cwd: Path,
        logging: Logging,
    ):
        self.nvim = nvim
        self.cwd: Path = cwd
        self.java_basic_types = java_basic_types
        self.logging = logging
        self.ts_java = Language(tsjava.language())
        self.parser = Parser(self.ts_java)

    def convert_bytes_to_string(self, bytes_value: bytes) -> str:
        try:
            return bytes_value.decode()
        except (UnicodeDecodeError, AttributeError) as e:
            error_msg = f"Error decoding bytes: {e}"
            self.logging.log(error_msg, "error")
            raise RuntimeError(error_msg)

    def convert_string_to_bytes(self, string_value: str) -> bytes:
        try:
            return string_value.encode()
        except (UnicodeEncodeError, AttributeError) as e:
            error_msg = f"Error enconding string: {e}"
            self.logging.log(error_msg, "error")
            raise RuntimeError(error_msg)

    def convert_buffer_to_tree(self, buffer: Path | bytes) -> Tree:
        try:
            buffer_bytes: bytes
            if isinstance(buffer, Path):
                try:
                    buffer_bytes = buffer.read_bytes()
                except (OSError, FileNotFoundError) as e:
                    error_msg = f"Error reading from file path {buffer}: {e}"
                    self.logging.log(error_msg, "error")
                    raise RuntimeError(error_msg)
            else:
                buffer_bytes = buffer
            buffer_tree = self.parser.parse(buffer_bytes)
            return buffer_tree
        except Exception as e:
            error_msg = f"Error parsing buffer to tree: {e}"
            self.logging.log(error_msg, "error")
            raise RuntimeError(error_msg)

    def query_match(self, tree: Tree, query_param: str) -> List[Node]:
        try:
            query: Query = self.ts_java.query(query_param)
        except Exception as e:
            error_msg = f"Error creating query from query_param '{query_param}': {e}"
            self.logging.log(error_msg, "error")
            raise RuntimeError(error_msg)
        try:
            query_results: List[Tuple[int, Dict[str, List[Node]]]] = query.matches(
                tree.root_node
            )
            nodes: List[Node] = []
            for result in query_results:
                for item in result[1].values():
                    for node in item:
                        nodes.append(node)
            return nodes
        except Exception as e:
            error_msg = f"Error matching query in tree: {e}"
            self.logging.log(error_msg, "error")
            raise RuntimeError(error_msg)

    def get_node_by_type(self, node: Node, type_name: str) -> Optional[Node]:
        if node.type == type_name:
            return node
        for child in node.children:
            result = self.get_node_by_type(child, type_name)
            if result is not None:
                return result
        return None

    def insert_code_into_position(
        self, tree: Tree, code: str, insert_position: int, debug: bool = False
    ) -> Tree:
        buffer_bytes = tree.root_node.text
        buffer_string: Optional[str] = None
        if not buffer_bytes:
            error_msg = "Unable to convert root node's text to bytes"
            self.logging.log(error_msg, "critical")
            raise ValueError(error_msg)
        buffer_string = buffer_bytes.decode()
        modified_buffer_string = (
            buffer_string[:insert_position] + code + buffer_string[insert_position:]
        )
        if debug:
            self.logging.log(
                [
                    f"Code:\n{code}",
                    f"Insert position: {insert_position}",
                    f"Current buffer:\n{buffer_string}",
                    f"Modified buffer:\n{modified_buffer_string}",
                ],
                "debug",
            )
        return self.convert_buffer_to_tree(modified_buffer_string.encode())

    def update_buffer(
        self,
        tree: Tree,
        buffer_path: Path,
        save: bool = False,
        format: bool = False,
        organize_imports: bool = False,
        debug: bool = False,
    ):
        node_text = tree.root_node.text
        if not node_text:
            error_msg = "Root node doesn't have text"
            self.logging.log(error_msg, "error")
            raise ValueError(error_msg)
        buffer_path.write_bytes(node_text)
        self.nvim.command(f"e {str(buffer_path)}")
        if save:
            self.nvim.command(f"w {str(buffer_path)}")
        if organize_imports:
            self.nvim.command("lua require('jdtls').organize_imports()")
        if format and not save:
            self.nvim.command("lua vim.lsp.buf.format({ async = true })")
        if debug:
            self.logging.log(
                [
                    f"Updated buffer: {node_text.decode()}",
                    f"Original buffer: {buffer_path.read_text('utf-8')}",
                ],
                "debug",
            )

    def get_buffer_public_class_node_from_query_results(
        self, query_results: List[Node], debug: bool = False
    ) -> Optional[Node]:
        public_class_node: Optional[Node] = None
        for node in query_results:
            for child_node in node.children:
                if child_node.type == "modifiers" and child_node.text:
                    modifiers_text_str = self.convert_bytes_to_string(
                        child_node.text
                    ).split("\n")
                    if modifiers_text_str[-1] == "public":
                        public_class_node = node
        if debug:
            public_class_node_str: Optional[str] = None
            if public_class_node and public_class_node.text:
                self.convert_bytes_to_string(public_class_node.text)
            self.logging.log(
                f"Found public class node: {public_class_node_str}", "debug"
            )
        return public_class_node

    def get_buffer_public_class_name(
        self, tree: Tree, debug: bool = False
    ) -> Optional[str]:
        public_class_name: Optional[str] = None
        query_param = "(class_declaration) @class_decl"
        query_results: List[Node] = self.query_match(tree=tree, query_param=query_param)
        public_class_node = self.get_buffer_public_class_node_from_query_results(
            query_results=query_results, debug=debug
        )
        if public_class_node:
            name_node = public_class_node.child_by_field_name("name")
            if name_node and name_node.text:
                public_class_name = self.convert_bytes_to_string(name_node.text)
        if debug:
            self.logging.log(
                [
                    f"Query param: {query_param}",
                    f"Total query results: {len(query_results)}",
                    f"Public class name: {public_class_name}",
                ],
                "debug",
            )
        return public_class_name

    def buffer_public_class_has_annotation(
        self, tree: Tree, annotation_name: str, debug: bool = False
    ) -> bool:
        public_class_has_annotation: bool = False
        query_param = "(class_declaration) @class_decl"
        query_results: List[Node] = self.query_match(tree=tree, query_param=query_param)
        public_class_node = self.get_buffer_public_class_node_from_query_results(
            query_results=query_results, debug=debug
        )
        if public_class_node:
            modifiers = self.get_node_by_type(public_class_node, "modifiers")
            if modifiers:
                for child in modifiers.children:
                    if child.type in ["marker_annotation", "annotation"]:
                        name_node = child.child_by_field_name("name")
                        if name_node and name_node.text:
                            if (
                                self.convert_bytes_to_string(name_node.text)
                                == annotation_name
                            ):
                                public_class_has_annotation = True
        if debug:
            self.logging.log(
                f"Annotation found: {public_class_has_annotation}", "debug"
            )
        return public_class_has_annotation

    def buffer_public_class_has_method(
        self, tree: Tree, method_name: str, debug: bool = False
    ):
        public_class_has_method: bool = False
        query_param = "(class_declaration) @class_decl"
        query_results: List[Node] = self.query_match(tree=tree, query_param=query_param)
        public_class_node = self.get_buffer_public_class_node_from_query_results(
            query_results=query_results, debug=debug
        )
        if public_class_node:
            body = public_class_node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "method_declaration":
                        node_name = child.child_by_field_name("name")
                        if node_name and node_name.text:
                            node_name_str = self.convert_bytes_to_string(node_name.text)
                            if node_name_str == method_name:
                                public_class_has_method = True
        if debug:
            self.logging.log(
                f"Public class has method '{method_name}': {public_class_has_method}",
                "debug",
            )
        return public_class_has_method

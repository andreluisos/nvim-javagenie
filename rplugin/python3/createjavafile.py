from pathlib import Path
from typing import Literal

from messaging import Messaging


class CreateJavaFile:
    def __init__(self, nvim, messaging: Messaging):
        self.nvim = nvim
        self.messaging = messaging

    def get_boiler_plate(
        self, file_type: str, package_path: str, file_name: str, debugger: bool = False
    ) -> str:
        boiler_plate: str = ""
        if file_type in ["class", "interface", "enum"]:
            boiler_plate = f"""package {package_path};\n\npublic {file_type} {file_name} {{\n\n}}"""
        elif file_type == "record":
            boiler_plate = (
                f"""package {package_path};\n\npublic record {file_name}(\n\n) {{}}"""
            )
        else:
            boiler_plate = (
                f"""package {package_path};\n\npublic @interface {file_name} {{\n\n}}"""
            )
        if debugger:
            self.messaging.log(f"Boiler plate: {boiler_plate}", "debug")
        return boiler_plate

    def get_file_path(
        self,
        main_class_path: str,
        package_path: str,
        file_name: str,
        debugger: bool = False,
    ) -> Path:
        base_path = Path(main_class_path).parent
        relative_path = Path(package_path.replace(".", "/"))
        index_to_replace: int
        try:
            index_to_replace = base_path.parts.index("main")
        except ValueError:
            self.messaging.log("Unable to parse root directory.", "error")
            raise ValueError("Unable to parse root directory")
        file_path = (
            Path(*base_path.parts[: index_to_replace + 2])
            / relative_path
            / f"{file_name}.java"
        )
        if debugger:
            self.messaging.log(f"Base path: {str(base_path)}", "debug")
            self.messaging.log(f"Relative path: {str(relative_path)}", "debug")
            self.messaging.log(f"File path: {str(file_path.parent)}", "debug")
            self.messaging.log(f"Successfully created: {file_path}", "debug")
        return file_path

    def create_java_file(
        self,
        main_class_path: str,
        package_path: str,
        file_name: str,
        file_type: Literal["class", "interface", "record", "enum", "annotation"],
        debugger: bool = False,
    ) -> None:
        boiler_plate = self.get_boiler_plate(
            file_type, package_path, file_name, debugger
        )
        file_path = self.get_file_path(
            main_class_path, package_path, file_name, debugger
        )
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as java_file:
                java_file.write(boiler_plate)
                self.nvim.command(f"edit {file_path}")
        else:
            self.messaging.log(
                f"Failed to create file {file_path} because it already exists", "error"
            )

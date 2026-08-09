"""Environment variable access for BlazeLang using the project root .env file."""

from pathlib import Path


class EnvironmentLibrary:
    def __init__(self, root_dir=None):
        # The .env file lives in the project root.
        self.root_dir = Path(root_dir) if root_dir else Path.cwd()
        self.env_file = self.root_dir / ".env"

    def _ensure_env_file(self):
        """Create .env automatically if it does not exist."""
        if not self.env_file.exists():
            self.env_file.write_text("", encoding="utf-8")

    def _read_env(self):
        """Read .env and return variables as a dictionary."""
        self._ensure_env_file()

        variables = {}

        try:
            lines = self.env_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return variables

        for line in lines:
            line = line.strip()

            # Ignore empty lines and comments
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove optional surrounding quotes
            if len(value) >= 2:
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]

            variables[key] = value

        return variables

    def _write_env(self, variables):
        """Write variables back to the .env file."""
        self._ensure_env_file()

        lines = []

        for key, value in variables.items():
            value = str(value)

            # Quote values containing spaces
            if " " in value:
                value = f'"{value}"'

            lines.append(f"{key}={value}")

        content = "\n".join(lines)

        if content:
            content += "\n"

        self.env_file.write_text(content, encoding="utf-8")

    def get(self, name, default=None):
        """Get a value from the .env file."""
        name = str(name)
        variables = self._read_env()
        return variables.get(name, default)

    def set(self, name, value):
        """Set or update a value in the .env file."""
        name = str(name)
        value = str(value)

        if not name:
            return False

        variables = self._read_env()
        variables[name] = value
        self._write_env(variables)

        return True

    def exists(self, name):
        """Check whether a variable exists in .env."""
        name = str(name)
        variables = self._read_env()
        return name in variables

    def remove(self, name):
        """Remove a variable from .env."""
        name = str(name)
        variables = self._read_env()

        if name not in variables:
            return False

        del variables[name]
        self._write_env(variables)

        return True


def create_env_module(root_dir=None):
    library = EnvironmentLibrary(root_dir)

    return {
        "Get": library.get,
        "Set": library.set,
        "Exists": library.exists,
        "Remove": library.remove,
    }


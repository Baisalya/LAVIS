# registry.py

class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, name, func):
        """Register a command with a name and function."""
        self.commands[name.lower()] = func

    def unregister(self, name):
        """Remove a registered command."""
        self.commands.pop(name.lower(), None)

    def execute(self, command_name):
        """Execute the registered command if found."""
        command_name = command_name.lower().strip()
        for name in self.commands:
            if name in command_name:
                try:
                    self.commands[name]()
                    return True
                except Exception as e:
                    print(f"❌ Command '{name}' failed: {e}")
                    return False
        return False

    def list_commands(self):
        return list(self.commands.keys())

# Example usage:
# registry = CommandRegistry()
# registry.register("open chrome", lambda: os.system("start chrome"))
# registry.execute("open chrome")

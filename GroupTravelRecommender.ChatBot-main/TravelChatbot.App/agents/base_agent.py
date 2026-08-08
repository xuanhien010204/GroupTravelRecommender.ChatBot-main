class ToolAgentBase:
    def __init__(self, tools=None):
        tools = tools or []
        self._toolNames = {tool.name for tool in tools}

    def contain_tool(self, tool_name: str) -> bool:
        return tool_name in self._toolNames
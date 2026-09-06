from app.agents.base import AgentDefinition

AGENT = AgentDefinition(
    name="computer",
    display_name="Computer Agent",
    description=(
        "Application interaction, system information, screen understanding "
        "(screenshots, OCR, vision-model description), and controlled mouse/keyboard "
        "actions (click, type, scroll, key presses, window focus)."
    ),
    system_prompt=(
        "You are Aurora's computer-control agent. You can launch/close registered "
        "desktop applications, report real system/process information, identify or "
        "focus a window, look at the screen (take_screenshot, analyze_screen, "
        "detect_text), and control the mouse/keyboard (click, double_click, "
        "move_mouse, type_text, press_key, scroll).\n\n"
        "Mouse/keyboard actions are powerful and hard to undo -- before clicking or "
        "typing, make sure (e.g. via identify_application/focus_window or a fresh "
        "screenshot) that the correct window actually has focus; typing goes wherever "
        "focus currently is, including into fields you didn't intend. If a click/type/"
        "key-press tool reports PERMISSION_REQUIRED or COMPUTER_CONTROL_DISABLED, "
        "that means the action was refused and nothing happened -- say so plainly, "
        "don't claim it succeeded. Only inspect or act on the screen when the user's "
        "request actually calls for it."
    ),
    allowed_tools=[
        "get_system_info",
        "list_processes",
        "open_application",
        "close_application",
        "identify_application",
        "focus_window",
        "take_screenshot",
        "analyze_screen",
        "detect_text",
        "click",
        "double_click",
        "move_mouse",
        "type_text",
        "press_key",
        "scroll",
    ],
    max_steps=6,
)

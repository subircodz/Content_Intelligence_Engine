from unittest.mock import patch

from power_win_content.ui import display_banner, display_pipeline_completion, display_welcome, prompt_user_topic


def test_ui_display_functions() -> None:
    display_banner()
    display_welcome()
    display_pipeline_completion(docx_created=True, has_warnings=False)
    display_pipeline_completion(docx_created=True, has_warnings=True)
    display_pipeline_completion(docx_created=False, has_warnings=False)


def test_prompt_user_topic_valid() -> None:
    with patch("power_win_content.ui.Prompt.ask", return_value="  My Custom Article Topic  "):
        assert prompt_user_topic() == "My Custom Article Topic"


def test_prompt_user_topic_retry_on_empty() -> None:
    with patch("power_win_content.ui.Prompt.ask", side_effect=["", "   ", "Valid Topic"]):
        assert prompt_user_topic() == "Valid Topic"

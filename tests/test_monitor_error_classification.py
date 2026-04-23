from scripts.monitor import classify_tool_result


def test_error_null_json_is_success():
    is_error, kind = classify_tool_result('{"output":"OK", "exit_code": 0, "error": null}')
    assert not is_error
    assert kind == ""


def test_success_false_json_is_error():
    is_error, kind = classify_tool_result('{"success": false, "error": "Skill not found"}')
    assert is_error
    assert "Skill not found" in kind


def test_nonzero_exit_code_json_is_error():
    is_error, kind = classify_tool_result('{"output":"", "exit_code": 2, "error": null}')
    assert is_error
    assert "exit_code=2" in kind

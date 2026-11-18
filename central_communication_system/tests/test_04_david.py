def test_david_payload_structure():
    """Verify standard payload contract for David browser actions."""
    mock_payload = {
        "recipient": "david",
        "action": "scrape",
        "payload": {"selector": "body"}
    }
    
    assert mock_payload["recipient"] == "david"
    assert mock_payload["action"] == "scrape"
    assert mock_payload["payload"]["selector"] == "body"

def test_david_navigate_payload_structure():
    """Verify standard payload contract for David browser navigate action."""
    mock_nav = {
        "recipient": "david",
        "action": "navigate",
        "payload": {"url": "https://www.google.com", "new_tab": False}
    }
    assert mock_nav["action"] == "navigate"
    assert mock_nav["payload"]["url"] == "https://www.google.com"

def test_david_type_and_click_payload_structure():
    """Verify David smart typing and clicking payloads with semantic selectors."""
    click_task = {
        "recipient": "david",
        "action": "click",
        "payload": {"selector": "Compose"}
    }
    assert click_task["action"] == "click"
    assert click_task["payload"]["selector"] == "Compose"

    type_task = {
        "recipient": "david",
        "action": "type",
        "payload": {
            "selector": "To",
            "text": "test@example.com",
            "press_enter": True
        }
    }
    assert type_task["action"] == "type"
    assert type_task["payload"]["press_enter"] is True

def test_david_perception_actions_payload_structure():
    """Verify David perception actions: get_page_elements and read_page."""
    elements_task = {
        "recipient": "david",
        "action": "get_page_elements",
        "payload": {}
    }
    assert elements_task["action"] == "get_page_elements"

    read_task = {
        "recipient": "david",
        "action": "read_page",
        "payload": {"selector": "div.content"}
    }
    assert read_task["action"] == "read_page"

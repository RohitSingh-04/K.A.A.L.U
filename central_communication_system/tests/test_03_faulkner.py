from unittest.mock import patch, MagicMock
from faulkner_system.terminal_executor import TerminalExecutor
from faulkner_system.phone_link import PhoneLinkController

def test_faulkner_terminal_executor():
    """Directly test Faulkner's terminal execution logic without WebSocket overhead."""
    result = TerminalExecutor.run_command("echo 'Faulkner Unit Test'")
    
    assert result["success"] is True
    assert result["exit_code"] == 0
    assert "Faulkner Unit Test" in result["stdout"]


def test_phone_link_dial_with_direct_number():
    """Verify PhoneLinkController formats tel URI and triggers Windows shell handler."""
    with patch("os.startfile", create=True) as mock_startfile:
        res = PhoneLinkController.dial(target="+918477873189")
        assert res["success"] is True
        assert res["action"] == "phone_link_call"
        assert res["phone_number"] == "+918477873189"
        assert res["protocol_uri"] == "tel:+918477873189"
        assert res["app"] == "Microsoft Phone Link"
        mock_startfile.assert_any_call("tel:+918477873189")


def test_phone_link_dial_resolves_contact_name():
    """Verify PhoneLinkController automatically resolves 'Mom' to her phone number."""
    mock_contact = {"name": "Mom", "number": "+91 84778 73189", "clean_number": "+918477873189"}
    with patch.object(PhoneLinkController, "resolve_contact_number", return_value=mock_contact):
        with patch("os.startfile", create=True) as mock_startfile:
            res = PhoneLinkController.dial(target="Mom")
            assert res["success"] is True
            assert res["contact"] == "Mom"
            assert res["phone_number"] == "+918477873189"
            assert res["protocol_uri"] == "tel:+918477873189"
            mock_startfile.assert_any_call("tel:+918477873189")


def test_phone_link_open_app():
    """Verify open_app launches Phone Link via Windows AppsFolder / ms-phone protocol."""
    with patch("os.startfile", create=True) as mock_startfile:
        res = PhoneLinkController.open_app()
        assert res["success"] is True
        assert res["action"] == "open_phone_link"
        assert res["app"] == "Microsoft Phone Link"
        mock_startfile.assert_called_with("shell:AppsFolder\\Microsoft.YourPhone_8wekyb3d8bbwe!App")


def test_phone_link_send_sms():
    """Verify send_sms invokes sms protocol handler with encoded body."""
    mock_contact = {"name": "Mom", "clean_number": "+918477873189"}
    with patch.object(PhoneLinkController, "resolve_contact_number", return_value=mock_contact):
        with patch("os.startfile", create=True) as mock_startfile:
            res = PhoneLinkController.send_sms(target="Mom", message="Hello from Phone Link")
            assert res["success"] is True
            assert res["action"] == "phone_link_sms"
            assert res["phone_number"] == "+918477873189"


def test_phone_link_close_app():
    """Verify close_app sends WM_CLOSE / CloseMainWindow without terminating process."""
    mock_proc = MagicMock(returncode=0, stdout="SUCCESS", stderr="")
    with patch("subprocess.run", return_value=mock_proc):
        res = PhoneLinkController.close_app()
        assert res["success"] is True
        assert res["action"] == "close_phone_link"
        assert res["app"] == "Microsoft Phone Link"
        assert "taskbar" in res["message"]

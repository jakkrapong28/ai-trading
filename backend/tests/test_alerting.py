import pytest
from unittest.mock import patch, AsyncMock
from backend.alert import send_alert

@pytest.mark.asyncio
@patch("httpx.AsyncClient.post")
async def test_send_alert(mock_post):
    mock_post.return_value = AsyncMock(status_code=200)
    
    # Mock token and chat_id in environment
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"}):
        await send_alert("CRITICAL", "Test Alert Message")
        
        # Verify post is called to Telegram api endpoint
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert "telegram.org/botmock_token/sendMessage" in args[0]
        assert kwargs["json"]["text"] == "🚨 [CRITICAL] Test Alert Message"

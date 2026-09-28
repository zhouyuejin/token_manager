from fastapi.dependencies.utils import get_dependant

from app.api.v1.chat import send_message


def test_send_message_receives_request_context_for_request_id():
    dependant = get_dependant(path="/chats/{conversation_id}/messages", call=send_message)

    assert dependant.request_param_name == "request"

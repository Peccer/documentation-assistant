import os
import json
import uuid
import time
import logging

CONVERSATION_STORE_FILE = "conversations.json"

def _load_conversations():
    """
    Loads all conversations from the local JSON file.
    """
    if not os.path.exists(CONVERSATION_STORE_FILE):
        return {}
    try:
        with open(CONVERSATION_STORE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Could not load conversations file: {e}")
        return {}

def _save_conversations(conversations):
    """
    Saves all conversations to the local JSON file.
    """
    try:
        with open(CONVERSATION_STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(conversations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Could not save conversations file: {e}")

def create_conversation(title="Untitled Conversation"):
    """
    Creates a new conversation entry with a unique ID.
    """
    conversations = _load_conversations()
    conversation_id = str(uuid.uuid4())
    conversations[conversation_id] = {
        "id": conversation_id,
        "title": title,
        "messages": [],
        "created_at": time.time()
    }
    _save_conversations(conversations)
    return conversation_id

def get_conversation(conversation_id):
    """
    Returns a single conversation by ID, or None if not found.
    """
    conversations = _load_conversations()
    return conversations.get(conversation_id)

def list_conversations():
    """
    Returns a list of all conversations, sorted by creation time descending.
    """
    conversations = _load_conversations()
    # Return as a list
    conv_list = list(conversations.values())
    conv_list.sort(key=lambda c: c.get("created_at", 0), reverse=True)
    return conv_list

def delete_conversation(conversation_id):
    """
    Deletes the conversation with the specified ID.
    """
    conversations = _load_conversations()
    if conversation_id in conversations:
        del conversations[conversation_id]
        _save_conversations(conversations)
        return True
    return False

def add_message_to_conversation(conversation_id, role, content):
    """
    Adds a message to a conversation (role = 'user' or 'assistant'),
    returns the updated conversation or None if not found.
    """
    conversations = _load_conversations()
    conv = conversations.get(conversation_id)
    if not conv:
        return None
    
    # Create a new message
    message = {
        "role": role,
        "content": content,
        "timestamp": time.time()
    }
    conv["messages"].append(message)
    conversations[conversation_id] = conv
    _save_conversations(conversations)
    return conv

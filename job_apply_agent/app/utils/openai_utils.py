"""Shared OpenAI utilities."""

import os
import json
import openai


def ensure_api_key_set():
    """Ensure OpenAI API key is available in environment.
    
    Reads OPENAI_API_KEY from environment and sets it in openai module.
    
    Raises:
        ValueError: If OPENAI_API_KEY environment variable is not set
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY not set. Please set it in your .env file or environment variables."
        )
    openai.api_key = api_key


def call_openai_for_json(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> dict:
    """Call OpenAI API and parse JSON response.
    
    Handles the common pattern: send prompts → get response → parse JSON.
    
    Args:
        system_prompt: System message (instructions for the model)
        user_prompt: User message (the actual data to parse)
        max_tokens: Maximum tokens in response (default 1500)
        
    Returns:
        Parsed JSON response as dict
        
    Raises:
        ValueError: If API call fails or response is invalid JSON
    """
    ensure_api_key_set()
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,  # Deterministic output for parsing
            max_tokens=max_tokens,
        )
        
        response_text = response["choices"][0]["message"]["content"].strip()
        parsed = json.loads(response_text)
        return parsed
        
    except json.JSONDecodeError as e:
        raise ValueError(f"OpenAI response was not valid JSON: {e}")
    except Exception as e:
        raise ValueError(f"OpenAI API call failed: {e}")


def fill_defaults(data: dict, defaults: dict) -> dict:
    """Fill in missing keys with default values.
    
    Ensures all expected keys are present in the dict.
    
    Args:
        data: Dict with potentially missing keys
        defaults: Dict of key -> default_value
        
    Returns:
        Dict with all keys from defaults, using values from data if present
    """
    result = dict(data)  # Start with provided data
    for key, default_val in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default_val
    return result

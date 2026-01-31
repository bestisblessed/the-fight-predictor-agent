import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

import requests

DATASET_FILES = [
    ("fighter_info.csv", "OPENAI_FIGHTER_INFO_FILE_ID"),
    ("event_data_sherdog.csv", "OPENAI_EVENT_DATA_FILE_ID"),
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _read_cache(cache_path: Optional[str]) -> Dict[str, str]:
    if not cache_path or not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        return {}
    return {}


def _write_cache(cache_path: Optional[str], mapping: Dict[str, str]) -> None:
    if not cache_path:
        return
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f)
    except Exception:
        return


def get_dataset_file_ids(
    client: Any,
    data_dir: str = "data",
    cache_path: Optional[str] = None,
    dataset_files: Optional[Iterable[tuple]] = None,
) -> List[str]:
    dataset_files = dataset_files or DATASET_FILES
    cached = _read_cache(cache_path)
    file_ids: Dict[str, str] = {}
    missing_paths: List[str] = []

    for filename, env_var in dataset_files:
        file_id = os.getenv(env_var) or cached.get(filename)
        if file_id:
            file_ids[filename] = file_id
            continue

        local_path = os.path.join(data_dir, filename)
        if not os.path.exists(local_path):
            missing_paths.append(local_path)
            continue

        with open(local_path, "rb") as f:
            uploaded = client.files.create(file=f, purpose="assistants")
        file_ids[filename] = uploaded.id

    if missing_paths:
        missing = ", ".join(missing_paths)
        env_hint = ", ".join([env for _, env in dataset_files])
        raise FileNotFoundError(
            "Missing dataset files: "
            f"{missing}. Provide the files or set {env_hint}."
        )

    _write_cache(cache_path, file_ids)
    return list(file_ids.values())


def build_input_messages(
    user_text: str,
    file_ids: Iterable[str],
    system_prompt: Optional[str] = None,
) -> List[Dict[str, Any]]:
    content: List[Dict[str, Any]] = [{"type": "input_text", "text": user_text}]
    for file_id in file_ids:
        content.append({"type": "input_file", "file_id": file_id})

    messages: List[Dict[str, Any]] = []
    if system_prompt:
        messages.append(
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            }
        )
    messages.append({"role": "user", "content": content})
    return messages


def create_response(
    client: Any,
    model: str,
    user_text: str,
    file_ids: Iterable[str],
    system_prompt: Optional[str] = None,
    previous_response_id: Optional[str] = None,
) -> Any:
    params: Dict[str, Any] = {
        "model": model,
        "input": build_input_messages(user_text, file_ids, system_prompt),
        "tools": [{"type": "code_interpreter"}],
    }
    if previous_response_id:
        params["previous_response_id"] = previous_response_id
    return client.responses.create(**params)


def extract_text(response: Any) -> Optional[str]:
    output_text = _get(response, "output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    collected: List[str] = []
    output_items = _get(response, "output", []) or []
    for item in output_items:
        content_items = _get(item, "content", []) or []
        for part in content_items:
            part_type = _get(part, "type")
            if part_type not in (None, "output_text", "text"):
                continue
            text_payload = _get(part, "text")
            if isinstance(text_payload, str):
                collected.append(text_payload)
                continue
            if text_payload:
                value = _get(text_payload, "value") or _get(text_payload, "text")
                if isinstance(value, str):
                    collected.append(value)

    joined = "\n".join([text for text in collected if text]).strip()
    return joined or None


def extract_file_entries(response: Any) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    output_items = _get(response, "output", []) or []

    for item in output_items:
        content_items = _get(item, "content", []) or []
        for part in content_items:
            part_type = _get(part, "type") or ""
            file_id = _get(part, "file_id")
            if not file_id:
                image_file = _get(part, "image_file")
                if image_file:
                    file_id = _get(image_file, "file_id") or _get(image_file, "id")
            if not file_id:
                image = _get(part, "image")
                if image:
                    file_id = _get(image, "file_id") or _get(image, "id")
            if file_id:
                entries.append({"file_id": file_id, "type": part_type})

    return entries


def _get_filename(client: Any, file_id: str) -> Optional[str]:
    try:
        metadata = client.files.retrieve(file_id)
        return _get(metadata, "filename")
    except Exception:
        return None


def download_file_content(client: Any, file_id: str, api_key: Optional[str]) -> bytes:
    try:
        content = client.files.content(file_id)
        if hasattr(content, "read"):
            return content.read()
        if isinstance(content, bytes):
            return content
        if hasattr(content, "content"):
            return content.content
    except Exception:
        pass

    if not api_key:
        raise RuntimeError("OpenAI API key is required to fetch file content.")

    url = f"https://api.openai.com/v1/files/{file_id}/content"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.content


def save_response_files(
    client: Any,
    file_entries: Iterable[Dict[str, str]],
    output_dir: str,
    filename_prefix: str,
    api_key: Optional[str] = None,
) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    saved_paths: List[str] = []

    for index, entry in enumerate(file_entries):
        file_id = entry.get("file_id")
        if not file_id:
            continue
        part_type = (entry.get("type") or "").lower()

        filename = _get_filename(client, file_id)
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        if not ext:
            ext = ".png" if "image" in part_type else ".bin"

        output_path = os.path.join(output_dir, f"{filename_prefix}_{index}{ext}")
        data = download_file_content(client, file_id, api_key)
        with open(output_path, "wb") as f:
            f.write(data)
        saved_paths.append(output_path)

    return saved_paths


def save_response_image(
    client: Any,
    file_entries: Iterable[Dict[str, str]],
    output_path: str,
    api_key: Optional[str] = None,
) -> Optional[str]:
    file_entries = list(file_entries)
    if not file_entries:
        return None

    chosen = None
    for entry in file_entries:
        if "image" in (entry.get("type") or "").lower():
            chosen = entry
            break

    if not chosen:
        for entry in file_entries:
            filename = _get_filename(client, entry.get("file_id", ""))
            if filename and os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS:
                chosen = entry
                break

    if not chosen:
        chosen = file_entries[0]

    data = download_file_content(client, chosen["file_id"], api_key)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(data)
    return output_path


def get_response_id(response: Any) -> Optional[str]:
    response_id = _get(response, "id")
    if isinstance(response_id, str):
        return response_id
    return None


def default_cache_path(data_dir: str) -> str:
    filename = "openai_dataset_file_ids.json"
    return os.path.join(data_dir, filename)


def unique_filename_prefix(base: str) -> str:
    timestamp = int(time.time())
    return f"{base}_{timestamp}"

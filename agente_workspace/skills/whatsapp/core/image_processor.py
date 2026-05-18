"""Image processing for WhatsApp skill."""

import json
import base64
from pathlib import Path
from skills.whatsapp.routing.remote_client import RemoteClient
from skills.whatsapp.utils.config import Config

CONFIG = Config()
REMOTE = RemoteClient()
DESCR_DIR = CONFIG.PROJECT_DIR / 'data' / 'descriptions'
DESCR_DIR.mkdir(parents=True, exist_ok=True)
SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
PROMPT = """You are analyzing an image from a WhatsApp conversation.\nDescribe what you see in detail: people, objects, text, context, emotions, setting. Be concise but complete. Answer in English."""


def encode_image(image_path: Path) -> str:
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def describe_image(image_path: Path, msg_id: int, router=None) -> dict:
    result_path = DESCR_DIR / f"{msg_id:04d}_{image_path.stem}.json"
    if result_path.exists():
        with open(result_path, encoding='utf-8') as f:
            cached = json.load(f)
        if not cached.get('error'):
            return cached

    if image_path.suffix.lower() not in SUPPORTED:
        return {'id': msg_id, 'text': None, 'error': f'Unsupported format: {image_path.suffix}'}

    try:
        image_data = encode_image(image_path)
        route = router.route_vision({"filepath": str(image_path)}) if router else None
        route_used = None
        if route:
            try:
                raw = REMOTE.generate(
                    generate_url=route.host,
                    model=route.model,
                    prompt=PROMPT,
                    images=[image_data],
                    timeout=route.timeout,
                )
                route_used = route.key
                if not (raw.get('response') or '').strip():
                    # Empty local output is treated as degraded result and retried on DGX.
                    fallback = router.route_fallback("vision")
                    raw = REMOTE.generate(
                        generate_url=fallback.host,
                        model=fallback.model,
                        prompt=PROMPT,
                        images=[image_data],
                        timeout=fallback.timeout,
                    )
                    route_used = fallback.key
            except Exception:
                fallback = router.route_fallback("vision")
                raw = REMOTE.generate(
                    generate_url=fallback.host,
                    model=fallback.model,
                    prompt=PROMPT,
                    images=[image_data],
                    timeout=fallback.timeout,
                )
                route_used = fallback.key
        else:
            raw = REMOTE.generate(
                generate_url=f"{CONFIG.LOCAL_OLLAMA_URL}/api/generate",
                model=CONFIG.VISION_MODEL,
                prompt=PROMPT,
                images=[image_data],
                timeout=CONFIG.TIMEOUTS['vision'],
            )
            route_used = 'local_default_vision'
        description = raw.get('response', '').strip()
        result = {
            'id': msg_id,
            'original': str(image_path),
            'text': description,
            'error': None,
            'route': route_used,
        }
    except Exception as e:
        result = {'id': msg_id, 'original': str(image_path), 'text': None, 'error': str(e), 'route': None}

    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def process_images(messages: list, router) -> list:
    tasks = [m for m in messages if m['type'] == 'image' and m.get('filepath')]
    if not tasks:
        print('No images to process.')
        return messages

    print(f'\nDescribing {len(tasks)} images with {CONFIG.VISION_MODEL}...')
    for msg in tasks:
        print(f"[{msg['id']:03d}] {msg['sender']} - {msg['filename']}")
        result = describe_image(Path(msg['filepath']), msg['id'], router=router)
        msg['result'] = result.get('text')
        msg['processed'] = True
        if result.get('error'):
            print(f"  ERROR: {result['error']}")
        else:
            print(f"  OK: {result['text'][:80]}...")
    return messages

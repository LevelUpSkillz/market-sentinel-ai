import json
from pathlib import Path
import httpx
import yaml
from jsonschema import validate
root=Path(__file__).resolve().parents[1]
response=httpx.get('https://render.com/schema/render.yaml.json',timeout=30)
response.raise_for_status()
schema=response.json()
validate(yaml.safe_load((root/'render.yaml').read_text()),schema)
print('Render Blueprint schema validation passed')

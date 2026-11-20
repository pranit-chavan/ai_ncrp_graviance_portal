"""Run the English citizen portal using only local inference services."""
import argparse
import os
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8503)
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    gpu_python = ROOT / '.venv-gpu' / 'Scripts' / 'python.exe'
    if gpu_python.is_file() and Path(sys.executable).resolve() != gpu_python.resolve():
        result = subprocess.run([str(gpu_python), str(Path(__file__).resolve()), *sys.argv[1:]], check=False)
        raise SystemExit(result.returncode)
    os.environ['CYBERASSIST_OFFLINE'] = '1'
    os.environ['INTAKE_LLM_PROVIDER'] = 'ollama'
    os.environ['LLM_PROVIDER'] = 'ollama'
    os.environ['OLLAMA_MODEL'] = os.getenv('CYBERASSIST_MODEL', 'qwen2.5:3b')
    os.environ['OLLAMA_URL'] = 'http://127.0.0.1:11434'
    os.environ['WHISPER_MODEL'] = os.getenv('CYBERASSIST_SPEECH_MODEL', 'small.en')
    device = os.getenv('CYBERASSIST_SPEECH_DEVICE', 'auto')
    if device == 'auto':
        try:
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        except Exception:
            device = 'cpu'
    os.environ['WHISPER_DEVICE'] = device
    print(f"Using local language model {os.environ['OLLAMA_MODEL']} and Whisper {os.environ['WHISPER_MODEL']} ({device}).")
    import uvicorn
    uvicorn.run('server:app', host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()

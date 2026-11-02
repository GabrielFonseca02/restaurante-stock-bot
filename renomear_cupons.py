"""Renomeação determinística com manifesto e hashes para auditoria."""
import hashlib
import json
import re
from pathlib import Path


def main():
    pasta = Path(__file__).resolve().parent / 'receipts/personal'
    arquivos = sorted((p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in {'.jpeg', '.jpg', '.png'}),
                      key=lambda p: [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', p.name)])
    existentes = [int(m.group(1)) for p in arquivos if (m := re.fullmatch(r'cupom-(\d+)\.[^.]+', p.name))]
    numero = max(existentes, default=0) + 1
    plano = []
    for arquivo in arquivos:
        if re.fullmatch(r'cupom-\d+\.[^.]+', arquivo.name):
            continue
        destino = pasta / f'cupom-{numero:03d}{arquivo.suffix.lower()}'
        if destino.exists():
            raise FileExistsError(destino)
        plano.append(dict(original=arquivo.name, novo=destino.name,
                          sha256=hashlib.sha256(arquivo.read_bytes()).hexdigest()))
        numero += 1
    if not plano:
        print('Nenhum arquivo pendente de renomeação.')
        return
    manifesto = pasta / 'renomeacao.json'
    if manifesto.exists():
        raise FileExistsError('Preserve o manifesto anterior antes de uma nova renomeação.')
    manifesto.write_text(json.dumps(plano, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in plano:
        (pasta / item['original']).rename(pasta / item['novo'])
    print(f'{len(plano)} arquivos renomeados; último: {plano[-1]["novo"]}')


if __name__ == '__main__':
    main()

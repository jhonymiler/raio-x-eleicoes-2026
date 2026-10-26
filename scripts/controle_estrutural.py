#!/usr/bin/env python3
"""Controle estrutural: roda Benford em variaveis que NAO sao votos de
candidato -- eleitorado apto, comparecimento, abstencao, total de votos.

Se essas variaveis exibirem a mesma assinatura de digitos que um candidato,
a assinatura vem da geografia municipal brasileira, nao do candidato e
muito menos de manipulacao.

Fonte: detalhe_votacao_munzona_2026_BRASIL.csv (dados abertos do TSE),
agregado de zona para municipio.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402
from analisar import bloco, linha_gate  # noqa: E402

DADOS = Path(__file__).parent.parent / "dados"
SAIDA = Path(__file__).parent.parent / "resultados"

COLUNAS = {
    "QT_APTOS": "eleitorado apto",
    "QT_COMPARECIMENTO": "comparecimento",
    "QT_ABSTENCOES": "abstencoes",
    "QT_TOTAL_VOTOS_VALIDOS": "votos validos",
    "QT_VOTOS_BRANCOS": "votos brancos",
    "QT_VOTOS_NULOS": "votos nulos",
}


def main() -> None:
    caminho = DADOS / "detalhe_munzona" / "detalhe_votacao_munzona_2026_BRASIL.csv"
    por_mun: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    with open(caminho, encoding="latin-1", newline="") as fh:
        leitor = csv.DictReader(fh, delimiter=";", quotechar='"')
        disponiveis = [c for c in COLUNAS if c in leitor.fieldnames]
        for r in leitor:
            if r.get("CD_CARGO") != "1" or r.get("NR_TURNO") != "1" or r.get("SG_UF") == "ZZ":
                continue
            chave = f"{r['SG_UF']}-{r['CD_MUNICIPIO']}"
            for col in disponiveis:
                try:
                    por_mun[chave][col] += int(r[col])
                except (ValueError, KeyError):
                    pass

    L: list[str] = []
    w = L.append
    w("=" * 78)
    w("CONTROLE ESTRUTURAL -- variaveis que ninguem manipula")
    w("=" * 78)
    w(f"municipios: {len(por_mun):,}  |  1o turno, cargo Presidente")
    w("")
    w("Se a assinatura de digitos destas variaveis for igual a de um")
    w("candidato, a assinatura e da geografia, nao do candidato.")
    w("")

    for col in disponiveis:
        serie = [m[col] for m in por_mun.values() if m[col] > 0]
        if len(serie) < 500:
            continue
        w(f"--- {COLUNAS[col]}  ({col}) ---")
        g, _ = linha_gate(serie, "municipio")
        w(g)
        r1 = bf.avaliar("1o digito", serie, bf.primeiro_digito,
                        bf.p_primeiro_digito())
        r1.kuiper_v, r1.p_kuiper, _ = bf.kuiper_mantissa(serie)
        w(bloco(r1, "primeiro digito", top=9))
        w("")

    texto = "\n".join(L)
    SAIDA.mkdir(parents=True, exist_ok=True)
    (SAIDA / "controle_estrutural.txt").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()

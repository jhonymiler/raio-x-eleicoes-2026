#!/usr/bin/env python3
"""Analise de Benford sobre os totais por municipio do 2o turno.

Le os totais finais de totais_2t.py (nao o retrato parcial de
coletar_2t.py), sem os municipios do exterior. So existe o nivel municipio (a API
de divulgacao nao expoe votos por secao), entao roda o teste de primeiro
digito, que e o valido nessa faixa, mais dois primeiros digitos, Kuiper
e invariancia de soma.

Uso:  python3 analisar_2t.py [cd_eleicao]
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import benford as bf  # noqa: E402
import totais_2t  # noqa: E402
from analisar import bloco, linha_gate  # noqa: E402

SAIDA = Path(__file__).parent.parent / "resultados"


def main(cd: str = "6258") -> None:
    linhas, meta = totais_2t.ler(cd)          # totais finais, exterior excluido

    series: dict[str, list[int]] = defaultdict(list)
    nomes: dict[str, str] = {}
    por_mun: dict[str, dict[str, int]] = defaultdict(dict)
    for r in linhas:
        v = r["qt_votos"]
        if v > 0:
            series[r["nr_votavel"]].append(v)
            nomes.setdefault(r["nr_votavel"], r["nm_votavel"])
            chave = f"{r['uf']}-{r['cd_municipio']}"
            por_mun[chave][r["nr_votavel"]] = v

    L: list[str] = []
    w = L.append
    w("=" * 78)
    w("ANALISE FORENSE DE BENFORD -- 2o TURNO (totais por municipio)")
    w("=" * 78)
    w(f"fonte              : {meta['fonte']} (exterior excluido)")
    w(f"secoes totalizadas : {meta['secoes_totalizadas']:,} de "
      f"{meta['secoes_esperadas']:,}  ({meta['pct_totalizado']}%)")
    w(f"totalizacao encerrada: {meta['totalizacao_encerrada']}")
    w(f"municipios          : {meta['municipios']:,} "
      f"({meta['municipios_encerrados']:,} encerrados)")
    if not meta["totalizacao_encerrada"]:
        w("")
        w("!! APURACAO PARCIAL. Totais municipais incompletos misturam")
        w("!! municipios 100% apurados com municipios pela metade. Isso")
        w("!! distorce os digitos por construcao. Os numeros abaixo sao um")
        w("!! retrato do instante, NAO uma auditoria. Rode de novo com")
        w("!! 'totalizacao_encerrada: true'.")
    w("")

    for nr in sorted(series, key=lambda k: -sum(series[k])):
        serie = series[nr]
        if len(serie) < 500:
            continue
        w(f"[{nr}] {nomes[nr]}   total = {sum(serie):,}")
        g, aplicavel = linha_gate(serie, "municipio")
        w(g)
        r1 = bf.avaliar("1o digito", serie, bf.primeiro_digito,
                        bf.p_primeiro_digito())
        r1.kuiper_v, r1.p_kuiper, _ = bf.kuiper_mantissa(serie)
        w(bloco(r1, "primeiro digito"))
        r2 = bf.avaliar("2 primeiros digitos", serie, bf.dois_primeiros,
                        bf.p_dois_primeiros())
        w(bloco(r2, "dois primeiros", top=6))
        inv = bf.invariancia_soma(serie)
        w("    invariancia de soma (esperado 11.11% por digito):")
        w("      " + "  ".join(f"{d}:{inv[d]*100:5.2f}%" for d in range(1, 10)))
        w("")

    # ---- decomposicao porte x share, comparavel ao controle de 2022 ----
    muns = [m for m in por_mun if sum(por_mun[m].values()) > 0]
    tot = {m: sum(por_mun[m].values()) for m in muns}
    base = bf.fourier_empirico([tot[m] for m in muns])["phi"][1]
    w("=" * 78)
    w("DECOMPOSICAO DE FOURIER  (votos = porte x share)")
    w("=" * 78)
    w("Sob independencia |phi_V| = |phi_P| x |phi_S| <= |phi_P|: um fator")
    w("multiplicativo independente so pode APROXIMAR de Benford. Razao >> 1")
    w("prova acoplamento na frequencia 2pi -- estrutura, nao manipulacao.")
    w("")
    w(f"porte municipal (votos validos): |phi(2pi)| = {base:.4f}")
    w("")
    w(f"    {'candidato':<26} {'|phi_V|':>8} {'|phi_S|':>8} "
      f"{'esperado':>9} {'razao':>7}  {'share':>6}")
    w("    " + "-" * 70)
    for nr in sorted(series, key=lambda k: -sum(series[k])):
        v = [por_mun[m].get(nr, 0) for m in muns]
        if sum(1 for x in v if x > 0) < 500:
            continue
        s = [por_mun[m][nr] / tot[m] for m in muns if por_mun[m].get(nr, 0) > 0]
        pv = bf.fourier_empirico([x for x in v if x > 0])["phi"][1]
        ps = bf.fourier_empirico(s)["phi"][1]
        esp = base * ps
        razao = pv / esp if esp else 0.0
        marca = "  <<<" if razao > 2 else ""
        w(f"    {nomes[nr][:26]:<26} {pv:>8.4f} {ps:>8.4f} "
          f"{esp:>9.4f} {razao:>6.2f}x  {sum(s)/len(s):>5.3f}{marca}")
    w("")
    w("Referencia historica (mesmo calculo: sem exterior, porte = votos validos):")
    w("    Jair Bolsonaro  2022 1T = 2.93x   2022 2T = 2.87x")
    w("    Lula            2022 1T = 0.49x   2022 2T = 0.47x")
    w("")

    texto = "\n".join(L)
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"benford_2o_turno_{cd}.txt"
    destino.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"\n[gravado em {destino}]")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "6258")

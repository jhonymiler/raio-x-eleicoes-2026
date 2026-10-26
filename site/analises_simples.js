'use strict';
/* Textos em linguagem simples para cada análise. A versão técnica continua em pistas.json. */

const SIMPLES = {
  integridade: {
    pergunta: 'O resultado oficial é a soma das urnas?',
    resposta: 'Sim, nos dois turnos. No 1º, somamos os boletins das 499.206 urnas; no 2º, os boletins assinados de 12.746 urnas de 108 cidades sorteadas inteiras. Tudo bate voto a voto.',
    fraude: 'O número impresso no boletim de alguma urna seria diferente do número que o TSE divulgou para ela.',
    normal: 'Cada boletim bate exatamente com o resultado divulgado.',
    vimos: 'Nenhuma diferença em 3,8 milhões de linhas conferidas, em todos os estados. Isso descarta mexida na transmissão e na contagem, mas não testa o que acontece dentro da urna.',
  },
  logs: {
    pergunta: 'O “diário” de cada urna confirma o boletim?',
    resposta: 'Sim. Cada urna anota, com a hora, cada eleitor liberado e cada voto. Esse diário bate com o boletim em todas as urnas que olhamos.',
    fraude: 'Votos sem eleitor, vários votos em poucos segundos, ou uma enxurrada de eleitores liberados sem digital na última hora.',
    normal: 'Mais ou menos um voto a cada 2 minutos, espalhados pelo dia, e só 4 a 9 em cada 100 eleitores liberados sem digital.',
    vimos: 'As 988 urnas que tinham chamado atenção batem com o boletim. Em 10.800 urnas sorteadas, nos dois turnos, nenhuma teve enxurrada de liberações no fim do dia.',
  },
  biometria: {
    pergunta: 'Onde muita gente votou sem digital, o Lula foi melhor?',
    resposta: 'Um pouco, mas a causa é a idade: a digital dos idosos falha mais, e os idosos votam mais no Lula. Comparando seções com a mesma idade, a diferença some.',
    fraude: 'Mesários liberando gente sem digital para votar no lugar de quem faltou.',
    normal: 'O leitor de digital falha mais com pessoas idosas, que têm as digitais mais gastas.',
    vimos: 'Sem levar a idade em conta, essas seções davam 8,4 pontos a mais ao Lula. Levando a idade em conta, 0,3 ponto: praticamente nada. Nos diários dessas urnas, a digital falha desde o primeiro eleitor da manhã até o fim do dia, como um leitor com defeito.',
  },
  klimek: {
    pergunta: 'Seções em que quase todo mundo votou no mesmo candidato',
    resposta: 'São aldeias indígenas, quilombos e comunidades pequenas que já votavam assim em 2022. Quase todos os eleitores se identificaram pela própria digital.',
    fraude: 'Urnas “completadas” com votos de quem não apareceu.',
    normal: 'Comunidades pequenas e unidas costumam votar em bloco e ir votar em massa.',
    vimos: '65 seções (62 para o Lula, 3 para o Flávio). Das 21 que já existiam em 2022, 18 já davam 90% ou mais ao mesmo candidato. 92 de cada 100 eleitores se identificaram pela digital.',
  },
  escola: {
    pergunta: 'Urnas que votaram muito diferente das outras da mesma escola',
    resposta: '185 urnas, de 451 mil (4 em cada 10 mil). No 2º turno, com as urnas recarregadas, 172 de 173 voltaram a destoar do mesmo jeito: é o perfil de quem vota ali, não a urna. Juntas, mudariam no máximo 3.460 votos.',
    fraude: 'Uma urna adulterada votaria diferente das vizinhas, porque na mesma escola os eleitores costumam ser parecidos.',
    normal: 'Algumas urnas têm um público diferente, como uma seção nova só com jovens que acabaram de tirar o título.',
    vimos: '123 pendem para o Lula e 62 para o Flávio. Das 60 que já existiam em 2022, 55 já eram diferentes do mesmo jeito. As outras 125 são urnas novas, com eleitores mais jovens. O diário dessas urnas é normal.',
    conferimos: 'Baixamos o boletim assinado do 2º turno dessas urnas e das vizinhas de escola. 172 de 173 destoaram de novo, no mesmo sentido e com a mesma força. Uma urna adulterada no 1º turno não repetiria o desvio no 2º, com software recarregado. Só uma seção, em Camaçari (BA), destoou no 1º e não no 2º: dezenas de votos.',
  },
  viradas: {
    pergunta: 'Cidades que trocaram de vencedor desde 2022',
    resposta: 'No 1º turno, 7 cidades trocaram de lado, acima do normal. Comparando 2º turno com 2º turno, só 3 mudam fora do padrão, e nas 3 há políticos fortes da própria cidade puxando votos.',
    fraude: 'Só algumas urnas da cidade mudariam; as outras ficariam iguais a 2022.',
    normal: 'Um político forte da própria cidade (prefeito, candidato a deputado) leva o eleitorado junto.',
    vimos: 'Em 6 das 7 cidades, 100% das urnas andaram na mesma direção. Em 3 delas, candidatos a deputado da própria cidade tiveram de 26% a 43% dos votos locais, contra menos de 6% no estado.',
    conferimos: 'Repetimos o teste com os dois finalistas frente a frente (2º turno de 2022 × 2º turno de 2026). Sobram 3 cidades: São Julião e Pedro Laurentino (PI), com deputados do PT da cidade, e Belo Monte (AL), com deputados do MDB, que foi para o lado do Flávio. As 7 do 1º turno vinham da divisão dos votos entre 13 candidatos.',
  },
  crescimento: {
    pergunta: 'Cidades onde o número de votos cresceu demais desde 2022',
    resposta: '17 cidades. A população delas cresceu de verdade, e em todas o Lula perdeu espaço desde 2022: os eleitores novos não favoreceram quem ganhou.',
    fraude: 'Eleitores que não existem, ou títulos transferidos de gente que não mora na cidade.',
    normal: 'A cidade ganhou moradores de verdade.',
    vimos: 'Nessas cidades os novos eleitores foram votar, e a maioria se identificou pela digital. Só uma (Anhangüera, GO) tem o padrão de título de quem não mora lá: muitos eleitores novos e pouca gente votando.',
    conferimos: 'Comparamos com o Censo 2022 e a estimativa de 2025 do IBGE: em 11 das 17 a população cresceu mais que o dobro da média do país. O eleitorado cresceu ainda mais que a população, o padrão de quem transfere o título para a cidade da casa de praia ou do trabalho. Isso é cadastro, que o TRE revisa de rotina, e não mexeu no resultado a favor do Lula.',
  },
  horarios: {
    pergunta: 'Urnas que abriram cedo ou fecharam antes da hora',
    resposta: 'Nenhuma. 955 urnas abriram com mais de meia hora de atraso, o que é problema de organização, não de resultado.',
    fraude: 'Urnas recebendo votos antes da abertura, ou fechadas antes das 17h.',
    normal: 'Todas abrem às 8h e fecham às 17h, no horário de Brasília.',
    vimos: 'Nenhuma urna abriu antes da hora nem fechou antes das 17h. Os primeiros alertas eram erro nosso: o oeste do Amazonas tem outro fuso horário.',
  },
  ultimo_digito: {
    pergunta: 'Os números foram inventados à mão?',
    resposta: 'Não. Quem inventa números costuma escolher finais “redondos”, 0 e 5. Isso não aparece em nenhum estado.',
    fraude: 'Sobrariam votos terminados em 0 e em 5.',
    normal: 'Os finais de 0 a 9 aparecem quase na mesma quantidade.',
    vimos: 'Nenhum estado tem excesso de finais 0 e 5.',
  },
  estados: {
    pergunta: 'Algum estado mudou de um jeito estranho desde 2022?',
    resposta: 'Não. O que mais mudou foi Goiás, e lá o governador Ronaldo Caiado era candidato a presidente.',
    fraude: 'Um estado mudaria muito mais que os outros, sem motivo.',
    normal: 'Cada estado muda um pouco, conforme os candidatos da região.',
    vimos: 'Todos os estados ficaram dentro da variação normal.',
  },
  benford: {
    pergunta: 'A urna eletrônica mudou o padrão dos números?',
    resposta: 'Não. Um teste matemático clássico (Lei de Benford) aponta desvios na mesma proporção no voto em papel de 1994 e na urna eletrônica: 13% e 12%.',
    fraude: 'Os desvios ficariam mais frequentes depois que a urna eletrônica chegou.',
    normal: 'Os desvios aparecem com a mesma frequência antes e depois da urna.',
    vimos: '13 em cada 100 testes com desvio no papel; 12 em cada 100 na urna.',
  },
  exterior: {
    pergunta: 'Seções no exterior com o mesmo número de urna',
    resposta: 'Não é problema: essas seções votaram em cédula de papel, e o número é o do computador que digitou os votos depois.',
    fraude: 'Uma mesma urna usada em vários lugares.',
    normal: 'Votação em papel, digitada depois num mesmo computador.',
    vimos: '28 seções, todas sem horário de abertura, porque nelas não houve urna.',
  },
  segundo_turno: {
    pergunta: 'De onde vieram os votos que o Lula ganhou no 2º turno?',
    resposta: 'Dos eleitores dos 11 candidatos que saíram da disputa, de quem votou branco ou nulo no 1º turno e de quem só foi votar no 2º. A conta fecha em todas as 5.571 cidades.',
    fraude: 'O Lula ganharia mais votos do que havia disponíveis, ou ganharia igual em todo lugar, até onde os eleitores eliminados eram de direita.',
    normal: 'O Lula ganharia mais onde os eliminados eram de centro ou esquerda, e menos onde eram de direita.',
    vimos: 'Havia cerca de 14 milhões de votos “soltos”, e o Lula ficou com 74% deles. Onde esses votos eram quase todos de direita, ele levou 57%; onde eram menos de direita, até 91%. É o padrão de eleitores escolhendo.',
    conferimos: 'Nas 938 cidades onde o Flávio perdeu votos, em 728 menos gente foi votar no 2º turno, e isso explica 121 mil dos 134 mil votos que ele perdeu. Nos diários dessas urnas, os votos caem 4,7% e a identificação pela digital fica igual (91%), sem enxurrada no fim do dia. Sobram 12.683 votos em 210 cidades e 21.487 eleitores que trocaram o Flávio pelo Lula em 290 cidades: no máximo uns 56 mil votos na diferença, 1,3% dela.',
  },
  cadastro: {
    pergunta: 'Há cidades com mais eleitores do que moradores?',
    resposta: 'Sim: 718 cidades. Mas 532 delas já tinham mais eleitores que moradores no Censo de 2022, que conta pessoa por pessoa: o excesso é antigo. E essas cidades se moveram menos para o Lula. Pior caso: 709 mil votos, um sexto da diferença.',
    fraude: 'Eleitores que não existem votando a favor de quem ganhou.',
    normal: 'Quem se muda para a cidade grande costuma manter o título na cidade natal. A lei permite.',
    vimos: 'São quase todas cidades pequenas de MG, GO, PI e RS. E elas se moveram menos para o Lula que as vizinhas, o contrário do que faria uma fraude a favor dele.',
    conferimos: 'Cruzamos o eleitorado de 2022 com a contagem do Censo 2022: 532 das 718 já estavam acima da população, com 193 mil eleitores a mais. É título de quem saiu da cidade e não transferiu, comum em cidades pequenas de MG, GO, PI e RS.',
  },
  ponto_cego: {
    pergunta: 'A urna gravou exatamente o voto que o eleitor digitou?',
    resposta: 'Não dá para testar com os arquivos públicos. Esse ponto é coberto pelo teste em que urnas sorteadas votam em paralelo com cédulas de papel, com filmagem e acompanhamento do TCU.',
    fraude: 'A urna gravaria um voto diferente do digitado.',
    normal: 'A urna grava o voto digitado.',
    vimos: 'Fora do alcance desta investigação.',
  },
  prorrogacao: {
    pergunta: 'A votação até 19h trouxe uma enxurrada de votos para o Lula?',
    resposta: 'Não. Quase todas as urnas fecharam às 17h. Só 741 de 2,7 milhões de votos da amostra vieram depois das 17h.',
    fraude: 'Muitos votos chegando depois das 17h, aproveitando a decisão do ministro Zanin.',
    normal: 'A prorrogação mal foi aplicada: muitos mesários não foram avisados e fecharam às 17h.',
    vimos: 'No 2º turno, com prorrogação, houve menos voto depois das 17h (0,03%) do que no 1º turno, sem prorrogação (3,5%). No país inteiro, isso dá no máximo uns 39 mil votos: mesmo que todos fossem do Lula, seria menos de 1% da diferença.',
  },
};

const LADO = {
  'sem sinal': ['ok', '✓', 'Os dados se parecem com o lado <b>normal</b>.'],
  'explicada': ['ok', '✓', 'Os dados se parecem com o lado <b>normal</b>.'],
  'explicada em parte': ['meio', '◐', 'Em parte normal, em parte <b>ainda sem explicação</b>.'],
  'aberta': ['aberto', '?', 'Ainda <b>não dá para descartar</b>. Vale conferir.'],
  'fora do alcance': ['fora', '–', 'Os dados públicos <b>não permitem</b> testar.'],
};

/* ---------- visuais simples ---------- */
function pilha(titulo, segs, comoLer) {
  const tot = segs.reduce((s, x) => s + x.v, 0);
  return `<div class="viz"><h4>${titulo}</h4>
    <div class="pilha" role="img" aria-label="${esc(segs.map(s => `${s.rot}: ${P(s.v / tot, 0)}`).join(', '))}">${segs.map(s => `<i style="width:${s.v / tot * 100}%;background:${s.cor}">${s.v / tot > .09 ? P(s.v / tot, 0) : ''}</i>`).join('')}</div>
    <div class="pilha-leg">${segs.map(s => `<span><i style="background:${s.cor}"></i>${s.rot}: <b>${N(s.v)}</b></span>`).join('')}</div>
    ${comoLer ? `<p class="como-ler">${comoLer}</p>` : ''}</div>`;
}
function contraMargem(teto, rotulo) {
  const m = E.d.turno2.margem;
  return `<div class="viz"><h4>Isso poderia mudar o resultado?</h4>
    ${barras([{ rot: 'Diferença entre Lula e Flávio', v: m, cor: 'var(--lula)' }, { rot: rotulo, v: teto, cor: 'var(--ambar)' }], { fmt: N })}
    <p class="como-ler">A barra amarela é o <b>máximo</b> que este ponto poderia mudar, supondo o pior caso. Ela ${teto / m < .02 ? 'quase não aparece' : 'é bem menor'} perto da diferença de ${N(m)} votos.</p></div>`;
}
function vizSimples(id) {
  const d = E.d;
  switch (id) {
    case 'integridade':
      return numeros([[N(d.gerado.secoes), 'urnas conferidas'], [N(d.gerado.registros_bu), 'linhas de boletim comparadas'], ['0', 'diferenças encontradas']]);
    case 'logs':
      return numeros([['988 de 988', 'urnas suspeitas em que o diário bate com o boletim'], ['10.800', 'urnas sorteadas em cada turno, 400 por estado'], ['0', 'urnas com enxurrada de liberações no fim do dia']]);
    case 'biometria': {
      const [a, b] = d.biometria_modelos.filter(m => m.variavel === 'biom');
      return `<div class="viz"><h4>Vantagem do Lula nas seções com muita gente sem digital</h4>
        ${barras([{ rot: 'Sem considerar a idade', v: a.coef, cor: 'var(--ambar)' }, { rot: 'Comparando seções com a mesma idade', v: b.coef, cor: 'var(--verde)' }], { fmt: v => PP(v) })}
        <p class="como-ler">A barra de cima parece um sinal. Quando se compara seções com a mesma proporção de idosos (barra de baixo), ela praticamente desaparece.</p></div>`;
    }
    case 'klimek':
      return numeros([['65', 'seções com quase 100% num candidato'], ['18 de 21', 'que já existiam em 2022 já votavam assim'], ['92%', 'dos eleitores se identificaram pela digital']]);
    case 'escola':
      return numeros([['185', 'urnas destoam das vizinhas'], ['451.803', 'urnas comparadas'], ['125', 'delas são urnas novas, com eleitores mais jovens']]) + contraMargem(3460, 'Máximo que essas 185 urnas mudam');
    case 'viradas':
      return `<div class="viz"><h4>Quantas cidades trocaram de vencedor a cada eleição</h4>
        ${colunas(d.viradas_base.map(v => ({ rot: v.periodo, v: v.municipios, cor: v.periodo.endsWith('2026') ? 'var(--ambar)' : 'var(--cinza)' })), { fmt: N })}
        <p class="como-ler">Cada coluna é uma troca de eleição. Em 2026 (amarelo) foram 7 cidades, acima do costume. Em todas, as urnas mudaram juntas.</p></div>`;
    case 'crescimento':
      return numeros([['17', 'cidades com crescimento fora do padrão'], ['1', 'com o padrão de título de quem não mora lá (Anhangüera, GO)']]);
    case 'horarios':
      return numeros([['0', 'urnas abertas antes da hora'], ['0', 'urnas fechadas antes das 17h'], ['955', 'urnas abertas com mais de 30 min de atraso']]);
    case 'benford':
      return `<div class="viz"><h4>Em quantos testes apareceu desvio</h4>
        ${colunas([{ rot: 'Voto em papel<br><small>1994</small>', v: .13, cor: 'var(--cinza)' }, { rot: 'Urna eletrônica<br><small>2002–2026</small>', v: .12, cor: 'var(--ciano)' }], { fmt: v => P(v, 0) })}
        <p class="como-ler">As duas colunas têm quase a mesma altura: a urna eletrônica não mudou o padrão.</p></div>`;
    case 'segundo_turno': return vizSegundoTurno();
    case 'cadastro':
      return numeros([['718', 'cidades com mais eleitores que moradores'], ['324.638', 'eleitores além da população']]) + contraMargem(708713, 'Pior caso possível');
    case 'prorrogacao': {
      const pr = d.prorrogacao, a = pr['3220'], b = pr['3221'];
      return `<div class="viz"><h4>De cada 100 votos, quantos vieram depois das 17h</h4>
        ${colunas([{ rot: '1º turno<br><small>sem prorrogação</small>', v: a.apos17h / a.votos, cor: 'var(--cinza)' }, { rot: '2º turno<br><small>com prorrogação até 19h</small>', v: b.apos17h / b.votos, cor: 'var(--ambar)' }], { fmt: v => P(v, 2) })}
        <p class="como-ler">Se a prorrogação tivesse trazido uma enxurrada de votos, a coluna do 2º turno seria maior. Ela quase some.</p></div>` + contraMargem(39434, 'Máximo de votos depois das 17h');
    }
    default: return '';
  }
}
function vizSegundoTurno(link = true) {
  const mn = E.d.migracao.nacional;
  const faixas = E.d.migracao.faixas.filter(f => f.municipios >= 50);
  return pilha('1. De onde vieram os votos em jogo no 2º turno', [
    { rot: 'Eleitores dos 11 candidatos eliminados', v: mn.eliminados, cor: '#64748b' },
    { rot: 'Quem votou branco ou nulo no 1º turno', v: mn.bn1 - mn.bn2, cor: '#94a3b8' },
    { rot: 'Quem só foi votar no 2º turno', v: mn.comp2 - mn.comp1, cor: '#cbd5e1' },
  ], `Somando tudo, havia <b>${N(mn.ganho_lula + mn.ganho_flavio)}</b> votos que não eram nem do Lula nem do Flávio no 1º turno.`)
    + pilha('2. Para quem foram esses votos', [
      { rot: 'Lula', v: mn.ganho_lula, cor: 'var(--lula)' },
      { rot: 'Flávio', v: mn.ganho_flavio, cor: 'var(--flavio)' },
    ], 'O Lula ficou com a maior parte. A pergunta é: isso faz sentido com quem eram esses eleitores?')
    + `<div class="viz"><h4>3. Onde os votos soltos eram mais de direita, o Lula ganhou menos</h4>
      ${barras(faixas.map(f => ({ rot: `${f.direita_no_bolo} de direita <span class="texto-2">· ${N(f.municipios)} cidades</span>`, v: f.parcela_lula, cor: 'var(--lula)' })), { fmt: v => P(v, 0), max: 1 })}
      <p class="como-ler">Cada linha junta cidades parecidas. Exemplo da última linha: em ${N(faixas.at(-1).municipios)} cidades, mais de 80% dos votos soltos eram de candidatos de direita (Caiado, Renan, Zema), e mesmo assim o Lula ficou com ${P(faixas.at(-1).parcela_lula, 0)} deles. A barra vai encolhendo de cima para baixo: quanto mais direita, menos o Lula ganhou. É o que se espera de eleitores escolhendo; uma fraude tenderia a dar o mesmo ganho em todo lugar.</p></div>
      ${link ? `<p><a class="botao-contorno" style="text-decoration:none;display:inline-block;color:var(--texto)" href="#turnos">Ver a comparação completa entre os turnos →</a></p>` : ''}`;
}

function cartaoAnalise(p) {
  const s = SIMPLES[p.id] || { pergunta: p.titulo, resposta: p.achado, fraude: p.hipotese_fraude, normal: p.hipotese_inocente, vimos: p.achado };
  const [cl, ic, frase] = LADO[p.status] || LADO['fora do alcance'];
  return `
    <details class="cartao pista" id="p-${p.id}" data-classe="${STATUS[p.status]?.[0] || 'fora'}">
      <summary><span class="nivel">${esc(p.nivel || '')}</span><h3>${esc(s.pergunta)}</h3>${selo(p.status)}
        <span class="resposta r-${cl}"><b>Resposta curta:</b> ${esc(s.resposta)}</span>
        <span class="abrir">Ver como chegamos a isso</span></summary>
      <div class="pista-corpo">
        <ol class="passos">
          <li><span class="passo-n">1</span><div><b>Se fosse fraude, veríamos…</b><p>${esc(s.fraude)}</p></div></li>
          <li><span class="passo-n">2</span><div><b>Se fosse normal, veríamos…</b><p>${esc(s.normal)}</p></div></li>
          <li><span class="passo-n">3</span><div><b>O que os dados mostraram</b><p>${esc(s.vimos)}</p>
            <p class="conclui conclui-${cl}"><span aria-hidden="true">${ic}</span> ${frase}</p></div></li>
        </ol>
        <div class="viz-simples" data-viz="${p.id}"></div>
        ${s.conferimos ? `<div class="conferido"><b>✓ O que conferimos depois</b><p>${esc(s.conferimos)}</p></div>` : ''}
        <details class="tecnico"><summary>Detalhes técnicos e tabelas completas</summary>
          <div class="campo"><b>O teste</b>${esc(p.teste)}</div>
          <div class="campo"><b>Resultado, em termos técnicos</b>${esc(p.achado)}</div>
          ${p.impacto && p.impacto !== '—' ? `<div class="campo"><b>Tamanho máximo do efeito</b>${esc(p.impacto)}</div>` : ''}
          ${p.proximo ? `<div class="campo"><b>Próximo passo</b>${esc(p.proximo)}</div>` : ''}
          <div class="viz-tec" data-viz="${p.id}"></div>
        </details>
      </div>
    </details>`;
}

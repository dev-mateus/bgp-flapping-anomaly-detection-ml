# BGP Flapping Anomaly Detection ML

Projeto de Machine Learning para deteccao de anomalias de roteamento BGP
com foco em eventos raros, instabilidade de rotas e sinais de flapping
no plano de controle.

## Contexto

Este repositorio nasce como evolucao natural da trilha de estudos aplicada
em PCO213 (Aprendizado de Maquina / Mineracao de Dados), aproveitando:

1. Disciplina metodologica consolidada em pipeline completo.
2. Foco em problemas desbalanceados e metricas alem da acuracia.
3. Documentacao tecnica orientada a reprodutibilidade.

## Dataset Escolhido (fase inicial)

Fonte academica (SFU/IEEE DataPort) com registros BGP processados em CSV:

- 37 features extraidas de mensagens BGP UPDATE.
- Sinalizacoes de announcements, withdrawals, NLRI, AS-path,
  edit distance e demais estatisticas de roteamento.
- Rotulo binario por janela temporal: normal (-1) e anomalo (1).

Arquivos do dataset neste projeto:

- `dataset/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021.zip`
- `dataset/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021/`

Fonte oficial para reproducao (download original):

1. Pagina oficial do projeto (SFU):
   [SFU BGP Datasets](http://www.sfu.ca/~ljilja/cnl/projects/BGP_datasets/index.html)
2. Link direto do arquivo ZIP utilizado neste repositorio:
   [Download direto do ZIP](http://www.ensc.sfu.ca/~ljilja/cnl/projects/BGP_datasets/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021.zip)
3. Referencia complementar no IEEE DataPort (descricao e metadados):
   [IEEE DataPort - RIPE and BCNET](https://ieee-dataport.org/open-access/border-gateway-protocol-bgp-routing-records-reseaux-ip-europeens-ripe-and-bcnet)

## Objetivo Tecnico

Construir um pipeline reproducivel para:

1. Entender comportamento de instabilidade BGP em dados reais.
2. Detectar eventos anomalos com foco em recall e robustez para classe rara.
3. Comparar baselines e modelos mais fortes com validacao coerente.
4. Gerar analise interpretavel e acionavel para contexto de redes/telecom.

## Perguntas Norteadoras

1. Quais features de BGP melhor discriminam periodos anormais?
2. Quais modelos equilibram melhor deteccao de anomalias e falso positivo?
3. Qual limiar de decisao oferece melhor compromisso tecnico-operacional?
4. Qual estrategia generaliza melhor entre cenarios de anomalia distintos?

## Estrategia de Modelagem (resumo)

1. EDA orientada a eventos raros e distribuicao temporal.
2. Baseline simples (Dummy/Regressao Logistica) para referencia minima.
3. Modelos candidatos: arvore/ensemble e alternativas lineares.
4. Ajuste de threshold e metricas apropriadas para desbalanceamento.
5. Analise final com importancia de features e matriz de confusao.

## Metricas Prioritarias

- PR-AUC
- Recall da classe anomala
- Precision da classe anomala
- F1/F2 para sensibilidade a eventos raros
- MCC (quando aplicavel)

## Estrutura do Repositorio

- `dataset/`: dados brutos e dados preparados para modelagem.
- `resultados/`: tabelas, figuras, metricas e artefatos da analise.
- `README.md`: visao geral e direcao tecnica do projeto.
- `contexto.md`: guia operacional detalhado do projeto.

## Resultado Esperado

Ao final da fase inicial, o projeto deve entregar:

1. Pipeline executavel ponta a ponta.
2. Relatorio de desempenho com comparacao de modelos.
3. Recomendacoes tecnicas para deteccao de instabilidade BGP em ambiente de redes.

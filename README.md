# BGP Flapping Anomaly Detection ML

Projeto de Machine Learning para detecção de anomalias de roteamento BGP
com foco em eventos raros, instabilidade de rotas e sinais de flapping
no plano de controle.

## Contexto

Este repositório nasce como evolução natural da trilha de estudos aplicada
em PCO213 (Aprendizado de Máquina / Mineração de Dados), aproveitando:

1. Disciplina metodológica consolidada em pipeline completo.
2. Foco em problemas desbalanceados e métricas além da acurácia.
3. Documentação técnica orientada à reprodutibilidade.

## Dataset Escolhido (fase inicial)

Fonte acadêmica (SFU/IEEE DataPort) com registros BGP processados em CSV:

- 37 features extraídas de mensagens BGP UPDATE.
- Sinalizações de announcements, withdrawals, NLRI, AS-path,
  edit distance e demais estatísticas de roteamento.
- Rótulo binário por janela temporal: normal (-1) e anômalo (1).

Arquivos do dataset neste projeto:

- `dataset/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021.zip`
- `dataset/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021/`

Fonte oficial para reprodução (download original):

1. Página oficial do projeto (SFU):
   [SFU BGP Datasets](http://www.sfu.ca/~ljilja/cnl/projects/BGP_datasets/index.html)
2. Link direto do arquivo ZIP utilizado neste repositório:
   [Download direto do ZIP](http://www.ensc.sfu.ca/~ljilja/cnl/projects/BGP_datasets/BGP_RIPE_datasets_for_anomaly_detection_csv_revised_19022021.zip)
3. Referência complementar no IEEE DataPort (descrição e metadados):
   [IEEE DataPort - RIPE and BCNET](https://ieee-dataport.org/open-access/border-gateway-protocol-bgp-routing-records-reseaux-ip-europeens-ripe-and-bcnet)

## Objetivo Técnico

Construir um pipeline reproduzível para:

1. Entender comportamento de instabilidade BGP em dados reais.
2. Detectar eventos anômalos com foco em recall e robustez para classe rara.
3. Comparar baselines e modelos mais fortes com validação coerente.
4. Gerar análise interpretável e acionável para contexto de redes/telecom.

## Perguntas Norteadoras

1. Quais features de BGP melhor discriminam períodos anormais?
2. Quais modelos equilibram melhor detecção de anomalias e falso positivo?
3. Qual limiar de decisão oferece melhor compromisso técnico-operacional?
4. Qual estratégia generaliza melhor entre cenários de anomalia distintos?

## Estratégia de Modelagem (resumo)

1. EDA orientada a eventos raros e distribuição temporal.
2. Baseline simples (Dummy/Regressão Logística) para referência mínima.
3. Modelos candidatos: árvore/ensemble e alternativas lineares.
4. Ajuste de threshold e métricas apropriadas para desbalanceamento.
5. Análise final com importância de features e matriz de confusão.

## Métricas Prioritárias

- PR-AUC
- Recall da classe anômala
- Precision da classe anômala
- F1/F2 para sensibilidade a eventos raros
- MCC (quando aplicável)

## Estrutura do Repositório

- `dataset/`: dados brutos e dados preparados para modelagem.
- `resultados/`: tabelas, figuras, métricas e artefatos da análise.
- `README.md`: visão geral e direção técnica do projeto.
- `contexto.md`: guia operacional detalhado do projeto.

## Resultado Esperado

Ao final da fase inicial, o projeto deve entregar:

1. Pipeline executável ponta a ponta.
2. Relatório de desempenho com comparação de modelos.
3. Recomendações técnicas para detecção de instabilidade BGP em ambiente de redes.

## Execução Rápida

Executar o pipeline completo:

```bash
python pipeline_bgp_flapping.py
```

Saídas geradas em `resultados/`:

1. `metrics_modelos.csv`
2. `distribuicao_classes_por_arquivo.csv`
3. `resumo_execucao.json`

## Licença

Este projeto de código-fonte está licenciado sob a Apache License 2.0.

- Arquivo de licença: `LICENSE`
- Texto oficial: [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0)

## Licença dos Dados

Os datasets usados neste repositório são de fonte externa e seguem os termos
de uso da fonte original. A licença Apache 2.0 deste repositório aplica-se ao
código e aos artefatos autorais do projeto, não relicenciando automaticamente
os dados de terceiros.

Fontes oficiais dos dados utilizados nesta fase:

1. [SFU BGP Datasets](http://www.sfu.ca/~ljilja/cnl/projects/BGP_datasets/index.html)
2. [IEEE DataPort - RIPE and BCNET](https://ieee-dataport.org/open-access/border-gateway-protocol-bgp-routing-records-reseaux-ip-europeens-ripe-and-bcnet)

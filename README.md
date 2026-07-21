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

## Dataset e Estratégia de Dados

O projeto usa como base principal um dataset de flapping construído a partir de
dados brutos de BGP UPDATE.

Para manter a aderência à proposta original de flapping BGP, o repositório também
inclui um gerador de dataset a partir de BGP UPDATE bruto usando RIS, RouteViews
e CAIDA PyBGPStream.

Esse fluxo:

1. consulta registros UPDATE com granularidade temporal fina;
2. agrega por coletor, janela temporal e prefixo;
3. constrói features orientadas a churn e instabilidade de rota;
4. aplica uma rotulagem heurística inicial para janelas com sinais de flapping.

Documentação detalhada:

- [MONTAGEM_DATASET_FLAPPING.md](MONTAGEM_DATASET_FLAPPING.md)

## Objetivo Técnico

Construir um pipeline reproduzível para:

1. Entender comportamento de instabilidade BGP em dados reais.
2. Detectar sinais de flapping e outros eventos anômalos no plano de controle.
3. Comparar baselines e modelos mais fortes com validação coerente.
4. Gerar análise interpretável e acionável para contexto de redes/telecom.

## Perguntas Norteadoras

1. Quais features de BGP melhor discriminam janelas com sinais de flapping?
2. Quais modelos equilibram melhor detecção de instabilidade e falso positivo?
3. Qual limiar de decisão oferece melhor compromisso técnico-operacional?
4. Qual estratégia generaliza melhor entre cenários, coletores e períodos distintos?

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
- `build_bgp_flapping_dataset.py`: geração de dataset a partir de BGP UPDATE bruto.
- `pipeline_bgp_flapping.py`: treinamento e avaliação dos modelos sobre o dataset gerado.
- `MONTAGEM_DATASET_FLAPPING.md`: metodologia e instruções para montagem do dataset.
- `README.md`: visão geral e direção técnica do projeto.
- `contexto.md`: guia operacional detalhado do projeto.

## Resultado Esperado

Ao final da fase inicial, o projeto deve entregar:

1. Pipeline executável ponta a ponta.
2. Dataset reproduzível para estudo de flapping BGP a partir de dados brutos.
3. Relatório de desempenho com comparação de modelos.
4. Recomendações técnicas para detecção de instabilidade BGP em ambiente de redes.

## Execução Rápida

### 1. Montagem de dataset de flapping a partir de UPDATE bruto

Executar o gerador de dataset com uma coleta histórica controlada:

```bash
python build_bgp_flapping_dataset.py \
   --from-time "2024-01-01 00:00:00" \
   --until-time "2024-01-02 00:00:00" \
   --collectors route-views.sg \
   --projects routeviews \
   --window-minutes 5 \
   --top-prefixes-per-window 20 \
   --output-dir dataset/flapping_raw_windows_24h
```

Saídas geradas em `dataset/flapping_raw_windows_24h/`:

1. `bgp_flapping_windows.csv`
2. `metadata.json`

Observação: o rótulo `label_flapping` desse fluxo é heurístico e foi desenhado
como ponto de partida reproduzível para estudo acadêmico. Ele não substitui
ground truth operacional.

### 2. Treinamento do pipeline no dataset gerado

Executar o pipeline de ML usando o CSV gerado pelo coletor:

```bash
python pipeline_bgp_flapping.py \
   --dataset-path dataset/flapping_raw_windows_24h/bgp_flapping_windows.csv \
   --output-dir resultados_flapping_24h
```

Saídas geradas em `resultados_flapping_24h/`:

1. `metrics_modelos.csv`
2. `distribuicao_classes_por_coletor.csv`
3. `resumo_execucao.json`

### Parâmetros principais do coletor

- `--from-time`: início da coleta histórica em UTC.
- `--until-time`: fim da coleta histórica em UTC.
- `--collectors`: coletores a consultar, como `route-views.sg`.
- `--projects`: projeto de origem dos dados, como `routeviews`.
- `--window-minutes`: tamanho da janela de agregação temporal.
- `--top-prefixes-per-window`: número máximo de prefixos mantidos por janela, ordenados por churn.
- `--output-dir`: diretório de saída do dataset agregado.

### Parâmetros principais do pipeline

- `--dataset-path`: caminho para o arquivo `bgp_flapping_windows.csv`.
- `--output-dir`: diretório onde serão gravadas as métricas e o resumo de execução.

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
3. [RIPE RIS MRT](https://ris.ripe.net/docs/mrt/)
4. [RouteViews Archive](https://archive.routeviews.org/)

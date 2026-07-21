# Montagem de Dataset de Flapping BGP

Este projeto agora inclui um caminho reproduzivel para montar um dataset a partir de BGP UPDATE bruto com granularidade temporal.

## Fontes consultadas

1. RIPE RIS MRT: atualizacoes em arquivos update a cada 5 minutos.
2. RouteViews archive: arquivos MRT update historicos por coletor.
3. CAIDA PyBGPStream: interface Python para consultar RIS e RouteViews por intervalo temporal.

## Estrategia adotada

O script [build_bgp_flapping_dataset.py](build_bgp_flapping_dataset.py) consulta apenas registros BGP UPDATE e agrega por:

1. coletor;
2. janela temporal;
3. prefixo.

As features construidas sao orientadas a churn e instabilidade de rota:

1. total de updates;
2. announcements;
3. withdrawals;
4. transicoes A/W;
5. mudancas de AS-path;
6. quantidade de peers unicos;
7. quantidade de origin AS distintos;
8. estatisticas de inter-arrival time;
9. profundidade media de prepend.

O rotulo inicial `label_flapping` e heuristico. Uma janela e marcada como flapping quando combina:

1. churn alto;
2. alternancia de estado;
3. withdrawals relevantes;
4. instabilidade de caminho.

## Requisito

Instale PyBGPStream no ambiente Python antes da execucao. Em Windows, isso pode exigir dependencias nativas do libbgpstream.

## Exemplo de execucao

```bash
python build_bgp_flapping_dataset.py \
  --from-time "2024-01-01 00:00:00" \
  --until-time "2024-01-01 06:00:00" \
  --collectors rrc00 route-views.sg \
  --projects ris routeviews \
  --window-minutes 5 \
  --top-prefixes-per-window 50
```

## Saidas

O script grava em `dataset/flapping_raw_windows/`:

1. `bgp_flapping_windows.csv`: dataset tabular agregado.
2. `metadata.json`: configuracao da coleta e da regra de rotulagem.

## Observacoes metodologicas

1. Esse rotulo nao substitui ground truth operacional; ele cria um dataset inicial defensavel para estudo academico.
2. O ideal e complementar esse criterio com validacao manual de eventos conhecidos ou com listas de incidentes.
3. Para maior rigor, compare janelas positivas com prefixos beacons, incidentes RIS/RouteViews ou literatura sobre churn/flap damping.

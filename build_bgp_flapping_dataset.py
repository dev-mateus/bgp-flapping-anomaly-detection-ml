from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import DefaultDict, Dict, Iterable, Iterator, List, Tuple

import pandas as pd


@dataclass(frozen=True)
class UpdateRecord:
    timestamp: int
    collector: str
    peer_asn: str
    prefix: str
    event_type: str
    as_path: str
    communities: Tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Constroi dataset de flapping BGP a partir de dados brutos UPDATE "
            "via CAIDA PyBGPStream."
        )
    )
    parser.add_argument("--from-time", required=True, help="Inicio UTC, ex.: 2024-01-01 00:00:00")
    parser.add_argument("--until-time", required=True, help="Fim UTC, ex.: 2024-01-01 12:00:00")
    parser.add_argument(
        "--collectors",
        nargs="+",
        default=["rrc00"],
        help="Lista de coletores RIS/RouteViews, ex.: rrc00 route-views.sg",
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["ris", "routeviews"],
        help="Projetos do BGPStream a consultar. Use ris, routeviews ou ambos.",
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=5,
        help="Tamanho da janela temporal em minutos para agregacao.",
    )
    parser.add_argument(
        "--min-updates",
        type=int,
        default=8,
        help="Minimo de updates na janela para considerar flapping.",
    )
    parser.add_argument(
        "--min-transitions",
        type=int,
        default=3,
        help="Minimo de transicoes A/W na janela para considerar flapping.",
    )
    parser.add_argument(
        "--min-withdrawals",
        type=int,
        default=2,
        help="Minimo de withdrawals na janela para considerar flapping.",
    )
    parser.add_argument(
        "--min-path-changes",
        type=int,
        default=2,
        help="Minimo de mudancas de AS-path na janela para considerar flapping.",
    )
    parser.add_argument(
        "--top-prefixes-per-window",
        type=int,
        default=0,
        help=(
            "Se maior que zero, mantem apenas os N prefixos com maior churn por janela/collector. "
            "Use 0 para manter todos."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("dataset/raw_cache"),
        help="Diretorio local de cache para arquivos MRT baixados pelo broker do BGPStream.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dataset/flapping_raw_windows"),
        help="Diretorio de saida para o dataset agregado.",
    )
    return parser.parse_args()


def stream_updates(
    *,
    from_time: str,
    until_time: str,
    collectors: List[str],
    projects: List[str],
    cache_dir: Path,
) -> Iterator[UpdateRecord]:
    try:
        import pybgpstream
    except ImportError as exc:
        raise RuntimeError(
            "PyBGPStream nao esta instalado. Instale com 'pip install pybgpstream' "
            "e garanta as dependencias nativas do libbgpstream."
        ) from exc

    stream = pybgpstream.BGPStream(
        from_time=from_time,
        until_time=until_time,
        collectors=collectors,
        projects=projects,
        record_type="updates",
    )
    stream.set_data_interface_option("broker", "cache-dir", str(cache_dir.resolve()))

    for elem in stream:
        prefix = elem.fields.get("prefix")
        if not prefix:
            continue

        event_type = str(elem.type).upper()
        if event_type not in {"A", "W"}:
            continue

        as_path = elem.fields.get("as-path", "")
        communities = tuple(elem.fields.get("communities", []))
        collector = getattr(elem.record, "collector", "unknown") or "unknown"
        peer_asn = str(getattr(elem, "peer_asn", "unknown"))

        yield UpdateRecord(
            timestamp=int(float(elem.time)),
            collector=collector,
            peer_asn=peer_asn,
            prefix=prefix,
            event_type=event_type,
            as_path=as_path,
            communities=communities,
        )


def floor_timestamp(timestamp: int, window_seconds: int) -> int:
    return (timestamp // window_seconds) * window_seconds


def compute_state_transitions(events: List[str]) -> int:
    if len(events) < 2:
        return 0
    return sum(1 for prev, cur in zip(events, events[1:]) if prev != cur)


def compute_inter_arrival_stats(timestamps: List[int]) -> Tuple[float, float, float]:
    if len(timestamps) < 2:
        return 0.0, 0.0, 0.0
    deltas = [cur - prev for prev, cur in zip(timestamps, timestamps[1:])]
    return float(min(deltas)), float(mean(deltas)), float(max(deltas))


def label_window(
    row: Dict[str, float],
    *,
    min_updates: int,
    min_transitions: int,
    min_withdrawals: int,
    min_path_changes: int,
) -> int:
    high_churn = row["updates_total"] >= min_updates and row["state_transitions"] >= min_transitions
    unstable_state = row["withdrawals"] >= min_withdrawals or row["announcement_withdraw_ratio"] <= 1.5
    route_instability = row["as_path_changes"] >= min_path_changes or row["unique_origin_asns"] >= 2
    return int(high_churn and unstable_state and route_instability)


def aggregate_records(records: Iterable[UpdateRecord], args: argparse.Namespace) -> pd.DataFrame:
    window_seconds = args.window_minutes * 60
    grouped: DefaultDict[Tuple[str, int, str], List[UpdateRecord]] = defaultdict(list)

    for record in records:
        window_start = floor_timestamp(record.timestamp, window_seconds)
        grouped[(record.collector, window_start, record.prefix)].append(record)

    rows: List[Dict[str, float]] = []
    for (collector, window_start, prefix), bucket in grouped.items():
        bucket.sort(key=lambda item: item.timestamp)
        timestamps = [item.timestamp for item in bucket]
        event_types = [item.event_type for item in bucket]
        as_paths = [item.as_path for item in bucket if item.as_path]
        peers = [item.peer_asn for item in bucket]
        community_count = sum(len(item.communities) for item in bucket)

        counts = Counter(event_types)
        unique_paths = list(dict.fromkeys(as_paths))
        path_changes = max(len(unique_paths) - 1, 0)
        origin_asns = []
        prepended_lengths = []
        path_lengths = []
        duplicate_paths = 0

        last_path = None
        for path in as_paths:
            hops = [hop for hop in path.split(" ") if hop]
            if not hops:
                continue

            dedup_hops: List[str] = []
            for hop in hops:
                if not dedup_hops or dedup_hops[-1] != hop:
                    dedup_hops.append(hop)

            origin_asns.append(dedup_hops[-1])
            path_lengths.append(len(dedup_hops))
            prepended_lengths.append(max(len(hops) - len(dedup_hops), 0))
            if last_path is not None and last_path == path:
                duplicate_paths += 1
            last_path = path

        min_delta, mean_delta, max_delta = compute_inter_arrival_stats(timestamps)
        announcements = counts.get("A", 0)
        withdrawals = counts.get("W", 0)
        updates_total = len(bucket)

        row: Dict[str, float] = {
            "window_start": window_start,
            "collector": collector,
            "prefix": prefix,
            "updates_total": updates_total,
            "announcements": announcements,
            "withdrawals": withdrawals,
            "state_transitions": compute_state_transitions(event_types),
            "unique_peers": len(set(peers)),
            "unique_as_paths": len(set(as_paths)),
            "as_path_changes": path_changes,
            "unique_origin_asns": len(set(origin_asns)),
            "avg_as_path_len": float(mean(path_lengths)) if path_lengths else 0.0,
            "max_as_path_len": float(max(path_lengths)) if path_lengths else 0.0,
            "avg_prepend_depth": float(mean(prepended_lengths)) if prepended_lengths else 0.0,
            "duplicate_as_path_events": duplicate_paths,
            "communities_total": community_count,
            "min_inter_arrival_sec": min_delta,
            "mean_inter_arrival_sec": mean_delta,
            "max_inter_arrival_sec": max_delta,
            "announcement_withdraw_ratio": float(announcements / withdrawals) if withdrawals else float(announcements),
        }
        row["label_flapping"] = label_window(
            row,
            min_updates=args.min_updates,
            min_transitions=args.min_transitions,
            min_withdrawals=args.min_withdrawals,
            min_path_changes=args.min_path_changes,
        )
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if args.top_prefixes_per_window > 0:
        filtered_parts: List[pd.DataFrame] = []
        for (_, window_start), group in df.groupby(["collector", "window_start"], sort=True):
            keep = group.sort_values(
                ["updates_total", "state_transitions", "withdrawals"],
                ascending=[False, False, False],
            ).head(args.top_prefixes_per_window)
            filtered_parts.append(keep)
        df = pd.concat(filtered_parts, ignore_index=True)

    return df.sort_values(["window_start", "collector", "prefix"]).reset_index(drop=True)


def save_outputs(df: pd.DataFrame, args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = args.output_dir / "bgp_flapping_windows.csv"
    df.to_csv(output_csv, index=False)

    metadata = {
        "from_time": args.from_time,
        "until_time": args.until_time,
        "collectors": args.collectors,
        "projects": args.projects,
        "window_minutes": args.window_minutes,
        "label_rules": {
            "min_updates": args.min_updates,
            "min_transitions": args.min_transitions,
            "min_withdrawals": args.min_withdrawals,
            "min_path_changes": args.min_path_changes,
        },
        "rows": int(len(df)),
        "positive_rows": int(df["label_flapping"].sum()) if not df.empty else 0,
        "columns": list(df.columns),
    }

    with open(args.output_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    records = stream_updates(
        from_time=args.from_time,
        until_time=args.until_time,
        collectors=args.collectors,
        projects=args.projects,
        cache_dir=args.cache_dir,
    )
    df = aggregate_records(records, args)
    if df.empty:
        raise RuntimeError("Nenhum UPDATE valido foi encontrado para os filtros informados.")
    save_outputs(df, args)

    print("Dataset gerado em:", args.output_dir)
    print("- bgp_flapping_windows.csv")
    print("- metadata.json")
    print(f"Linhas: {len(df)} | Positivas: {int(df['label_flapping'].sum())}")


if __name__ == "__main__":
    main()
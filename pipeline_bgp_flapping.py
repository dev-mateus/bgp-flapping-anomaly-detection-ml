from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


REQUIRED_COLUMNS = {
    "window_start",
    "collector",
    "prefix",
    "updates_total",
    "announcements",
    "withdrawals",
    "state_transitions",
    "unique_peers",
    "unique_as_paths",
    "as_path_changes",
    "unique_origin_asns",
    "avg_as_path_len",
    "max_as_path_len",
    "avg_prepend_depth",
    "duplicate_as_path_events",
    "communities_total",
    "min_inter_arrival_sec",
    "mean_inter_arrival_sec",
    "max_inter_arrival_sec",
    "announcement_withdraw_ratio",
    "label_flapping",
}


def load_dataset(dataset_path: Path) -> pd.DataFrame:
    df = pd.read_csv(dataset_path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_cols = ", ".join(sorted(missing))
        raise RuntimeError(f"Dataset invalido. Colunas ausentes: {missing_cols}")

    df = df.copy()
    df["label_flapping"] = df["label_flapping"].astype(np.int8)
    df["window_start"] = df["window_start"].astype(np.int64)
    return df


def temporal_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_sorted = df.sort_values(["window_start", "collector", "prefix"]).reset_index(drop=True)
    n_rows = len(df_sorted)

    if n_rows < 10:
        raise RuntimeError("Dataset pequeno demais para split train/val/test temporal.")

    train_end = max(int(n_rows * 0.70), 1)
    val_end = max(int(n_rows * 0.80), train_end + 1)
    val_end = min(val_end, n_rows - 1)

    train_df = df_sorted.iloc[:train_end].copy()
    val_df = df_sorted.iloc[train_end:val_end].copy()
    test_df = df_sorted.iloc[val_end:].copy()

    if train_df.empty or val_df.empty or test_df.empty:
        raise RuntimeError("Falha ao gerar split temporal com particoes nao vazias.")

    split_labels = [
        train_df["label_flapping"],
        val_df["label_flapping"],
        test_df["label_flapping"],
    ]
    if any(labels.nunique() < 2 for labels in split_labels):
        return stratified_split(df_sorted)

    return train_df, val_df, test_df


def stratified_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = df["label_flapping"]
    if y.nunique() < 2 or y.value_counts().min() < 2:
        raise RuntimeError("Dataset sem diversidade minima de classes para treinamento supervisionado.")

    train_val, test = train_test_split(
        df,
        test_size=0.20,
        random_state=42,
        shuffle=True,
        stratify=y,
    )
    y_train_val = train_val["label_flapping"]
    train, val = train_test_split(
        train_val,
        test_size=0.125,
        random_state=42,
        shuffle=True,
        stratify=y_train_val,
    )
    return train.copy(), val.copy(), test.copy()


def select_feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {"window_start", "collector", "prefix", "label_flapping"}
    feature_cols = [col for col in df.columns if col not in excluded]
    if not feature_cols:
        raise RuntimeError("Nenhuma feature numerica foi encontrada no dataset.")
    return feature_cols


def find_best_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return 0.5

    thresholds = np.linspace(0.05, 0.95, 91)
    best_t = 0.5
    best_score = -1.0

    for t in thresholds:
        y_pred = (y_proba >= t).astype(np.int8)
        score = fbeta_score(y_true, y_pred, beta=2, zero_division=0)
        if score > best_score:
            best_score = score
            best_t = float(t)

    return best_t


def safe_roc_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    return float(roc_auc_score(y_true, y_score))


def evaluate_model(
    name: str,
    model: Pipeline | RandomForestClassifier,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_val: np.ndarray,
    y_val: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> Dict[str, float]:
    model.fit(x_train, y_train)

    val_proba = model.predict_proba(x_val)[:, 1]
    threshold = find_best_threshold(y_val, val_proba)

    test_proba = model.predict_proba(x_test)[:, 1]
    test_pred = (test_proba >= threshold).astype(np.int8)

    metrics = {
        "model": name,
        "threshold": threshold,
        "accuracy": float(accuracy_score(y_test, test_pred)),
        "precision": float(precision_score(y_test, test_pred, zero_division=0)),
        "recall": float(recall_score(y_test, test_pred, zero_division=0)),
        "f1": float(f1_score(y_test, test_pred, zero_division=0)),
        "f2": float(fbeta_score(y_test, test_pred, beta=2, zero_division=0)),
        "mcc": float(matthews_corrcoef(y_test, test_pred)),
        "pr_auc": float(average_precision_score(y_test, test_proba)),
        "roc_auc": safe_roc_auc(y_test, test_proba),
    }

    tn, fp, fn, tp = confusion_matrix(y_test, test_pred, labels=[0, 1]).ravel()
    metrics["tn"] = int(tn)
    metrics["fp"] = int(fp)
    metrics["fn"] = int(fn)
    metrics["tp"] = int(tp)

    return metrics


def save_outputs(
    out_dir: Path,
    metrics_rows: List[Dict[str, float]],
    split_info: Dict[str, int],
    collector_distribution: pd.DataFrame,
    feature_cols: List[str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df = metrics_df.sort_values("f2", ascending=False).reset_index(drop=True)
    metrics_df.to_csv(out_dir / "metrics_modelos.csv", index=False)

    collector_distribution.to_csv(out_dir / "distribuicao_classes_por_coletor.csv", index=False)

    with open(out_dir / "resumo_execucao.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "split_info": split_info,
                "feature_cols": feature_cols,
                "modelo_melhor_f2": metrics_df.iloc[0].to_dict() if len(metrics_df) else {},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de ML para deteccao de flapping BGP no dataset gerado pelo coletor."
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=Path("dataset/flapping_raw_windows/bgp_flapping_windows.csv"),
        help="Caminho para o CSV gerado pelo build_bgp_flapping_dataset.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("resultados"),
        help="Diretorio para salvar tabelas de resultados.",
    )
    args = parser.parse_args()

    if not args.dataset_path.exists():
        raise RuntimeError("O CSV do dataset informado nao foi encontrado.")

    df = load_dataset(args.dataset_path)

    dist = (
        df.groupby("collector")["label_flapping"]
        .agg(total="count", positivos="sum")
        .reset_index()
    )
    dist["taxa_positiva"] = dist["positivos"] / dist["total"]

    train_df, val_df, test_df = temporal_split(df)

    feature_cols = select_feature_columns(df)

    x_train = train_df[feature_cols].to_numpy(dtype=np.float32)
    y_train = train_df["label_flapping"].to_numpy(dtype=np.int8)
    x_val = val_df[feature_cols].to_numpy(dtype=np.float32)
    y_val = val_df["label_flapping"].to_numpy(dtype=np.int8)
    x_test = test_df[feature_cols].to_numpy(dtype=np.float32)
    y_test = test_df["label_flapping"].to_numpy(dtype=np.int8)

    models: Dict[str, Pipeline | RandomForestClassifier] = {
        "logreg_balanced": Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=42,
                    ),
                ),
            ]
        ),
        "random_forest_balanced": RandomForestClassifier(
            n_estimators=400,
            max_depth=None,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        ),
    }

    metrics_rows: List[Dict[str, float]] = []
    for model_name, model in models.items():
        metrics = evaluate_model(
            model_name,
            model,
            x_train,
            y_train,
            x_val,
            y_val,
            x_test,
            y_test,
        )
        metrics_rows.append(metrics)
        print(f"[{model_name}] f2={metrics['f2']:.4f} recall={metrics['recall']:.4f} pr_auc={metrics['pr_auc']:.4f}")

    split_info = {
        "total_linhas": int(len(df)),
        "train_linhas": int(len(train_df)),
        "val_linhas": int(len(val_df)),
        "test_linhas": int(len(test_df)),
        "train_positivos": int(y_train.sum()),
        "val_positivos": int(y_val.sum()),
        "test_positivos": int(y_test.sum()),
    }

    save_outputs(args.output_dir, metrics_rows, split_info, dist, feature_cols)

    print("\nResumo do split:")
    for k, v in split_info.items():
        print(f"- {k}: {v}")

    print("\nArquivos gerados em:", args.output_dir)
    print("- metrics_modelos.csv")
    print("- distribuicao_classes_por_coletor.csv")
    print("- resumo_execucao.json")


if __name__ == "__main__":
    main()

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


def discover_csv_files(dataset_root: Path) -> List[Path]:
    csv_files = [
        p
        for p in dataset_root.rglob("*.csv")
        if not p.name.startswith("._") and "__MACOSX" not in p.as_posix()
    ]
    return sorted(csv_files)


def build_column_names() -> List[str]:
    time_cols = ["hhmm", "hour", "minute", "second"]
    feature_cols = [f"f_{i:02d}" for i in range(1, 38)]
    return time_cols + feature_cols + ["label"]


def load_dataset(csv_files: List[Path]) -> pd.DataFrame:
    col_names = build_column_names()
    frames: List[pd.DataFrame] = []

    for file_path in csv_files:
        df = pd.read_csv(file_path, header=None)
        if df.shape[1] != 42:
            # Skip files that are not in expected schema.
            continue

        df.columns = col_names
        df["source_file"] = file_path.name
        df["row_in_file"] = np.arange(len(df), dtype=np.int32)
        frames.append(df)

    if not frames:
        raise RuntimeError("Nenhum CSV valido (42 colunas) foi encontrado no dataset.")

    all_data = pd.concat(frames, axis=0, ignore_index=True)
    all_data["label"] = (all_data["label"] == 1).astype(np.int8)
    return all_data


def temporal_split_by_file(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_parts: List[pd.DataFrame] = []
    val_parts: List[pd.DataFrame] = []
    test_parts: List[pd.DataFrame] = []

    for _, g in df.groupby("source_file", sort=True):
        g_sorted = g.sort_values(["row_in_file"]).reset_index(drop=True)
        y = g_sorted["label"]
        can_stratify = y.nunique() > 1 and y.value_counts().min() >= 2

        train_val, test = train_test_split(
            g_sorted,
            test_size=0.20,
            random_state=42,
            shuffle=True,
            stratify=y if can_stratify else None,
        )

        y_train_val = train_val["label"]
        can_stratify_tv = y_train_val.nunique() > 1 and y_train_val.value_counts().min() >= 2

        train, val = train_test_split(
            train_val,
            test_size=0.125,
            random_state=42,
            shuffle=True,
            stratify=y_train_val if can_stratify_tv else None,
        )

        train_parts.append(train.copy())
        val_parts.append(val.copy())
        test_parts.append(test.copy())

    train_df = pd.concat(train_parts, ignore_index=True)
    val_df = pd.concat(val_parts, ignore_index=True)
    test_df = pd.concat(test_parts, ignore_index=True)
    return train_df, val_df, test_df


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
    source_distribution: pd.DataFrame,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df = metrics_df.sort_values("f2", ascending=False).reset_index(drop=True)
    metrics_df.to_csv(out_dir / "metrics_modelos.csv", index=False)

    source_distribution.to_csv(out_dir / "distribuicao_classes_por_arquivo.csv", index=False)

    with open(out_dir / "resumo_execucao.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "split_info": split_info,
                "modelo_melhor_f2": metrics_df.iloc[0].to_dict() if len(metrics_df) else {},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline de ML para deteccao de anomalias BGP com foco em evento raro."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("dataset"),
        help="Diretorio raiz onde os CSVs estao localizados.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("resultados"),
        help="Diretorio para salvar tabelas de resultados.",
    )
    args = parser.parse_args()

    csv_files = discover_csv_files(args.dataset_root)
    if not csv_files:
        raise RuntimeError("Nenhum CSV encontrado no caminho informado.")

    df = load_dataset(csv_files)

    dist = (
        df.groupby("source_file")["label"]
        .agg(total="count", positivos="sum")
        .reset_index()
    )
    dist["taxa_positiva"] = dist["positivos"] / dist["total"]

    train_df, val_df, test_df = temporal_split_by_file(df)

    feature_cols = [f"f_{i:02d}" for i in range(1, 38)]

    x_train = train_df[feature_cols].to_numpy(dtype=np.float32)
    y_train = train_df["label"].to_numpy(dtype=np.int8)
    x_val = val_df[feature_cols].to_numpy(dtype=np.float32)
    y_val = val_df["label"].to_numpy(dtype=np.int8)
    x_test = test_df[feature_cols].to_numpy(dtype=np.float32)
    y_test = test_df["label"].to_numpy(dtype=np.int8)

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

    save_outputs(args.output_dir, metrics_rows, split_info, dist)

    print("\nResumo do split:")
    for k, v in split_info.items():
        print(f"- {k}: {v}")

    print("\nArquivos gerados em:", args.output_dir)
    print("- metrics_modelos.csv")
    print("- distribuicao_classes_por_arquivo.csv")
    print("- resumo_execucao.json")


if __name__ == "__main__":
    main()

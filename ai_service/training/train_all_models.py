r"""Train all inference models from the checked-in synthetic training datasets.

Run from the repository root with:
    ai_service\.venv-ai\Scripts\python.exe ai_service\training\train_all_models.py

The evaluation split holds out exact normalized titles to prevent duplicate
requests from appearing in both training and evaluation. Metrics still measure
synthetic-data performance, not accuracy on real company requests.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit

AI_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = AI_DIR / "training" / "data"
PARTITIONS_DIR = DATA_DIR / "partitions"
MODELS_DIR = AI_DIR / "models"
NLP_DATASET = DATA_DIR / "enterprise_requests_dataset_large.csv"
MASTER_DATASET = PARTITIONS_DIR / "master_requests_large.csv"

NLP_TARGETS = {
    "request_type": "nlp_request_type_model.pkl",
    "department": "nlp_department_model.pkl",
    "lifecycle_template": "nlp_template_model.pkl",
}

CATEGORICAL_COLUMNS = (
    "request_type",
    "department",
    "user_role",
    "priority_level",
)

RISK_FEATURES = [
    "request_type_enc",
    "department_enc",
    "user_role_enc",
    "priority_level_enc",
    "amount_log",
    "amount_millions",
    "budget_log",
    "amount_to_budget_ratio",
    "is_over_budget",
    "is_split_amount_suspect",
    "has_receipt",
    "num_attachments",
    "no_receipt_has_amount",
    "user_tenure_months",
    "past_requests_count",
    "past_rejection_rate",
    "high_rejection_rate",
    "is_off_hours",
    "is_template_matched",
]

RISK_INPUT_COLUMNS = [
    "title",
    *CATEGORICAL_COLUMNS,
    "amount_vnd",
    "budget_remaining_vnd",
    "has_receipt",
    "num_attachments",
    "user_tenure_months",
    "past_requests_count",
    "past_rejection_rate",
    "is_off_hours",
    "is_split_amount_suspect",
    "is_over_budget",
    "is_template_matched",
    "risk_score",
]

DOMAIN_DATASETS = {
    "finance": "finance_fraud_partition.csv",
    "hr": "hr_operations_partition.csv",
    "it": "it_security_partition.csv",
}

ARTIFACT_NAMES = [
    "nlp_vectorizer.pkl",
    *NLP_TARGETS.values(),
    "nlp_labels.json",
    "risk_model.pkl",
    "feature_columns.json",
    "encoders.json",
    "risk_model_finance.pkl",
    "feature_cols_finance.json",
    "risk_model_hr.pkl",
    "feature_cols_hr.json",
    "risk_model_it.pkl",
    "feature_cols_it.json",
    "domain_model_registry.json",
    "model_metadata.json",
]


def _normalize_group(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", str(value)).casefold().split())


def grouped_train_validation_test_indices(
    labels: np.ndarray,
    groups: np.ndarray,
    random_state: int = 42,
    additional_labels: tuple[np.ndarray, ...] = (),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create approximately 60/20/20 splits with no group crossing."""
    labels = np.asarray(labels)
    groups = np.asarray(groups)
    if len(labels) != len(groups) or len(labels) < 10:
        raise ValueError("Training data needs matching labels/groups and at least 10 rows.")
    preserved_targets = [labels, *(np.asarray(values) for values in additional_labels)]
    if any(len(values) != len(labels) for values in preserved_targets):
        raise ValueError("All target arrays must have the same number of rows.")
    if any(pd.isna(values).any() for values in preserved_targets) or pd.isna(groups).any():
        raise ValueError("Training labels and title groups cannot contain missing values.")

    all_label_sets = [set(values.tolist()) for values in preserved_targets]
    indices = np.arange(len(labels))
    best_split = None
    best_missing = sum(map(len, all_label_sets)) * 3

    for seed in range(random_state, random_state + 12):
        outer = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=seed)
        try:
            train_validation, test = next(outer.split(indices, labels, groups))
            inner = GroupShuffleSplit(
                n_splits=1, test_size=0.25, random_state=seed + 100
            )
            train_local, validation_local = next(
                inner.split(
                    train_validation,
                    labels[train_validation],
                    groups[train_validation],
                )
            )
        except ValueError:
            continue

        train = train_validation[train_local]
        validation = train_validation[validation_local]
        split = (train, validation, test)
        missing = sum(
            len(all_labels - set(values[part].tolist()))
            for part in split
            for values, all_labels in zip(preserved_targets, all_label_sets)
        )
        if missing < best_missing:
            best_split, best_missing = split, missing
        if missing == 0:
            break

    if best_split is None:
        raise ValueError("Could not construct a group-isolated data split.")

    train, validation, test = best_split
    group_sets = [np.unique(groups[part]) for part in best_split]
    if any(
        np.intersect1d(group_sets[left], group_sets[right]).size
        for left, right in ((0, 1), (0, 2), (1, 2))
    ):
        raise RuntimeError("Internal split error: a title group crossed data splits.")
    for values, all_labels in zip(preserved_targets, all_label_sets):
        if set(values[train].tolist()) != all_labels:
            raise ValueError("Some classes are absent from the training split.")

    return train, validation, test


def _load_csv(path: Path, required_columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    header = pd.read_csv(path, nrows=0).columns.tolist()
    missing = sorted(set(required_columns) - set(header))
    if missing:
        raise ValueError(f"{path.name} is missing required columns: {', '.join(missing)}")
    frame = pd.read_csv(path, usecols=required_columns, low_memory=False)
    if frame.empty:
        raise ValueError(f"Dataset is empty: {path}")
    return frame


def _classification_metrics(
    expected: np.ndarray,
    predicted: np.ndarray,
    labels: list[Any],
) -> dict[str, Any]:
    return {
        "accuracy": float(accuracy_score(expected, predicted)),
        "f1_macro": float(f1_score(expected, predicted, labels=labels, average="macro")),
        "f1_weighted": float(
            f1_score(expected, predicted, labels=labels, average="weighted")
        ),
        "classification_report": classification_report(
            expected,
            predicted,
            labels=labels,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(expected, predicted, labels=labels).tolist(),
    }


def _grouped_split_for_frame(
    frame: pd.DataFrame,
    target_column: str,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    groups = frame["title"].map(_normalize_group).to_numpy()
    return grouped_train_validation_test_indices(
        frame[target_column].to_numpy(),
        groups,
        random_state=random_state,
        additional_labels=tuple(
            frame[column].astype(str).to_numpy()
            for column in NLP_TARGETS
            if column != target_column
        ),
    )


def train_nlp_models(artifacts: Path, random_state: int) -> dict[str, Any]:
    required = ["title", "description", *NLP_TARGETS]
    frame = _load_csv(NLP_DATASET, required)
    frame["title"] = frame["title"].fillna("").astype(str).str.strip()
    frame["description"] = frame["description"].fillna("").astype(str).str.strip()
    frame = frame[
        frame["title"].ne("")
        & frame[list(NLP_TARGETS)].notna().all(axis=1)
    ].reset_index(drop=True)
    if frame.empty:
        raise ValueError("NLP dataset has no rows with text and complete labels.")

    text = (frame["title"] + " " + frame["description"]).to_numpy()
    train, validation, test = _grouped_split_for_frame(
        frame, "request_type", random_state
    )
    print(
        f"NLP rows: {len(frame):,} | train/validation/test: "
        f"{len(train):,}/{len(validation):,}/{len(test):,} "
        "| title groups isolated"
    )

    vectorizer = TfidfVectorizer(
        max_features=40000,
        min_df=2,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    x_train = vectorizer.fit_transform(text[train])
    x_validation = vectorizer.transform(text[validation])
    x_test = vectorizer.transform(text[test])
    print(f"NLP vocabulary: {x_train.shape[1]:,} terms")

    result: dict[str, Any] = {
        "dataset": str(NLP_DATASET.relative_to(AI_DIR)),
        "rows": len(frame),
        "split": {
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
            "group_key": "normalized title",
        },
        "tasks": {},
    }
    labels_metadata: dict[str, list[str]] = {}
    joblib.dump(vectorizer, artifacts / "nlp_vectorizer.pkl")

    for target, model_filename in NLP_TARGETS.items():
        labels = frame[target].astype(str).to_numpy()
        model = LogisticRegression(
            C=2.0,
            max_iter=1000,
            random_state=random_state,
        )
        model.fit(x_train, labels[train])
        predicted = model.predict(x_test)
        task_labels = sorted(set(labels.tolist()))
        metrics = _classification_metrics(labels[test], predicted, task_labels)
        metrics["validation_accuracy"] = float(
            accuracy_score(labels[validation], model.predict(x_validation))
        )
        result["tasks"][target] = metrics
        labels_metadata[target] = task_labels
        joblib.dump(model, artifacts / model_filename)
        print(
            f"  NLP {target}: test accuracy={metrics['accuracy']:.4f}, "
            f"macro-F1={metrics['f1_macro']:.4f}"
        )

    with (artifacts / "nlp_labels.json").open("w", encoding="utf-8") as file:
        json.dump(labels_metadata, file, ensure_ascii=False, indent=2)
    return result


def _category_encoders(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    encoders = {}
    for column in CATEGORICAL_COLUMNS:
        values = frame[column].astype("string").str.strip()
        if values.isna().any() or values.eq("").any():
            raise ValueError(f"Categorical column {column} contains missing values.")
        encoders[column] = {
            label: index for index, label in enumerate(sorted(values.unique().tolist()))
        }
    return encoders


def _engineer_risk_features(
    frame: pd.DataFrame,
    encoders: dict[str, dict[str, int]],
) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    for column in CATEGORICAL_COLUMNS:
        values = frame[column].astype("string").str.strip()
        encoded = values.map(encoders[column])
        if encoded.isna().any():
            unknown = sorted(values[encoded.isna()].dropna().unique().tolist())
            raise ValueError(f"Unknown values in {column}: {unknown[:10]}")
        result[f"{column}_enc"] = encoded.astype(np.float32)

    amount = pd.to_numeric(frame["amount_vnd"], errors="raise").astype(np.float64)
    budget = pd.to_numeric(
        frame["budget_remaining_vnd"], errors="raise"
    ).astype(np.float64)
    if amount.isna().any() or budget.isna().any() or (amount < 0).any() or (budget < 0).any():
        raise ValueError("Amounts and budgets must be present and non-negative.")

    result["amount_log"] = np.log1p(amount)
    result["amount_millions"] = amount / 1_000_000.0
    result["budget_log"] = np.log1p(budget)
    result["amount_to_budget_ratio"] = amount / (budget + 1.0)
    result["is_over_budget"] = (amount > budget).astype(np.int8)

    numeric_columns = [
        "is_split_amount_suspect",
        "has_receipt",
        "num_attachments",
        "user_tenure_months",
        "past_requests_count",
        "past_rejection_rate",
        "is_off_hours",
        "is_template_matched",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(frame[column], errors="raise")
    if result[numeric_columns].isna().any().any():
        raise ValueError("Risk features contain missing values.")

    result["no_receipt_has_amount"] = (
        (amount > 0) & (result["has_receipt"] == 0)
    ).astype(np.int8)
    result["high_rejection_rate"] = (
        result["past_rejection_rate"] > 0.25
    ).astype(np.int8)

    engineered = result[RISK_FEATURES].astype(np.float32)
    if not np.isfinite(engineered.to_numpy()).all():
        raise ValueError("Engineered risk features contain infinite or invalid values.")
    return engineered


def _train_xgboost(
    name: str,
    features: pd.DataFrame,
    risk_scores: np.ndarray,
    groups: np.ndarray,
    threads: int,
    random_state: int,
) -> tuple[xgb.XGBClassifier, dict[str, Any], dict[str, int]]:
    train, validation, test = grouped_train_validation_test_indices(
        risk_scores,
        groups,
        random_state=random_state,
    )
    class_values = sorted(set(risk_scores.tolist()))
    class_to_index = {value: index for index, value in enumerate(class_values)}
    y = np.array([class_to_index[value] for value in risk_scores], dtype=np.int32)
    x = features.to_numpy(dtype=np.float32, copy=False)

    model = xgb.XGBClassifier(
        n_estimators=400,
        max_depth=7,
        learning_rate=0.07,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_weight=3,
        reg_lambda=1.0,
        num_class=len(class_values),
        objective="multi:softprob",
        eval_metric="mlogloss",
        tree_method="hist",
        random_state=random_state,
        n_jobs=threads,
        early_stopping_rounds=30,
        verbosity=0,
    )
    print(
        f"{name}: fitting {len(train):,} rows, validating on {len(validation):,} "
        f"and testing on {len(test):,} (threads={threads})"
    )
    started = time.monotonic()
    model.fit(
        x[train],
        y[train],
        eval_set=[(x[validation], y[validation])],
        verbose=False,
    )
    predicted_indices = np.asarray(model.predict(x[test]), dtype=np.int32)
    predicted = np.array([class_values[index] for index in predicted_indices])
    expected = risk_scores[test]
    metrics = _classification_metrics(expected, predicted, class_values)
    metrics.update(
        {
            "validation_accuracy": float(
                accuracy_score(
                    risk_scores[validation],
                    [
                        class_values[index]
                        for index in np.asarray(model.predict(x[validation]), dtype=np.int32)
                    ],
                )
            ),
            "best_iteration": int(model.best_iteration),
            "training_seconds": round(time.monotonic() - started, 2),
            "split": {
                "train": len(train),
                "validation": len(validation),
                "test": len(test),
                "group_key": "normalized title",
            },
            "risk_classes": class_values,
            "top_features": sorted(
                zip(RISK_FEATURES, model.feature_importances_.tolist()),
                key=lambda item: item[1],
                reverse=True,
            )[:10],
        }
    )
    print(
        f"  {name}: test accuracy={metrics['accuracy']:.4f}, "
        f"macro-F1={metrics['f1_macro']:.4f}, "
        f"weighted-F1={metrics['f1_weighted']:.4f}, "
        f"best_iteration={model.best_iteration}"
    )
    return model, metrics, class_to_index


def train_risk_models(
    artifacts: Path,
    threads: int,
    random_state: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    master = _load_csv(MASTER_DATASET, RISK_INPUT_COLUMNS)
    encoders = _category_encoders(master)
    master_features = _engineer_risk_features(master, encoders)
    master_labels = pd.to_numeric(master["risk_score"], errors="raise").to_numpy()
    if not np.isfinite(master_labels).all() or not np.equal(
        master_labels, np.floor(master_labels)
    ).all():
        raise ValueError("risk_score labels must be complete integers.")
    master_labels = master_labels.astype(np.int32)
    if set(master_labels.tolist()) != {1, 2, 3, 4, 5}:
        raise ValueError("Master risk_score must contain every class from 1 to 5.")
    master_groups = master["title"].map(_normalize_group).to_numpy()
    if np.any(master_groups == ""):
        raise ValueError("Risk dataset contains blank titles; cannot isolate groups.")

    master_model, master_metrics, _ = _train_xgboost(
        "Master risk model",
        master_features,
        master_labels,
        master_groups,
        threads,
        random_state,
    )
    joblib.dump(master_model, artifacts / "risk_model.pkl")
    with (artifacts / "feature_columns.json").open("w", encoding="utf-8") as file:
        json.dump(RISK_FEATURES, file, ensure_ascii=False, indent=2)
    with (artifacts / "encoders.json").open("w", encoding="utf-8") as file:
        json.dump(encoders, file, ensure_ascii=False, indent=2)

    results: dict[str, Any] = {
        "master": {
            "dataset": str(MASTER_DATASET.relative_to(AI_DIR)),
            "rows": len(master),
            **master_metrics,
        }
    }
    del master_features, master_model, master_labels, master_groups, master

    registry = {}
    for domain, filename in DOMAIN_DATASETS.items():
        path = PARTITIONS_DIR / filename
        frame = _load_csv(path, RISK_INPUT_COLUMNS)
        features = _engineer_risk_features(frame, encoders)
        labels = pd.to_numeric(frame["risk_score"], errors="raise").to_numpy()
        if not np.isfinite(labels).all() or not np.equal(labels, np.floor(labels)).all():
            raise ValueError(f"{filename}: risk_score labels must be complete integers.")
        labels = labels.astype(np.int32)
        if not set(labels.tolist()).issubset({1, 2, 3, 4, 5}):
            raise ValueError(f"{filename}: risk_score labels must be in the range 1..5.")
        groups = frame["title"].map(_normalize_group).to_numpy()
        if np.any(groups == ""):
            raise ValueError(f"{filename}: dataset contains blank titles.")

        model, metrics, class_to_index = _train_xgboost(
            f"{domain.title()} risk model",
            features,
            labels,
            groups,
            threads,
            random_state,
        )
        model_filename = f"risk_model_{domain}.pkl"
        features_filename = f"feature_cols_{domain}.json"
        joblib.dump(model, artifacts / model_filename)
        reverse_remap = {
            str(index): int(label)
            for label, index in class_to_index.items()
        }
        feature_metadata = {
            "feature_cols": RISK_FEATURES,
            "label_remap": {
                str(label): int(index)
                for label, index in class_to_index.items()
            },
            "reverse_remap": reverse_remap,
        }
        with (artifacts / features_filename).open("w", encoding="utf-8") as file:
            json.dump(feature_metadata, file, ensure_ascii=False, indent=2)

        registry[domain] = {
            "model_file": model_filename,
            "features_file": features_filename,
            "accuracy": round(metrics["accuracy"], 4),
            "f1_weighted": round(metrics["f1_weighted"], 4),
            "f1_macro": round(metrics["f1_macro"], 4),
            "rows": len(frame),
        }
        results[domain] = {
            "dataset": str(path.relative_to(AI_DIR)),
            "rows": len(frame),
            **metrics,
        }
        del frame, features, labels, groups, model

    with (artifacts / "domain_model_registry.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(registry, file, ensure_ascii=False, indent=2)
    return results, encoders


def _commit_artifacts(staging_dir: Path) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".training-backup-", dir=MODELS_DIR
    ) as backup_name:
        backup_dir = Path(backup_name)
        existing = {
            name: MODELS_DIR / name
            for name in ARTIFACT_NAMES
            if (MODELS_DIR / name).is_file()
        }
        for name, path in existing.items():
            shutil.copy2(path, backup_dir / name)

        replaced: list[str] = []
        try:
            for name in ARTIFACT_NAMES:
                source = staging_dir / name
                if not source.is_file():
                    raise FileNotFoundError(f"Training output is missing {name}.")
                os.replace(source, MODELS_DIR / name)
                replaced.append(name)
        except Exception:
            for name in reversed(replaced):
                destination = MODELS_DIR / name
                backup = backup_dir / name
                if backup.is_file():
                    os.replace(backup, destination)
                elif destination.exists():
                    destination.unlink()
            raise


def run_pipeline(threads: int, random_state: int) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    start = time.monotonic()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".training-staging-", dir=MODELS_DIR
    ) as staging_name:
        staging = Path(staging_name)
        print("Phase 1/2: train NLP request type, department, and lifecycle models")
        nlp_metrics = train_nlp_models(staging, random_state)
        print("\nPhase 2/2: train master and finance/HR/IT risk models in sequence")
        risk_metrics, _ = train_risk_models(staging, threads, random_state)

        metadata = {
            "pipeline_version": "grouped-holdout-v1",
            "trained_at": started_at.isoformat(),
            "training_duration_seconds": round(time.monotonic() - start, 2),
            "status": "READY_FOR_INFERENCE",
            "evaluation_scope": (
                "Synthetic datasets with exact normalized titles held out across "
                "train/validation/test. These metrics do not estimate accuracy on "
                "real company requests."
            ),
            "random_state": random_state,
            "xgboost_threads": threads,
            "nlp_metrics": nlp_metrics,
            "risk_metrics": risk_metrics,
        }
        with (staging / "model_metadata.json").open("w", encoding="utf-8") as file:
            json.dump(metadata, file, ensure_ascii=False, indent=2)

        _commit_artifacts(staging)

    print(
        "\nTraining complete. Model artifacts were updated only after all "
        "seven risk/NLP tasks finished."
    )
    return metadata


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train every AI model with title-group-isolated evaluation."
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=max(1, min(4, os.cpu_count() or 1)),
        help="Maximum XGBoost threads per model (default: up to 4).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic split and training seed.",
    )
    args = parser.parse_args(argv)
    if args.threads < 1:
        parser.error("--threads must be at least 1")
    if args.seed < 0:
        parser.error("--seed must be non-negative")

    for path in [NLP_DATASET, MASTER_DATASET]:
        if not path.is_file():
            raise FileNotFoundError(f"Required training data is missing: {path}")
    for filename in DOMAIN_DATASETS.values():
        path = PARTITIONS_DIR / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required training data is missing: {path}")

    metadata = run_pipeline(args.threads, args.seed)
    print(f"Metadata: {MODELS_DIR / 'model_metadata.json'}")
    print(
        "Synthetic held-out test accuracy — "
        f"NLP request type: {metadata['nlp_metrics']['tasks']['request_type']['accuracy']:.4f}; "
        f"master risk: {metadata['risk_metrics']['master']['accuracy']:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

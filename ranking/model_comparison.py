"""
랭킹 모델 비교 골격 (4순위: LightGBM 등 경량 랭킹 모델 학습 및 평가)

rule-only(pseudo-label 수식 그대로) → 선형회귀 → RandomForest → LightGBM → XGBoost → CatBoost 순으로
비교해, "단순 규칙에서 트리 기반 비선형 모델로 갈수록 얼마나 개선되는지"를 확인하는 게 목적이다.

[중요 - 방법론 주의사항]
pseudo-label은 rule-only 수식(compute_pseudo_label) 자체로 만든 값이라, rule-only는 정의상 이 값을
"완벽하게" 재현한다 (자기 자신이므로). 따라서 "MAE가 가장 낮은 모델 = 가장 좋은 모델"이라는 식으로
rule-only와 학습 모델을 직접 비교하면 rule-only가 항상 이기는 게 당연해서 비교가 무의미해진다.
대신 이 모듈은:
    1. train/test로 데이터를 나누고, 학습 모델은 train만 보고 test의 pseudo-label을 얼마나 잘 "예측"하는지 측정
       (rule-only는 train/test 구분과 무관하게 어차피 완벽하므로, 이 지표에서는 항상 만점에 가까움 - 이건 정상이며
        "심사 자료"에서는 이 사실 자체를 설명해야 함 - 즉 이 지표는 학습 모델들끼리의 상대 비교에만 의미가 있음)
    2. 값(MAE/RMSE)뿐 아니라 순위 상관관계(Spearman)도 함께 본다 - 실제 서비스에서 중요한 건 정확한 점수值가 아니라
       "순위가 맞는지"이기 때문
    3. 대회 데이터가 실제로 없는 상태이므로, 최종 판단은 수치 하나가 아니라 팀 정성 검토(상위 K개 추천이
       실제로 납득되는지)와 함께 이뤄져야 한다 (4장 4.4절 "rule-only 버전과 학습 모델 버전을 비교하는
       정성 평가표" 요구사항과 일치).

지금은 mock 데이터 8쌍뿐이라 어떤 모델도 의미 있게 학습되지 않는다. 이 모듈은 파이프라인이 끝까지
동작하는지 검증하는 용도이고, 실 데이터 확보 후 다시 실행해서 실제 비교를 진행해야 한다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

import numpy as np

FEATURE_COLUMNS = [
    "rlte_rank_norm",
    "category_match",
    "embedding_similarity",
    "cnctr_rate_gap",
    "travel_time_minutes",
]


@dataclass
class ModelEvalResult:
    model_name: str
    mae: float
    rmse: float
    spearman_corr: float  # 예측 순위와 실제 pseudo-label 순위 간 상관계수 (1에 가까울수록 좋음)
    n_test: int


def load_dataset_from_json(path: str, exclude_ambiguous: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """
    ranking/dataset_builder.py 또는 ranking/build_real_dataset.py / build_multi_spot_dataset.py가
    저장한 JSON을 읽어 (X, y) = (feature 행렬, pseudo_label 벡터)로 변환한다.

    Args:
        exclude_ambiguous: True면 is_region_ambiguous=true인 행(KorService2 검색이 여러 건이라
            지역 매칭이 불확실했던 후보, live_api_client.py 참고)을 제외한다. mock 데이터나
            이 필드가 없는 파일에서는 아무 영향 없다.
    """
    import json

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if exclude_ambiguous:
        before = len(data)
        data = [row for row in data if not row.get("is_region_ambiguous", False)]
        print(f"[안내] is_region_ambiguous 제외: {before}건 -> {len(data)}건")

    X = np.array([[row["features"][col] for col in FEATURE_COLUMNS] for row in data])
    y = np.array([row["pseudo_label"] for row in data])
    return X, y


def _make_rule_only_predictor() -> Callable[[np.ndarray], np.ndarray]:
    """
    rule-only 모델: 학습하지 않고 ranking/features.py의 PSEUDO_LABEL_WEIGHTS 수식을 그대로 재적용한다.
    비교 목적상 "모델"과 동일한 인터페이스(predict(X))를 갖도록 감싼다.
    주의: 위 방법론 주의사항 참고 - 이 예측값은 pseudo_label 자체와 사실상 동일하다.
    """
    from ranking.features import PSEUDO_LABEL_WEIGHTS

    def predict(X: np.ndarray) -> np.ndarray:
        rank_norm, cat_match, emb_sim, cnctr_gap, travel_time = X.T
        normalized_gap = cnctr_gap / 100.0
        proximity = 1.0 / (1.0 + travel_time / 10.0)
        return (
            PSEUDO_LABEL_WEIGHTS["rlte_rank_norm"] * rank_norm
            + PSEUDO_LABEL_WEIGHTS["category_match"] * cat_match
            + PSEUDO_LABEL_WEIGHTS["embedding_similarity"] * emb_sim
            + PSEUDO_LABEL_WEIGHTS["cnctr_rate_gap"] * normalized_gap
            + abs(PSEUDO_LABEL_WEIGHTS["travel_time_minutes"]) * proximity
        )

    return predict


def get_model_registry() -> dict[str, Any]:
    """
    비교할 모델들을 이름 -> (fit 가능한 객체 또는 rule-only predictor) 형태로 등록한다.
    실제 학습이 필요한 모델은 sklearn 스타일 .fit(X, y) / .predict(X) 인터페이스를 따른다.
    설치되지 않은 라이브러리(xgboost, catboost 등)는 건너뛰고 경고만 출력한다 (requirements.txt 설치 필요).
    """
    registry: dict[str, Any] = {"rule_only": _make_rule_only_predictor()}

    try:
        from sklearn.linear_model import Ridge

        registry["ridge_regression"] = Ridge(alpha=1.0)
    except ImportError:
        print("[경고] scikit-learn 미설치 - ridge_regression, random_forest 건너뜀")

    try:
        from sklearn.ensemble import RandomForestRegressor

        registry["random_forest"] = RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42)
    except ImportError:
        pass

    try:
        from lightgbm import LGBMRegressor

        # 데이터가 매우 작을 때(mock 8쌍) LightGBM 기본 파라미터는 과적합/에러가 나기 쉬워
        # min_child_samples, num_leaves를 작게 조정. 실 데이터 확보 후에는 기본값으로 되돌려 튜닝할 것.
        registry["lightgbm"] = LGBMRegressor(
            n_estimators=50, num_leaves=4, min_child_samples=1, verbose=-1, random_state=42
        )
    except ImportError:
        print("[경고] lightgbm 미설치 - pip install lightgbm 필요")

    try:
        from xgboost import XGBRegressor

        registry["xgboost"] = XGBRegressor(n_estimators=50, max_depth=3, random_state=42, verbosity=0)
    except ImportError:
        print("[경고] xgboost 미설치 - pip install xgboost 필요")

    try:
        from catboost import CatBoostRegressor

        registry["catboost"] = CatBoostRegressor(iterations=50, depth=3, random_state=42, verbose=False)
    except ImportError:
        print("[경고] catboost 미설치 - pip install catboost 필요")

    return registry


def evaluate_model(name: str, model: Any, X: np.ndarray, y: np.ndarray) -> ModelEvalResult:
    """
    Leave-One-Out 교차검증으로 모델을 평가한다.
    데이터가 아주 작을 때(현재 mock 8쌍)는 일반적인 train/test 분할보다 LOO가 더 안정적인 추정을 준다.
    실 데이터가 충분히 쌓이면(수백 건 이상) k-fold 또는 단순 train/test 분할로 바꿀 것.
    """
    n = len(y)
    predictions = np.zeros(n)

    for i in range(n):
        train_idx = [j for j in range(n) if j != i]
        X_train, y_train = X[train_idx], y[train_idx]
        X_test = X[i : i + 1]

        if callable(model) and not hasattr(model, "fit"):
            # rule_only처럼 학습이 필요 없는 순수 함수 predictor
            predictions[i] = model(X_test)[0]
        else:
            model.fit(X_train, y_train)
            predictions[i] = model.predict(X_test)[0]

    mae = float(np.mean(np.abs(predictions - y)))
    rmse = float(np.sqrt(np.mean((predictions - y) ** 2)))

    from scipy.stats import spearmanr

    spearman_corr, _ = spearmanr(predictions, y)

    return ModelEvalResult(
        model_name=name, mae=round(mae, 4), rmse=round(rmse, 4),
        spearman_corr=round(float(spearman_corr), 4), n_test=n,
    )


def compare_models(dataset_path: str, exclude_ambiguous: bool = False) -> list[ModelEvalResult]:
    """등록된 모든 모델을 Leave-One-Out으로 평가하고 결과를 반환한다 (MAE 오름차순 정렬)."""
    X, y = load_dataset_from_json(dataset_path, exclude_ambiguous=exclude_ambiguous)
    registry = get_model_registry()

    results = []
    for name, model in registry.items():
        try:
            results.append(evaluate_model(name, model, X, y))
        except Exception as e:  # noqa: BLE001 - 한 모델 실패가 나머지 비교를 막지 않도록
            print(f"[{name}] 평가 실패: {e}")

    results.sort(key=lambda r: r.mae)
    return results


def _print_comparison_table(results: list[ModelEvalResult]) -> None:
    print(f"{'모델':<18}{'MAE':<10}{'RMSE':<10}{'Spearman':<10}{'n':<5}")
    for r in results:
        print(f"{r.model_name:<18}{r.mae:<10}{r.rmse:<10}{r.spearman_corr:<10}{r.n_test:<5}")


if __name__ == "__main__":
    # 실행: python -m ranking.model_comparison  (ai/ 폴더 안에서)
    # 실 데이터가 있으면 그걸 쓰고, 없으면 mock 데이터로 폴백한다.
    import os

    dataset_path = "data/processed/training_pairs_real_multi.json"
    if not os.path.exists(dataset_path):
        dataset_path = "data/processed/training_pairs_real.json"
    if not os.path.exists(dataset_path):
        dataset_path = "data/processed/training_pairs_mock.json"
        print("[주의] mock 데이터로는 어떤 모델도 의미 있게 학습되지 않습니다. 파이프라인 검증용입니다.\n")

    print(f"데이터셋: {dataset_path}\n")

    print("=== 전체 데이터 (지역 매칭 애매 포함) ===")
    results_all = compare_models(dataset_path, exclude_ambiguous=False)
    _print_comparison_table(results_all)

    print("\n=== 지역 매칭 애매 제외 ===")
    results_filtered = compare_models(dataset_path, exclude_ambiguous=True)
    _print_comparison_table(results_filtered)

    print(
        "\nrule_only는 정의상 낮은 오차가 나오는 게 정상입니다 (pseudo_label 자체가 이 수식으로 만들어졌으므로).\n"
        "학습 모델들끼리의 상대 비교, 그리고 Spearman(순위 상관관계)을 함께 보고 판단할 것.\n"
        "전체 vs 애매 제외 두 결과가 크게 다르면, 지역 매칭 정확도를 먼저 높이는 게 우선순위일 수 있습니다.\n"
        "rule-only vs 학습 모델 비교는 수치뿐 아니라 팀 정성 검토(상위 K개 추천이 납득되는지)를 함께 진행할 것."
    )

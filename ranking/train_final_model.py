"""
최종 랭킹 모델 학습 (5순위 준비)

model_comparison.py에서 확인한 결과를 바탕으로, 프로덕션에 쓸 모델 1개를 확정 학습하고 저장한다.
기본값은 LightGBM (원래 설계 근거: 가볍고 빠름, Railway/Render 배포 환경에 유리, lambdarank objective 지원 -
model_comparison.py 실험에서 pseudo-label이 선형식이라 트리 모델의 비선형 이득이 증명되진 않았지만,
그 근거 자체는 여전히 유효하므로 유지함).

[주의] 데이터가 90건뿐이라 held-out 검증 없이 전체 데이터로 학습한다 (과적합 위험 있음, 데이터가
더 쌓이면 train/valid 분할로 바꿀 것). exclude_ambiguous=True를 기본값으로 써서, 지역 매칭이
불확실한 24건은 프로덕션 모델 학습에서 제외한다 (실험 결과 극단적으로 나쁘진 않았지만, 실 서비스에
내보내는 모델은 보수적으로 가는 게 안전하다는 판단).
"""

from __future__ import annotations

import os

import joblib

from ranking.model_comparison import FEATURE_COLUMNS, load_dataset_from_json

MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "ranking_model.joblib")


def train_and_save_final_model(
    dataset_path: str, model_type: str = "lightgbm", exclude_ambiguous: bool = True
) -> str:
    """
    dataset_path의 전체 데이터로 최종 모델을 학습하고 MODEL_PATH에 저장한다.

    Returns:
        저장된 모델 파일 경로
    """
    X, y = load_dataset_from_json(dataset_path, exclude_ambiguous=exclude_ambiguous)

    if len(y) < 30:
        print(f"[주의] 학습 데이터가 {len(y)}건뿐입니다. 프로덕션에 쓰기엔 적고, 데이터가 더 쌓이면 재학습할 것.")

    if model_type == "lightgbm":
        from lightgbm import LGBMRegressor

        model = LGBMRegressor(n_estimators=50, num_leaves=8, min_child_samples=3, verbose=-1, random_state=42)
    elif model_type == "catboost":
        from catboost import CatBoostRegressor

        model = CatBoostRegressor(iterations=50, depth=3, random_state=42, verbose=False)
    else:
        raise ValueError(f"지원하지 않는 model_type: {model_type}")

    model.fit(X, y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump({"model": model, "feature_columns": FEATURE_COLUMNS, "model_type": model_type}, MODEL_PATH)
    print(f"모델 저장 완료: {MODEL_PATH} (model_type={model_type}, n_train={len(y)})")
    return MODEL_PATH


if __name__ == "__main__":
    # 실행: python -m ranking.train_final_model  (ai/ 폴더 안에서)
    dataset_path = "data/processed/training_pairs_real_multi.json"
    if not os.path.exists(dataset_path):
        dataset_path = "data/processed/training_pairs_real.json"
    if not os.path.exists(dataset_path):
        raise SystemExit(
            "실 데이터가 없습니다. 먼저 python -m ranking.build_multi_spot_dataset 등을 실행해 데이터를 모을 것."
        )

    train_and_save_final_model(dataset_path, model_type="lightgbm", exclude_ambiguous=True)

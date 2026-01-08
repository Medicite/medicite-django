import os
import pandas as pd

# === Paths ===
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ML_MODELS_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'ml_models'))

CSV_PATH = os.path.join(ML_MODELS_DIR, 'disease_dataset_hybrid_augmented.csv')
MODEL_PATH = os.path.join(ML_MODELS_DIR, 'new_model_main.json')
ENCODER_PATH = os.path.join(ML_MODELS_DIR, 'disease_encoder_main.pkl')
FEATURE_ORDER_PATH = os.path.join(ML_MODELS_DIR, 'feature_order_main.pkl')

# === CSV Columns ===
try:
    df = pd.read_csv(CSV_PATH)
    ALL_COLUMNS = df.columns.tolist()
except FileNotFoundError:
    print(f"⚠️ Warning: CSV not found at {CSV_PATH}")
    ALL_COLUMNS = []

# Age + Sex column rules
AGE_COLUMNS = ['age_adolescent', 'age_adult', 'age_all', 'age_child', 'age_elderly']
SEX_COLUMN = 'sex'

# Filter out the "disease" column (label)
SYMPTOM_COLUMNS = [col for col in ALL_COLUMNS if col not in (['disease'] + AGE_COLUMNS + [SEX_COLUMN])]

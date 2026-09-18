
from .team_data_pipeline import get_training_data
from .pitcher_pipeline import get_full_training_data
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import accuracy_score, roc_auc_score
import numpy as np
import joblib

import os



final_df = get_training_data()
final_df_with_pitchers = get_full_training_data(final_df)

feature_cols = [c for c in final_df_with_pitchers.columns if
                'season' in c or 'last10' in c or 'bullpen_ip_last3' in c]


final_df_with_pitchers = final_df_with_pitchers.dropna(subset=feature_cols)
final_df_with_pitchers = final_df_with_pitchers.sort_values('date').reset_index(drop=True)

split_idx = int(len(final_df_with_pitchers) * 0.8)
split_date = final_df_with_pitchers.iloc[:split_idx]['date'].max()

train = final_df_with_pitchers[final_df_with_pitchers['date'] <= split_date]
test = final_df_with_pitchers[final_df_with_pitchers['date'] > split_date]

X_train, y_train = train[feature_cols], train['home_win']
X_test, y_test = test[feature_cols], test['home_win']

#BEST MODEL
model_cv = LogisticRegressionCV(
    Cs=np.logspace(-3, 2, 20),
    cv=8,
    l1_ratios=(0.0,),        # 0.0 = pure L2 regularization, replaces penalty='l2'
    scoring='roc_auc',
    max_iter=2000,
    random_state=42
)
model_cv.fit(X_train, y_train)

preds = model_cv.predict(X_test)
probs = model_cv.predict_proba(X_test)[:, 1]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(SCRIPT_DIR, 'mlb_model.joblib')

joblib.dump({'model': model_cv, 'feature_cols': feature_cols,'metrics': {'accuracy': accuracy_score(y_test, preds),}}, MODEL_PATH)
print("Final model saved to mlb_model.joblib")
print("Accuracy:", accuracy_score(y_test, preds))
print("AUC:", roc_auc_score(y_test, probs))
print("Best C:", model_cv.C_)



#LOGISTIC REGRESSION IS the second best
# model = LogisticRegression(max_iter=1000)
# model.fit(X_train, y_train)

# preds = model.predict(X_test)
# probs = model.predict_proba(X_test)[:, 1]


# print("Accuracy:", accuracy_score(y_test, preds))
# print("AUC:", roc_auc_score(y_test, probs))

# naive_baseline = y_test.mean() if y_test.mean() > 0.5 else 1 - y_test.mean()
# print("Naive baseline:", naive_baseline)

# print(len(train), len(test))


#RANDOM FOREST THIRD BEST SO FAR
# rf_model = RandomForestClassifier(
#     n_estimators=300,
#     max_depth=3,
#     min_samples_leaf=40,
#     random_state=42
# )
# rf_model.fit(X_train, y_train)

# rf_preds = rf_model.predict(X_test)
# rf_probs = rf_model.predict_proba(X_test)[:, 1]

# print("Random Forest:")
# print("Accuracy:", accuracy_score(y_test, rf_preds))
# print("AUC:", roc_auc_score(y_test, rf_probs))
# print("Train accuracy:", accuracy_score(y_train, rf_model.predict(X_train)))


#WORST SO FAR BY A SMALL BIT

# xgb_model = XGBClassifier(
#     n_estimators=200,
#     max_depth=3,
#     learning_rate=0.05,
#     min_child_weight=20,
#     subsample=0.8,
#     colsample_bytree=0.8,
#     random_state=42,
#     eval_metric='logloss'
# )
# xgb_model.fit(X_train, y_train)

# xgb_preds = xgb_model.predict(X_test)
# xgb_probs = xgb_model.predict_proba(X_test)[:, 1]

# print("XGBoost:")
# print("Accuracy:", accuracy_score(y_test, xgb_preds))
# print("AUC:", roc_auc_score(y_test, xgb_probs))
# print("Train accuracy:", accuracy_score(y_train, xgb_model.predict(X_train)))
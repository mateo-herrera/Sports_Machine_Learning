from team_data_pipeline import get_training_data
from pitcher_pipeline import get_full_training_data

final_df = get_training_data()
final_df_with_pitchers = get_full_training_data(final_df)

print(final_df_with_pitchers.shape)
print(final_df_with_pitchers.head())

#USED FOR DEBUGGING OR UPDATING DATA IN THE FUTURE
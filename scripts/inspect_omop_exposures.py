import pandas as pd

df = pd.read_csv("data/05_reference_standards/omop/omop_reference_set.csv")
print("Unique Exposures (Drugs):", df['exposureName'].nunique())
print("Sample 20 Exposure Names:")
print(df['exposureName'].drop_duplicates().head(20).tolist())
print("\nUnique Outcomes:")
print(df[['outcomeId', 'outcomeName']].drop_duplicates())

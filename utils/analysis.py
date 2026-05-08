import pandas as pd
from utils.database import get_engine

def load_data(engine):
    query = """
    SELECT type, date(startDate) as date, value
    FROM health_records
    """
    df = pd.read_sql(query, engine)
    df['date'] = pd.to_datetime(df['date'])
    return df

def aggregate_data(df):
    # Some metrics should be summed (like Steps, DietaryEnergyConsumed), others averaged (HeartRate, VO2Max)
    # For simplicity, we first try to average everything, but let's define some sum metrics
    sum_metrics = [
        'StepCount', 'DistanceWalkingRunning', 'FlightsClimbed', 'AppleExerciseTime',
        'ActiveEnergyBurned', 'BasalEnergyBurned', 'DietaryEnergyConsumed',
        'DietaryWater', 'DietaryProtein', 'DietaryCarbohydrates', 'DietaryFatTotal'
    ]

    # We must group by date and type first, and then apply custom aggregation
    # because pivot_table passes a Series named 'value' to aggfunc.

    # Pre-aggregate: group by date and type, sum or mean based on type
    grouped = df.groupby(['date', 'type'])['value']

    # Calculate sums and means
    sums = grouped.sum()
    means = grouped.mean()

    # Combine based on type
    agg_df = pd.DataFrame(index=sums.index)
    agg_df['value'] = means # Default to mean

    # Identify which index combinations belong to sum_metrics
    # Create a boolean mask on the multiindex where the level 'type' is in sum_metrics
    mask = agg_df.index.get_level_values('type').isin(sum_metrics)

    # Overwrite the 'value' column with sum values where mask is True
    agg_df.loc[mask, 'value'] = sums[mask]

    # Now pivot
    pivot_df = agg_df.reset_index().pivot_table(
        index='date',
        columns='type',
        values='value',
        aggfunc='first' # We already aggregated, just restructure
    )

    return pivot_df

def compute_correlations(pivot_df):
    corr_matrix = pivot_df.corr(method='spearman')

    # Flatten the matrix to find top correlations
    corr_pairs = corr_matrix.unstack().dropna()
    corr_pairs = corr_pairs[corr_pairs.index.get_level_values(0) != corr_pairs.index.get_level_values(1)]

    # Remove duplicates (A-B and B-A)
    # Change column names to avoid "cannot insert type, already exists"
    corr_pairs.index.names = ['Metric 1', 'Metric 2']
    corr_pairs = corr_pairs.to_frame(name='Correlation').reset_index()

    corr_pairs['Abs_Corr'] = corr_pairs['Correlation'].abs()

    # Sort A-Z so we can drop duplicates based on pair
    corr_pairs['pair'] = corr_pairs.apply(lambda row: tuple(sorted([row['Metric 1'], row['Metric 2']])), axis=1)
    corr_pairs = corr_pairs.drop_duplicates(subset=['pair'])
    corr_pairs = corr_pairs.drop(columns=['pair'])

    corr_pairs = corr_pairs.sort_values(by='Abs_Corr', ascending=False)

    return corr_matrix, corr_pairs

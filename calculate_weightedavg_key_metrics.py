import argparse
import pandas as pd
import numpy as np
from pathlib import Path

# Segment buckets
def fico_bucket(fico):
    if pd.isna(fico) or fico < 620:
        return "[-999 to 620)"
    elif fico < 660:
        return "[620 to 660)"
    elif fico < 680:
        return "[660 to 680)"
    elif fico < 700:
        return "[680 to 700)"
    elif fico < 720:
        return "[700 to 720)"
    elif fico < 740:
        return "[720 to 740)"
    else:
        return "[740+]"

def mtmltv_bucket(val):
    pct = val * 100
    for i in range(0, 100, 10):
        if pct < i + 10:
            return f"[{i} to {i+10})"
    return "[100+]"

def dlq_bucket(val):
    if val == 0:
        return "0"
    elif 1 <= val <= 2:
        return "[1-2]"
    elif 3 <= val <= 6:
        return "[3-6]"
    else:
        return "[7+]"

def parse_headers(header_file, delimiter):
    with open(header_file, 'r') as f:
        return f.read().strip().split(delimiter)

def read_data(data_file, headers, delimiter, usecols):
    return pd.read_csv(data_file, delimiter=delimiter, names=headers, usecols=usecols, header=None)

def weighted_avg(df, group_col, value_cols, weight_col):
    grouped = df.groupby(group_col)
    result = []
    for name, group in grouped:
        weights = group[weight_col]
        row = {group_col: name, 'count': len(group), 'total_UPB': weights.sum()}
        for col in value_cols:
            row[col] = np.average(group[col], weights=weights) if not group[col].isnull().all() else np.nan
        result.append(row)
    return pd.DataFrame(result)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('loan_header')
    parser.add_argument('loan_data')
    parser.add_argument('final_header')
    parser.add_argument('final_data')
    parser.add_argument('output_file')
    args = parser.parse_args()

    loan_needed = ["LOAN_ID", "ACQUISITION_YEAR_MONTH", "CURRENT_UPB_DOLLAR", "CBD_CURRENT_FICO", "COMBINED_MTMLTV_RATE", "CURRENT_NOTE_RATE", "CURRENT_DLQ_MONTH_COUNT"]
    final_needed = ["LOAN_ID", "CFR", "StressCFR", "CPR", "StressCPR", "CPR5", "StressCPR5", "Losses", "GrossLosses", "StressLosses"]

    loan_headers = parse_headers(args.loan_header, ' ')
    final_headers = parse_headers(args.final_header, '|')

    loan_usecols = [c for c in loan_needed if c in loan_headers]
    final_usecols = [c for c in final_needed if c in final_headers]

    loan_df = read_data(args.loan_data, loan_headers, ' ', usecols=loan_usecols)
    final_df = read_data(args.final_data, final_headers, '|', usecols=final_usecols)

    loan_df = loan_df[loan_needed]
    final_df = final_df[final_needed]

    df = pd.merge(loan_df, final_df, on="LOAN_ID")

    df['MTMLTV_BUCKET'] = df['COMBINED_MTMLTV_RATE'].apply(mtmltv_bucket)
    df['FICO_BUCKET'] = df['CBD_CURRENT_FICO'].apply(fico_bucket)
    df['DLQ_BUCKET'] = df['CURRENT_DLQ_MONTH_COUNT'].apply(dlq_bucket)

    all_columns = ["CFR", "StressCFR", "CPR", "StressCPR", "CPR5", "StressCPR5", "Losses", "GrossLosses", "StressLosses"]

    segments = []

    # 1. All loans
    all_result = weighted_avg(df, group_col=pd.Series(["All Loans"] * len(df)), value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    all_result.insert(0, "Segment", all_result.index)
    segments.append(all_result)

    # 2. MTMLTV bucket
    mtmltv_result = weighted_avg(df, group_col="MTMLTV_BUCKET", value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    mtmltv_result.insert(0, "Segment", "MTMLTV: " + mtmltv_result["MTMLTV_BUCKET"].astype(str))
    segments.append(mtmltv_result)

    # 3. FICO bucket
    fico_result = weighted_avg(df, group_col="FICO_BUCKET", value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    fico_result.insert(0, "Segment", "FICO: " + fico_result["FICO_BUCKET"].astype(str))
    segments.append(fico_result)

    # 4. DLQ bucket
    dlq_result = weighted_avg(df, group_col="DLQ_BUCKET", value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    dlq_result.insert(0, "Segment", "DLQ: " + dlq_result["DLQ_BUCKET"].astype(str))
    segments.append(dlq_result)

    # 5. CURRENT_NOTE_RATE full pop
    rate_result = weighted_avg(df, group_col="CURRENT_NOTE_RATE", value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    rate_result.insert(0, "Segment", "NOTE_RATE: " + rate_result["CURRENT_NOTE_RATE"].astype(str))
    segments.append(rate_result)

    # 6. New acquisitions by MTMLTV
    new_acq = df[df['ACQUISITION_YEAR_MONTH'].isin([202409, 202408, 202407])].copy()
    new_acq['MTMLTV_BUCKET'] = new_acq['COMBINED_MTMLTV_RATE'].apply(mtmltv_bucket)
    new_mtmltv_result = weighted_avg(new_acq, group_col="MTMLTV_BUCKET", value_cols=all_columns, weight_col="CURRENT_UPB_DOLLAR")
    new_mtmltv_result.insert(0, "Segment", "NEWACQ_MTMLTV: " + new_mtmltv_result["MTMLTV_BUCKET"].astype(str))
    segments.append(new_mtmltv_result)

    # Combine and export
    final = pd.concat(segments, ignore_index=True)
    final.to_csv(args.output_file, index=False)
    print(f"✅ Output written to {args.output_file}")

if __name__ == '__main__':
    main()

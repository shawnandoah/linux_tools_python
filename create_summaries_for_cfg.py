import argparse
import pandas as pd
import re
from collections import defaultdict
from pathlib import Path
from openpyxl import Workbook

# Utility: parse a single cfg file into a list of functors with their properties
def parse_cfg(file_path):
    functors = []
    current = None

    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('[') and line.endswith(']'):
                functor_name = line[1:-1].strip()
                if '::' in functor_name or functor_name == 'Analytics':
                    current = None
                    continue
                current = {'name': functor_name, 'file': str(file_path), 'props': {}}
                functors.append(current)
            elif '=' in line and current is not None:
                k, v = map(str.strip, line.split('=', 1))
                if k not in current['props']:
                    current['props'][k] = v
    return functors

# Group by calculator type and gather metadata
def group_by_calculator(functors):
    calculators = defaultdict(lambda: {'files': set(), 'functors': []})

    for f in functors:
        if 'Type' in f['props']:
            calc_type = f['props']['Type']
            calculators[calc_type]['files'].add(f['file'])
            calculators[calc_type]['functors'].append(f)

    return calculators

# Build output Excel file
def write_summary(calculators, output_file):
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for calc, data in calculators.items():
            props = set()
            for f in data['functors']:
                props.update(k for k in f['props'] if k not in ('Type', 'Cashflow'))
            props = sorted(props)

            # Section a: Calculator name and used-in files
            used_in_df = pd.DataFrame(sorted(data['files']), columns=['CFG Files'])

            # Section b: List of Properties
            list_props_df = pd.DataFrame(props, columns=['Property Name'])

            # Section c: Table of Output
            rows = []
            for f in data['functors']:
                row = {p: f['props'].get(p, '') for p in props}
                row['Cashflow'] = f['props'].get('Cashflow', '')
                row['Name'] = f['name']
                rows.append(row)
            out_df = pd.DataFrame(rows)[['Cashflow', 'Name'] + props]

            # Write to Excel tab
            sheetname = str(calc)[:31]  # Excel sheet name max length = 31
            start = 0
            used_in_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)
            start += len(used_in_df) + 2
            list_props_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)
            start += len(list_props_df) + 2
            out_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)

# Main driver
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', required=True, help='Input .cfg file or .csv with paths')
    parser.add_argument('-o', '--outfile', default='./cfg_summary.xlsx', help='Output .xlsx file')
    args = parser.parse_args()

    input_path = Path(args.infile)
    cfg_files = []

    if input_path.suffix == '.cfg':
        cfg_files = [input_path]
    elif input_path.suffix == '.csv':
        cfg_files = [Path(line.strip()) for line in open(input_path) if line.strip()]
    else:
        raise ValueError("Input must be a .cfg file or a .csv listing .cfg files")

    all_functors = []
    for file in cfg_files:
        if file.exists():
            all_functors.extend(parse_cfg(file))

    grouped = group_by_calculator(all_functors)
    write_summary(grouped, args.outfile)
    print(f" Summary written to {args.outfile}")

if __name__ == '__main__':
    main()

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

# Utility: extract function block with nested braces
def extract_function_block(content, func_pattern):
    match = re.search(func_pattern, content)
    if not match:
        return None
    start_idx = match.end()
    brace_count = 1
    i = start_idx
    while i < len(content):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return content[match.start():i+1]
        i += 1
    return None

# Parse properties from C++ implementation file
def parse_cpp_properties(cpp_path):
    cpp_path = Path(cpp_path)
    if not cpp_path.exists():
        return {}

    with open(cpp_path, 'r') as f:
        content = f.read()

    init_block = extract_function_block(content, r'\w+::init\s*\([^)]*\)\s*{')
    if not init_block:
        return {}

    props = {}
    for line in init_block.splitlines():
        line = line.strip()
        if 'vm->' in line and 'get' in line and 'Setting' in line:
            match = re.search(r'mcfg\s*\+\s*"?(\w+)"?\s*,\s*([^)]+)', line)
            if match:
                prop = match.group(1)
                default = match.group(2).strip()
                if default != '0':
                    props[prop] = default
                else:
                    props[prop] = ''
            else:
                match = re.search(r'mcfg\s*\+\s*"?(\w+)"?', line)
                if match:
                    prop = match.group(1)
                    props[prop] = ''
    return props

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
    output_file = Path(output_file)
    if output_file.exists():
        output_file.unlink()

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for calc, data in calculators.items():
            all_props = set()
            for f in data['functors']:
                all_props.update(f['props'].keys())
            props = sorted(p for p in all_props if p not in ('Type', 'Cashflow'))
            props_for_list = sorted(p for p in props if p != 'OutputName')

            # Section a: Calculator name and used-in files
            sorted_files = sorted(data['files'])
            relative_paths = [f.split("m5-ccfa2.0/", 1)[-1] if "m5-ccfa2.0/" in f else f for f in sorted_files]
            used_in_df = pd.DataFrame(relative_paths, columns=['CFG Files'])

            # Section b: List of Properties
            list_props_df = pd.DataFrame(props_for_list, columns=['Property Name'])

            # Section c: Table of Output
            file_short_map = {f: Path(f).name for f in sorted_files}
            unique_rows = {}
            for f in data['functors']:
                row_key = tuple(f['props'].get(p, '') for p in props)
                if row_key not in unique_rows:
                    base_row = {p: f['props'].get(p, '') for p in props}
                    base_row['Cashflow'] = f['props'].get('Cashflow', '')
                    base_row['Name'] = f['name']
                    for short in file_short_map.values():
                        base_row[short] = ''
                    unique_rows[row_key] = base_row
                short_name = file_short_map[f['file']]
                unique_rows[row_key][short_name] = 'X'

            all_columns = ['Cashflow', 'Name'] + props + list(file_short_map.values())
            out_df = pd.DataFrame(list(unique_rows.values()))[all_columns]
            out_df = out_df.dropna(subset=['Name'])
            if out_df.empty:
                continue
            out_df.sort_values(by=['Cashflow', 'Name'], inplace=True)

            # Write to Excel tab
            sheetname = str(calc)[:31]
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
    parser.add_argument('-c', '--cpp', help='Optional .csv of C++ source files including register.cpp')
    args = parser.parse_args()

    input_path = Path(args.infile)
    cfg_files = []

    if input_path.suffix == '.cfg':
        cfg_files = [input_path]
    elif input_path.suffix == '.csv':
        with open(input_path, newline='') as csvfile:
            import csv
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    path_str = row[0].strip().replace("PosixPath(", "").replace(")", "").replace("'", "").strip()
                    cfg_files.append(Path(path_str))
    else:
        raise ValueError("Input must be a .cfg file or a .csv listing .cfg files")

    all_functors = []
    for file in cfg_files:
        if file.exists():
            all_functors.extend(parse_cfg(file))

    grouped = group_by_calculator(all_functors)
    write_summary(grouped, args.outfile)
    print(f"✅ Summary written to {args.outfile}")

if __name__ == '__main__':
    main()

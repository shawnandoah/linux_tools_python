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
                if '::' in functor_name or functor_name.lower() == 'analytics':
                    current = None
                    continue
                current = {'name': functor_name, 'file': str(file_path), 'props': {}}
                functors.append(current)
            elif '=' in line and current is not None:
                k, v = map(str.strip, line.split('=', 1))
                k = k.lower()
                if k not in current['props']:
                    current['props'][k] = v
    return functors

# Group by calculator type and gather metadata
def group_by_calculator(functors):
    calculators = defaultdict(lambda: {'files': set(), 'functors': []})

    for f in functors:
        if 'type' in f['props']:
            calc_type = f['props']['type']
            calculators[calc_type]['files'].add(f['file'])
            calculators[calc_type]['functors'].append(f)

    return calculators

# Parse register.cpp to extract calculator mappings
def parse_register_cpp(register_path):
    with open(register_path, 'r') as f:
        content = f.read()
    reg_block = re.search(r'Register\(\)\s*\{(.*?)\}', content, re.DOTALL)
    if not reg_block:
        return []
    registrations = re.findall(
    r'Registrator<\s*Calculator\s*>.*?"([^"]+)"\s*,\s*ObjectFactory<\s*Calculator\s*>::DFactoryMethod<\s*([^>\s]+)\s*>',
    reg_block,
    re.DOTALL
)

    return registrations

# Parse calculator implementation files for default property values
def parse_cpp_properties(cpp_path):
    with open(cpp_path, 'r') as f:
        content = f.read()
    props = []
    init_block = re.search(r'init\s*\(\)\s*\{(.*?)\}', content, re.DOTALL)
    if not init_block:
        return props
    lines = init_block.group(1).splitlines()
    for line in lines:
        if 'vm->' in line and re.search(r'Get\w+Setting', line):
            match = re.search(r'mcfg\s*\+\s*\"?(\w+)\"?\s*,\s*(\d+)?', line)
            if match:
                name = match.group(1)
                default = match.group(2) if match.group(2) else ''
                props.append((name, default))
    return props

# Build output Excel file
def write_summary(calculators, output_file, reg_data, cpp_props):
    output_file = Path(output_file)
    if output_file.exists():
        output_file.unlink()

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        summary_rows = []

        for calc, data in calculators.items():
            all_props = set()
            for f in data['functors']:
                all_props.update(f['props'].keys())
            props = sorted(p for p in all_props if p not in ('type', 'cashflow'))
            props_for_list = sorted(p for p in props if p != 'outputname')

            # Section a: Calculator name and used-in files
            sorted_files = sorted(data['files'])
            relative_paths = [f.split("m5-ccfa2.0/", 1)[-1] if "m5-ccfa2.0/" in f else f for f in sorted_files]
            used_in_df = pd.DataFrame(relative_paths, columns=['CFG Files'])

            # Section b: List of Properties + defaults from cpp
            prop_defaults = {k: v for k, v in cpp_props.get(calc, [])}
            combined_props = sorted(set(props_for_list).union(prop_defaults.keys()))
            list_props_df = pd.DataFrame([{"Property Name": p, "Default value": prop_defaults.get(p, '')} for p in combined_props])

            # Section c: Table of Output
            file_short_map = {f: Path(f).name for f in sorted_files}
            unique_rows = {}
            for f in data['functors']:
                row_key = tuple(f['props'].get(p, '') for p in props)
                if row_key not in unique_rows:
                    base_row = {p: f['props'].get(p, '') for p in props}
                    base_row['Cashflow'] = f['props'].get('cashflow', '')
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

            sheetname = str(calc)[:31]
            start = 0
            used_in_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)
            start += len(used_in_df) + 2
            list_props_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)
            start += len(list_props_df) + 2
            out_df.to_excel(writer, sheet_name=sheetname, index=False, startrow=start)

            # Add to summary tab
            for cname, impl in reg_data:
                if impl.lower().startswith(calc.lower()):
                    summary_rows.append({"Tab": impl, "Calculator Name": cname, "Type": calc, "Description": ''})

        # Write summary tab
        if summary_rows:
            pd.DataFrame(summary_rows)[["Tab", "Calculator Name", "Type", "Description"]].to_excel(writer, sheet_name="calculator summary", index=False)

# Main driver
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile', required=True, help='Input .cfg file or .csv with paths')
    parser.add_argument('-o', '--outfile', default='./cfg_summary.xlsx', help='Output .xlsx file')
    parser.add_argument('-c', '--cpp', help='CSV file with list of calculator .cpp files')
    args = parser.parse_args()

    input_path = Path(args.infile)
    cpp_path = Path(args.cpp) if args.cpp else None
    cfg_files = []
    cpp_files = []
    reg_data = []
    cpp_props = defaultdict(list)

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

    if cpp_path and cpp_path.exists():
        with open(cpp_path, newline='') as csvfile:
            import csv
            reader = csv.reader(csvfile)
            for row in reader:
                if row:
                    path = Path(row[0].strip())
                    if path.exists():
                        cpp_files.append(path)

    for file in cpp_files:
        if file.name == 'register.cpp':
            reg_data = parse_register_cpp(file)
        else:
            props = parse_cpp_properties(file)
            name = file.stem.replace('Calculator', '').lower()
            cpp_props[name] = props

    all_functors = []
    for file in cfg_files:
        if file.exists():
            all_functors.extend(parse_cfg(file))

    grouped = group_by_calculator(all_functors)
    write_summary(grouped, args.outfile, reg_data, cpp_props)
    print(f"✅ Summary written to {args.outfile}")

if __name__ == '__main__':
    main()

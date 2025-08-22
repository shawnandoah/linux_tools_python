#!/bin/bash

file1="$1"
file2="$2"

if [[ -z "$file1" || -z "$file2" ]]; then
  echo "Usage: $0 file1.csv file2.csv"
  exit 1
fi

# === Duplicate Detection ===
detect_duplicates() {
  local file="$1"
  local output="$2"
  awk -F',' '
    {count[$1]++; lines[$1]=lines[$1] ORS $0}
    END {
      for (k in count)
        if (count[k]>1)
          printf "%s", lines[k] > output
    }
  ' "$file"
}

detect_duplicates "$file1" "duplicates_in_file1.txt"
detect_duplicates "$file2" "duplicates_in_file2.txt"

has_dupes_f1=$(wc -l < duplicates_in_file1.txt)
has_dupes_f2=$(wc -l < duplicates_in_file2.txt)

if (( has_dupes_f1 > 0 || has_dupes_f2 > 0 )); then
  echo "❌ Duplicate keys found:"
  [[ $has_dupes_f1 -gt 0 ]] && echo " - See: duplicates_in_file1.txt"
  [[ $has_dupes_f2 -gt 0 ]] && echo " - See: duplicates_in_file2.txt"
  echo "Skipping comparison until duplicates are resolved."
  exit 1
fi

# === Sort Inputs ===
sort -t, -k1,1 "$file1" > f1_sorted.csv
sort -t, -k1,1 "$file2" > f2_sorted.csv

# === Header Detection ===
has_header() {
  local file="$1"
  local first_row
  first_row=$(head -n1 "$file")
  IFS=',' read -ra cols <<< "$first_row"
  local non_numeric=0
  local total=0
  for ((i=1; i<${#cols[@]}; i++)); do
    ((total++))
    if ! [[ "${cols[i]}" =~ ^[-+]?[0-9]*\.?[0-9]+$ ]]; then
      ((non_numeric++))
    fi
  done
  if (( total == 0 )); then
    return 1
  fi
  if (( non_numeric * 100 / total >= 70 )); then
    return 0
  else
    return 1
  fi
}

if has_header f1_sorted.csv && has_header f2_sorted.csv; then
  header=$(head -n1 f1_sorted.csv)
  tail -n +2 f1_sorted.csv > f1_data.csv
  tail -n +2 f2_sorted.csv > f2_data.csv
else
  header=""
  cp f1_sorted.csv f1_data.csv
  cp f2_sorted.csv f2_data.csv
fi

IFS=',' read -r -a columns <<< "$header"
num_cols=${#columns[@]}

# === Row Comparison with awk ===
awk -F',' -v OFS=',' -v num_cols="$num_cols" -v has_header="$header" '
  NR==FNR {
    a[$1] = $0
    total1++
    next
  }
  {
    key = $1
    total2++
    if (key in a) {
      matched++
      split(a[key], f1, ",")
      split($0, f2, ",")
      for (i = 2; i <= num_cols; i++) {
        cname = "Col" i
        if (f1[i] == f2[i]) {
          same[cname]++
        } else {
          diff[cname]++
          if (f1[i] ~ /^[-+]?[0-9]*\.?[0-9]+$/ && f2[i] ~ /^[-+]?[0-9]*\.?[0-9]+$/) {
            v1 = f1[i] + 0
            v2 = f2[i] + 0
            pct = (v1 == 0 && v2 == 0) ? 0 : (100 * (v2 - v1) / (v1 == 0 ? 1 : v1))
            min[cname] = (min[cname] == "" || pct < min[cname]) ? pct : min[cname]
            max[cname] = (max[cname] == "" || pct > max[cname]) ? pct : max[cname]
            sum[cname] += pct
            count[cname]++
          }
        }
      }
    } else {
      missing2++
    }
  }
  END {
    for (k in a) seen1[k]++
    for (k in seen1)
      if (!(k in a)) missing1++

    print "File 1 row count:", total1 > "compare_result.txt"
    print "File 2 row count:", total2 >> "compare_result.txt"
    print "" >> "compare_result.txt"
    print "Matched keys:", matched >> "compare_result.txt"
    print "Unmatched keys in File1:", total1 - matched >> "compare_result.txt"
    print "Unmatched keys in File2:", total2 - matched >> "compare_result.txt"
    print "" >> "compare_result.txt"
    print "Column Comparison Summary:" >> "compare_result.txt"
    print "----------------------------------------------------------" >> "compare_result.txt"
    printf "%-14s | %-9s | %-9s | %-10s | %-10s | %-10s\n", "Column Name", "Same Rows", "Diff Rows", "%Diff Min", "%Diff Max", "%Diff Mean" >> "compare_result.txt"
    print "----------------------------------------------------------" >> "compare_result.txt"
    for (i = 2; i <= num_cols; i++) {
      cname = "Col" i
      minval = (min[cname] == "") ? "-" : sprintf("%.2f%%", min[cname])
      maxval = (max[cname] == "") ? "-" : sprintf("%.2f%%", max[cname])
      meanval = (count[cname] == 0) ? "-" : sprintf("%.2f%%", sum[cname] / count[cname])
      colname = (has_header != "") ? "'\''" columns[i-1] "'\''" : cname
      printf "%-14s | %-9d | %-9d | %-10s | %-10s | %-10s\n", colname, same[cname]+0, diff[cname]+0, minval, maxval, meanval >> "compare_result.txt"
    }
  }
' f1_data.csv f2_data.csv

# === Cleanup temp files ===
rm -f f1_sorted.csv f2_sorted.csv f1_data.csv f2_data.csv

echo "✅ Done. Results written to compare_result.txt"
[[ -s duplicates_in_file1.txt ]] && echo "🔍 Duplicates found in file1: duplicates_in_file1.txt"
[[ -s duplicates_in_file2.txt ]] && echo "🔍 Duplicates found in file2: duplicates_in_file2.txt"

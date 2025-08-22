#!/bin/bash

file1="$1"
file2="$2"

if [[ -z "$file1" || -z "$file2" ]]; then
  echo "Usage: $0 file1.csv file2.csv"
  exit 1
fi

# Ensure sorted by key (first column)
sort -t, -k1,1 "$file1" > f1_sorted.csv
sort -t, -k1,1 "$file2" > f2_sorted.csv

# Get header
header=$(head -n1 f1_sorted.csv)
IFS=',' read -r -a columns <<< "$header"
num_cols=${#columns[@]}

# Strip headers
tail -n +2 f1_sorted.csv > f1_data.csv
tail -n +2 f2_sorted.csv > f2_data.csv

# Use awk to compare
awk -F, -v OFS="," -v num_cols="$num_cols" '
  NR==FNR { a[$1] = $0; next }
  {
    key = $1
    if (key in a) {
      split(a[key], f1, ",")
      split($0, f2, ",")
      for (i = 2; i <= num_cols; i++) {
        cname = "Col" i
        if (f1[i] == f2[i]) {
          same[cname]++
        } else {
          diff[cname]++
          # try to compute % difference if numeric
          if (f1[i] ~ /^[0-9.]+$/ && f2[i] ~ /^[0-9.]+$/) {
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
      matched++
    } else {
      missing2++
    }
  }
  END {
    for (k in a) total1++
    while ((getline < "f2_data.csv") > 0) {
      split($0, tmp, ","); seen[tmp[1]]++
    }
    for (k in a) {
      if (!(k in seen)) missing1++
    }
    
    print "File 1 row count:", total1 > "compare_result.txt"
    print "File 2 row count:", FNR > "compare_result.txt"
    print "" >> "compare_result.txt"
    print "Matched keys:", matched >> "compare_result.txt"
    print "Unmatched keys in File1:", missing1 >> "compare_result.txt"
    print "Unmatched keys in File2:", missing2 >> "compare_result.txt"
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
      printf "%-14s | %-9d | %-9d | %-10s | %-10s | %-10s\n", columns[i-1], same[cname]+0, diff[cname]+0, minval, maxval, meanval >> "compare_result.txt"
    }
  }
' f1_data.csv f2_data.csv

echo "✅ Done. Output written to compare_result.txt"

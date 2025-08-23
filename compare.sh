#!/bin/bash

file1="$1"
file2="$2"

if [[ -z "$file1" || -z "$file2" ]]; then
  echo "Usage: $0 file1.csv file2.csv"
  exit 1
fi

# Convert to full paths
file1_path=$(realpath "$file1")
file2_path=$(realpath "$file2")

# Ensure sorted by key (first column)
sort -t, -k1,1 "$file1" > f1_sorted.csv
sort -t, -k1,1 "$file2" > f2_sorted.csv

# Get header line
header=$(head -n1 f1_sorted.csv)

# Strip header
tail -n +2 f1_sorted.csv > f1_data.csv
tail -n +2 f2_sorted.csv > f2_data.csv

# Output file
outfile="compare_result.txt"

awk -F, -v OFS="," -v num_cols="$(awk -F, '{print NF; exit}' "$file1")" \
    -v out="$outfile" -v header="$header" -v file1_path="$file1_path" -v file2_path="$file2_path" '
BEGIN {
  split(header, columns, ",")
  print "Compare Report" > out
  print "===================" >> out
  print "File 1: " file1_path >> out
  print "File 2: " file2_path >> out
  print "" >> out
}
NR==FNR { a[$1] = $0; next }
{
  key = $1
  if (key in a) {
    split(a[key], f1, ",")
    split($0, f2, ",")
    for (i = 2; i <= num_cols; i++) {
      cname = columns[i]
      if (f1[i] == f2[i]) {
        same[cname]++
      } else {
        diff[cname]++
        # handle % diff if numeric
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

  print "File 1 row count: " total1 >> out
  print "File 2 row count: " FNR >> out
  print "" >> out
  print "Matched keys: " matched >> out
  print "Unmatched keys in File1: " missing1 >> out
  print "Unmatched keys in File2: " missing2 >> out
  print "" >> out

  print "Column Comparison Summary:" >> out
  print "----------------------------------------------------------" >> out
  printf "%-20s | %-9s | %-9s | %-10s | %-10s | %-10s\n", "Column Name", "Same Rows", "Diff Rows", "%Diff Min", "%Diff Max", "%Diff Mean" >> out
  print "----------------------------------------------------------" >> out

  for (i = 2; i <= num_cols; i++) {
    cname = columns[i]
    minval = (min[cname] == "") ? "-" : sprintf("%.2f%%", min[cname])
    maxval = (max[cname] == "") ? "-" : sprintf("%.2f%%", max[cname])
    meanval = (count[cname] == 0) ? "-" : sprintf("%.2f%%", sum[cname] / count[cname])
    printf "%-20s | %-9d | %-9d | %-10s | %-10s | %-10s\n", cname, same[cname]+0, diff[cname]+0, minval, maxval, meanval >> out
  }
}
' f1_data.csv f2_data.csv

echo "✅ Done. Output written to compare_result.txt"

#!/bin/bash

file1="$1"
file2="$2"

if [[ -z "$file1" || -z "$file2" ]]; then
  echo "Usage: $0 file1.csv file2.csv"
  exit 1
fi

# Convert to full paths and base names
file1_path=$(realpath "$file1")
file2_path=$(realpath "$file2")
base1=$(basename "$file1" .csv)
base2=$(basename "$file2" .csv)

# Set output filename
outfile="compare_result_${base1}_f${base2}.txt"

# Sort both by first column
sort -t, -k1,1 "$file1" > f1_sorted.csv
sort -t, -k1,1 "$file2" > f2_sorted.csv

# Get header and number of columns
header=$(head -n1 f1_sorted.csv)
num_cols=$(awk -F, 'NR==1 {print NF}' f1_sorted.csv)

# Strip headers
tail -n +2 f1_sorted.csv > f1_data.csv
tail -n +2 f2_sorted.csv > f2_data.csv

awk -F, -v OFS="," -v num_cols="$num_cols" \
    -v out="$outfile" -v header="$header" -v file1_path="$file1_path" -v file2_path="$file2_path" '
BEGIN {
  split(header, columns, ",")
  print "Compare Report" > out
  print "===================" >> out
  print "File 1: " file1_path >> out
  print "File 2: " file2_path >> out
  print "" >> out
}
NR==FNR {
  a[$1] = $0
  next
}
{
  key = $1
  seen2[key] = $0
  if (key in a) {
    split(a[key], f1, ",")
    split($0, f2, ",")
    row_diff = 0
    for (i = 2; i <= num_cols; i++) {
      cname = columns[i]
      if (f1[i] == f2[i]) {
        same[cname]++
      } else {
        row_diff = 1
        diff[cname]++
        if (f1[i] ~ /^[0-9.\-eE]+$/ && f2[i] ~ /^[0-9.\-eE]+$/) {
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
    if (row_diff && diff_row_count < 10) {
      diff_rows1[diff_row_count] = a[key]
      diff_rows2[diff_row_count] = $0
      diff_row_count++
    }
    matched++
  } else {
    if (missing2_count < 10) missing2_list[missing2_count++] = key
    missing2++
  }
}
END {
  for (k in a) {
    total1++
    if (!(k in seen2)) {
      if (missing1_count < 10) missing1_list[missing1_count++] = k
      missing1++
    }
  }

  print "File 1 row count: " total1 >> out
  print "File 2 row count: " FNR >> out
  print "" >> out
  print "Matched keys: " matched >> out
  print "Unmatched keys in File1: " missing1 >> out
  if (missing1 > 0) {
    print "First 10 unmatched keys in File1:" >> out
    for (i = 0; i < missing1_count; i++) print "  " missing1_list[i] >> out
  }
  print "" >> out
  print "Unmatched keys in File2: " missing2 >> out
  if (missing2 > 0) {
    print "First 10 unmatched keys in File2:" >> out
    for (i = 0; i < missing2_count; i++) print "  " missing2_list[i] >> out
  }
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

  if (diff_row_count > 0) {
    print "" >> out
    print "Sample of 10 Differing Rows:" >> out
    print "----------------------------" >> out
    print "Header: " header >> out
    print "" >> out
    for (i = 0; i < diff_row_count; i++) {
      print "[File1] " diff_rows1[i] >> out
      print "[File2] " diff_rows2[i] >> out
      print "" >> out
    }
  }
}
' f1_data.csv f2_data.csv

echo "✅ Done. Output written to $outfile"

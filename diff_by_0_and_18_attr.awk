awk -F'|' 'FNR==NR { id=$1; a[id]=$18; next } { id=$1; if (id in a && a[id] != $18) { print "ID:", id; print "File1 18th:", a[id]; print "File2 18th:", $18; print "---" } }' file1.txt file2.txt

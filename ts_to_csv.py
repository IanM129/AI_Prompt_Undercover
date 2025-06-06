import os
import sys


rf = open("wordPairs.ts", "r");
wf = open("wordPairs.csv", "w");
wf.write("majority,undercover\n");

for line in rf:
    line = line.strip();
    if (line.startswith('[')):
        comind = line.index(',');
        data = (line[1:comind], line[comind+2:len(line) - 2]);
        print(data[0] + ',' + data[1]);
        wf.write(data[0] + ',' + data[1] + '\n');

rf.close();
wf.close();
sys.exit(0);

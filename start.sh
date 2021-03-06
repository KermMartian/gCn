# globalCALCnet Hub/Service Starting Script
# Rudimentary at best, but it gets the job done
# Christopher Mitchell, 2012-2014
# Licensed under the BSD 3-Clause License (see LICENSE)

Execs=('gcnirc' 'gcnweb' 'gcnftp' 'gcnhub') #'gcnguest' 
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH=DIR:$PYTHONPATH

echo "Killing old executables..."
for Exec in "${Execs[@]}"
do
	kill -9 `pgrep $Exec`
done

echo "Starting new executables..."

for ((i=${#Execs[@]}-1; i>=0; i--)); do
	./${Execs[$i]}/${Execs[$i]}.py &
	sleep 6
done

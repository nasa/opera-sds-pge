# Run a PGE from the test data directory (where the runconfig XML is) with different ProcessingThreads values
#
# This script wraps a "docker run" command with metrics_collection_start() and
# metrics_collection_end() function calls.  See swot_pge/.ci/util.sh for details.
#
# usage:
#     run_metrics_series.sh <pge> <run config> <processing threads list, e.g. 8 16 32 48 96>
#
# example:
#     run_metrics_series.sh l1b_hr_slc l1bhrslc.rc.xml 64 32 16 8 4 2 1bash
#
# If there is a ProcessingThreads entry in the run config, it will be adjusted for each loop iteration.
# If there is not a ProcessingThreads, then the sed command will not modify the run config.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

. "${SCRIPT_DIR}"/util.sh

PGE=$1
RC=$2
shift 2

echo "$PGE"
echo "$RC"

container_name="${ghrVersion}.${PGE}.${RC}"
metrics_collection_start "$container_name"

docker run --rm --name "${container_name}" -u ${UID} -v "$(pwd)":/pge/run -w /pge/run pge/"${PGE}":"${ghrVersion}" /pge/run/"${RC}"
docker_run_exit_code=$?
echo "docker run exited with code $docker_run_exit_code"

metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RC"




container_name="abc"
metrics_collection_start "$container_name"

exit 0


#
#for npt in "$@"
#do
#    # clean up any disk space that may have been used by a prior run
#    rm -rf output/
#    rm -rf scratch/
#
#    # modify the runconfig to set the processors value
#    sed -i "s/ProcessingThreads=\"[0-9]*\"/ProcessingThreads=\"$npt\"/g" "${RC}"
#
#    # do the thing
#    echo "Running pge $PGE using run config $RC"
#    NPT=$(grep ProcessingThreads "$RC")
#    echo "$NPT"
#
#    container_name="${ghrVersion}.${PGE}.${RC}"
#    metrics_collection_start "$container_name"
#
#    docker run --rm --name "${container_name}" -u ${UID} -v "$(pwd)":/pge/run -w /pge/run pge/"${PGE}":"${ghrVersion}" /pge/run/"${RC}"
#    docker_run_exit_code=$?
#    echo "docker run exited with code $docker_run_exit_code"
#
#    metrics_collection_end "$container_name" $docker_run_exit_code "$PGE" "$RC"
#done

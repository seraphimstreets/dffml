import pathlib

# Command line utility helpers and DataFlow specific classes
from dffml import CMD, Arg, DataFlow, Input, GetSingle, run

# Allow users to give us a Git repo URL and we'll clone it and turn it into a
# directory that will be scanned
from dffml_feature_git.feature.operations import (
    clone_git_repo,
    cleanup_git_repo,
)

# Import checkers and analyzers
from .python.check import check_python
from .python.analyze import analyze_python
from .javascript.check import check_javascript
from .javascript.analyze import analyze_javascript

# Import static analysis result definition
from .types import SA_RESULTS


# Link inputs and outputs together according to their definitions
DATAFLOW = DataFlow.auto(
    clone_git_repo,
    check_python,
    analyze_python,
    check_javascript,
    analyze_javascript,
    cleanup_git_repo,
    GetSingle,
)
DATAFLOW.seed.append(
    Input(value=[SA_RESULTS.name,], definition=GetSingle.op.inputs["spec"],)
)

# Allow for directory to be provided by user instead of the result of cloning a
# Git repo to a temporary directory on disk
for opimp in [
    check_python,
    analyze_python,
    check_javascript,
    analyze_javascript,
]:
    DATAFLOW.flow[opimp.op.name].inputs["repo"].append("seed")
DATAFLOW.update()


class Use(CMD):

    arg_targets = Arg(
        "targets", nargs="+", help="Git repo URLs or directories to analyze"
    )

    async def run(self):
        # Make a corresponding list of path objects in case any of the targets
        # we are given are paths on disk rather than Git repo URLs
        paths = [
            pathlib.Path(target_name).expanduser().resolve()
            for target_name in self.targets
        ]
        # Run all the operations, Each iteration of this loop happens
        # when all inputs are exhausted for a context, the output
        # operations are then run and their results are yielded
        async for target_name, results in run(
            DATAFLOW,
            {
                # For each target add a new input set to the input network
                # The context operations execute under is the target name
                # to evaluate. Contexts ensure that data pertaining to
                # target A doesn't mingle with data pertaining to target B
                target_name: [
                    # The only input to the operations is the target name.
                    Input(
                        value={
                            "URL": "file://" + str(path),
                            "directory": str(path),
                        },
                        definition=clone_git_repo.op.outputs["repo"],
                    )
                    if path.is_dir()
                    else Input(
                        value=target_name,
                        definition=clone_git_repo.op.inputs["URL"],
                    )
                ]
                for target_name, path in zip(self.targets, paths)
            },
        ):
            print(results)

"""Module describing the planemo ``autoupdate`` command."""
import os.path

import click

from planemo import autoupdate, options
from planemo.cli import command_function
from planemo.config import planemo_option
from planemo.engine.test import (
    test_runnables,
)
from planemo.exit_codes import (
    EXIT_CODE_GENERIC_FAILURE,
    EXIT_CODE_OK
)
from planemo.io import (
    coalesce_return_codes,
    error,
    info,
    temp_directory
)
from planemo.runnable import (
    for_paths,
)
from planemo.tools import (
    is_tool_load_error,
    yield_tool_sources_on_paths
)


def dry_run_option():
    """Perform a dry run autoupdate without modifying the XML files"""
    return planemo_option(
        "--dry-run",
        is_flag=True,
        help="Perform a dry run autoupdate without modifying the XML files."
    )


def test_option():
    """Test updated XML files"""
    return planemo_option(
        "--test",
        is_flag=True,
        help="Test updated XML files."
    )


@click.command('autoupdate')
@options.optional_tools_arg(multiple=True)
@dry_run_option()
@options.recursive_option()
@test_option()
@options.test_options()
@options.galaxy_target_options()
@options.galaxy_config_options()
@options.report_level_option()
@options.report_xunit()
@options.fail_level_option()
@options.skip_option()
@command_function
def cli(ctx, paths, **kwds):
    """Auto-update tool requirements by checking against Conda and updating if newer versions are available."""
    assert_tools = kwds.get("assert_tools", True)
    recursive = kwds.get("recursive", False)
    exit_codes = []
    modified_files = set()
    for (tool_path, tool_xml) in yield_tool_sources_on_paths(ctx, paths, recursive):
        info("Auto-updating tool %s" % tool_path)
        try:
            updated = autoupdate.autoupdate(ctx, tool_path, modified_files=modified_files, **kwds)
            if updated:
                # modified_files += updated
                modified_files.update(updated)
        except Exception as e:
            error("{} could not be updated - the following error was raised: {}".format(tool_path, e.__str__()))
        if handle_tool_load_error(tool_path, tool_xml):
            exit_codes.append(EXIT_CODE_GENERIC_FAILURE)
            continue
        else:
            exit_codes.append(EXIT_CODE_OK)

    if kwds['test']:
        info("Running tests for auto-updated tools...")
        if not dirs_updated:
            info("No tools were updated, so no tests were run.")
        else:
            with temp_directory(dir=ctx.planemo_directory) as temp_path:
                # only test tools in updated directories
                paths = [path for path in paths if os.path.split(tool_path)[0] in dirs_updated]
                runnables = for_paths(paths, temp_path=temp_path)
                kwds["engine"] = "galaxy"
                return_value = test_runnables(ctx, runnables, original_paths=paths, **kwds)

    return coalesce_return_codes(exit_codes, assert_at_least_one=assert_tools)
    ctx.exit(return_value)


def handle_tool_load_error(tool_path, tool_xml):
    """ Return True if tool_xml is tool load error (invalid XML), and
    print a helpful error message.
    """
    is_error = False
    if is_tool_load_error(tool_xml):
        info("Could not update %s due to malformed xml." % tool_path)
        is_error = True
    return is_error
import glob
import os
import re
import sys

VALID_HUTCHES = [
    "xpp",
    "xcs",
    "cxi",
    "mfx",
    "mec",
    "tmo",
    "rix",
    "xrt",
    "aux",
    "det",
    "fee",
    "hpl",
    "icl",
    "las",
    "lfe",
    "kfe",
    "tst",
    "thz",
    "txi",
    "all",
]


def usage():
    print(f"""usage: {sys.argv[0]} <keyword> [hutch]

Options:
  -p, returns all discovered PVs of the IOC

greps hutch iocmanager config files for keyword
hutch can be any of:
{', '.join(VALID_HUTCHES)}
If no hutch is specified, all hutches will be searched
""")


def discover_pvs(paths):
    """
    Finds all PVs given a list of tuples returned from grep_ioc
    The line contents are parsed for these two patterns:
    id:'ioc-name'
    dir: 'path/to/ioc'
    and will extract the ioc-name and path/to/ioc string, then go to the db file there
    and parse it for PVs

    Inputs:
    path: list of tuples
        file path, line #, file line contents

    Outputs:
    pvs: list
        List of all strings of every found PV
    """
    db_paths = []
    dir_pattern = re.compile(r"dir:\s*'([^']+)'")
    id_pattern = re.compile(r"id:'([^']+)'")

    for _, _, line in paths:
        dir_match = dir_pattern.search(line)
        id_match = id_pattern.search(line)

        if dir_match and id_match:
            dir_path = dir_match.group(1)
            ioc_name = id_match.group(1)
            full_db_path = os.path.join(dir_path, "build", "iocBoot", f"{ioc_name}.db")
            db_paths.append(full_db_path)

    return db_paths


def grep_file(filepath, regex, ignore_case=False):
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(regex, flags)
    matches = []

    try:
        with open(filepath, "r", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if pattern.search(line):
                    matches.append((filepath, i, line.strip()))
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")

    return matches


def grep_ioc(regex, path_pattern, return_pvs=False):
    """
    Given a file path (includes wildcards), search for an instance of the regex pattern

    Inputs:
    regex : str
        Pattern to search for
    path_pattern: str
        File path to search in. If it has a wildcard, grab all mathcing files
    return_pvs: bool
        If True, grep_ioc will return a second list of all descovered PVs

    Output:
        List of lines where the regex is found
        Optionally a second list of descovered PVs
    """

    files = glob.glob(path_pattern, recursive=True)
    if not files and os.path.isfile(path_pattern):
        files = [path_pattern]

    all_matches = []
    for file in files:
        all_matches.extend(grep_file(file, regex, ignore_case=True))
    if return_pvs:
        pv_paths = discover_pvs(all_matches)
        return all_matches, pv_paths

    return all_matches


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        usage()
        sys.exit(0)

    # Initialize defaults
    pv = False
    keyword = sys.argv[1]
    hutch = "all"

    # Handle hutch and -p
    if len(sys.argv) == 3:
        if sys.argv[2] == "-p":
            pv = True
        elif sys.argv[2] in VALID_HUTCHES:
            hutch = sys.argv[2]
        else:
            print(f"Invalid argument: {sys.argv[2]}")
            usage()
            sys.exit(1)

    elif len(sys.argv) == 4:
        if sys.argv[2] in VALID_HUTCHES and sys.argv[3] == "-p":
            hutch = sys.argv[2]
            pv = True
        else:
            print("Incorrect usage of arguments.")
            usage()
            sys.exit(1)

    elif len(sys.argv) > 4:
        print("Too many arguments.")
        usage()
        sys.exit(1)

    # Path selection
    if hutch == "all":
        path_pattern = "/reg/g/pcds/pyps/config/*/iocmanager.cfg"
    else:
        path_pattern = f"/reg/g/pcds/pyps/config/{hutch}/iocmanager.cfg"

    # Main logic
    matches = grep_ioc(keyword, path_pattern, pv)

    for file, line_no, line in matches[0]:
        print(f"{file}:{line_no}: {line}")
    for line in matches[1]:
        print(line)

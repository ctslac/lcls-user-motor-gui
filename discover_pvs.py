import glob
import os
import re

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


def _build_plc_path(dir_path, ioc_name):
    """Build path for PLC .db files."""
    # If the ioc lives in someone's dev directory, the path passed here should end with iocBoot
    if "iocBoot" not in dir_path:
        dir_path = os.path.join(dir_path, "iocBoot", ioc_name)
    db_files = glob.glob(os.path.join(dir_path, "*.db"))

    if db_files:
        return db_files[0]
    return None


def _build_standard_path(dir_path, ioc_name):
    """Build path for standard IOC .db files."""
    ioc_clean_name = ioc_name.removeprefix("ioc-")
    return os.path.join(dir_path, "build", "iocBoot", ioc_name, f"{ioc_clean_name}.db")


def _get_db_file_path(dir_path, ioc_name, plc_flag):
    """Get the database file path for an IOC."""
    # Determine the full directory path
    if not (dir_path.startswith("/reg/") or dir_path.startswith("/cds/")):
        dir_path = os.path.join("/reg/g/pcds/epics", dir_path)

    # Build the appropriate path based on IOC type
    if plc_flag:
        return _build_plc_path(dir_path, ioc_name)
    else:
        return _build_standard_path(dir_path, ioc_name)


def _get_fallback_path(ioc_name):
    """Get fallback pvlist path when .db file is not found."""
    return os.path.join("/reg/d/iocData", ioc_name, "iocInfo", "IOC.pvlist")


def _extract_pvs_from_file(file_path, find_makefile):
    """Extract PVs from a single .db or .pvlist file."""
    pvs = []
    db_pattern = re.compile(r'record\s*\(\s*\w+\s*,\s*"([^"]+)"')

    try:
        if find_makefile:
            makefile_path = os.path.split(file_path)[0] + "/Makefile"
            if not os.path.exists(makefile_path):
                print(
                    "Failed to find Makefile, it does not exist in the folder containing the db. Continuing"
                )
            else:
                makefile_pattern = re.compile(r"(?<=PREFIX := ).*")
                with open(makefile_path, "r") as f:
                    for line in f:
                        match = makefile_pattern.search(line)
                        if match:
                            pvs.append(
                                match.group(0)
                            )  # Found a match for the prefix, now break out
                            break

        with open(file_path, "r") as f:
            # No need to use regex with pvlists
            if file_path.endswith(".pvlist"):
                for line in f:
                    pv = line.split(",")[0].strip()
                    if pv:
                        pvs.append(pv)
            else:
                for line in f:
                    match = db_pattern.search(line)
                    if match:
                        pvs.append(match.group(1))
    except Exception as e:
        print(f"Exception reading {file_path}: {e}")

    return pvs


def _build_db_path(paths, plc_flag):
    """Get the db or pvlist paths cooresponding to the ioc paths taken from iocmanager"""
    db_paths = []
    dir_pattern = re.compile(r"dir:\s*'([^']+)'")
    id_pattern = re.compile(r"id:'([^']+)'")

    for line in paths:
        dir_match = dir_pattern.search(line)
        id_match = id_pattern.search(line)

        if not (dir_match and id_match):
            continue

        dir_path = dir_match.group(1)
        ioc_name = id_match.group(1)

        # Try to get the primary db file path
        db_file_path = _get_db_file_path(dir_path, ioc_name, plc_flag)

        # If primary path doesn't exist, try fallback
        if not db_file_path or not os.path.exists(db_file_path):
            db_file_path = _get_fallback_path(ioc_name)

        db_paths.append(db_file_path)

    return db_paths


def grep_pvs(paths, plc_flag, usr_db_path=None, find_makefile=False):
    """
    Extracts PV .db or .pvlist file paths from grep match lines.
    Looks for id:'ioc-name' and dir: 'path/to/ioc'
    """
    if find_makefile and usr_db_path is None:
        print("find_makefile flag provided without a db path, exiting..")
        return 0

    # If this is user-provided, skip logic to build the path and go directly to getting PVs
    if usr_db_path is not None:
        return _extract_pvs_from_file(usr_db_path, find_makefile)

    # Get the db or pvlist paths given the ioc paths taken from iocmanager
    db_paths = _build_db_path(paths, plc_flag)

    # Extract PVs from all found files, removing duplicates
    seen = set()
    unique_pvs = []
    for path in db_paths:
        pvs = _extract_pvs_from_file(path, find_makefile)
        for pv in pvs:
            if pv not in seen:
                seen.add(pv)
                unique_pvs.append(pv)

    return unique_pvs


def grep_file(filepath, regex, plc_ioc_list):
    """Search for regex pattern in iocmanager files and return matching lines."""
    pattern = re.compile(regex, re.IGNORECASE)
    id_pattern = re.compile(r"id:'([^']+)'")
    matches = []

    try:
        with open(filepath, "r") as f:
            for line in f:
                # If plc_ioc_list is set, we want to keep the disabled entries and save their status in the results
                if "disable: True" in line and not plc_ioc_list:
                    continue
                id_match = id_pattern.search(line)
                if not id_match:
                    continue
                id_val = id_match.group(1)
                if pattern.search(id_val):
                    matches.append(line.strip())
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")

    return matches


def discover_pvs(
    keyword,
    hutch="all",
    plc_flag=False,
    plc_ioc_list=False,
    usr_db_path=None,
    find_makefile=False,
):
    """
    Searches iocmanager.cfg files for an IOC and extracts PV paths from db or pvlist files.

    Inputs:
    keyword : str
        IOC name to search for. If left blank, will return ALL PVs
    hutch : str
        One of the valid hutches, or "all" (default).
    plc_flag (optional): bool
        This flag will alter the search path for db files and return PVs that only live in the PLCs that were found
    plc_ioc_list (options): bool
        Return a dict of {IOC, db_path} for all PLCs that live in the iocmanager file(s) matching the keyword.
    usr_db_path (optional): str
        Direct path to a specific db file to use instead of searching via iocmanager files.
    find_makefile (optional) : str
        Get a prefix macro from the makefile. The usr_db_path must be provided. The first element of the returned list will be the prefix

    Returns:
    list of PVs (If plc_ioc_list is False)

    dictionary of {ioc_names, [status, db_paths]} (If plc_ioc_list is True)

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Ex. to get a dictionary of all PLCs and their db paths:
        discover_pvs('', hutch='all', plc_ioc_list=True)

    Ex. to get all PVs in a specific PLC:
        discover_pvs('svls', hutch='rix', plc_flag=True)

    Ex. to get the PVs of a specific IOC:
        discover_pvs('ioc_dccm_gige', hutch='lfe')
    """
    # Handle user-provided db path
    if usr_db_path is not None:
        if os.path.isfile(usr_db_path):
            return grep_pvs([], plc_flag, usr_db_path, find_makefile)
        else:
            raise FileExistsError(
                f"Invalid db path file provided: {usr_db_path}. File does not exist"
            )

    # Validate hutch parameter
    if hutch not in VALID_HUTCHES:
        raise ValueError(
            f"Invalid hutch: {hutch}. Must be one of: {', '.join(VALID_HUTCHES)}"
        )

    # Build file search pattern
    if hutch == "all":
        path_pattern = "/reg/g/pcds/pyps/config/*/iocmanager.cfg"
    else:
        path_pattern = f"/reg/g/pcds/pyps/config/{hutch}/iocmanager.cfg"

    # Find matching files
    files = glob.glob(path_pattern, recursive=True)
    if not files and os.path.isfile(path_pattern):
        files = [path_pattern]

    # Search for keyword in all files
    all_matches = []
    for file in files:
        matches = grep_file(file, keyword, plc_ioc_list)
        all_matches.extend(matches)

    if not all_matches:
        print("Could not find any files that match that ioc..")
        return []

    # Check flags aren't both set
    if plc_flag and plc_ioc_list:
        print(
            "This script is not meant to return more than one list. Instead, set only one flag and run this twice"
        )
        return []

    # Handle PLC-specific requests
    if plc_flag or plc_ioc_list:
        plc_dict = {}
        all_plc_db_paths = []

        # Filter matches to only include PLCs
        for match in all_matches:
            pattern = r"id:\s*'([^']*)'.*?dir:\s*'([^']*)'"
            parsed = re.search(pattern, match)

            if parsed:
                id_val, dir_val = parsed.groups()
                path_parts = dir_val.strip("/").split("/")

                # Check if any directory contains 'lcls-plc'
                if any("lcls-plc" in part for part in path_parts):
                    db_paths = _build_db_path([match], True)
                    db_path = db_paths[0] if db_paths else None

                    if plc_ioc_list:
                        # Get status
                        if "disable: True" in match:
                            status = "disabled"
                        elif "/epics-dev/" in match:
                            status = "dev"
                        else:
                            status = "prod"
                        plc_dict[id_val] = [status, db_path]

                    if db_path:
                        all_plc_db_paths.append(db_path)

        if plc_ioc_list:
            return plc_dict

        elif plc_flag:
            # Extract PVs from all collected PLC db files
            if not all_plc_db_paths:
                print("No valid PLC db files found")
                return []

            seen = set()
            unique_pvs = []
            for path in all_plc_db_paths:
                if os.path.exists(path):
                    pvs = _extract_pvs_from_file(path)
                    for pv in pvs:
                        if pv not in seen:
                            seen.add(pv)
                            unique_pvs.append(pv)
            return unique_pvs

    # Flags are not set, grep for PVs using matches
    return grep_pvs(all_matches, False, find_makefile)

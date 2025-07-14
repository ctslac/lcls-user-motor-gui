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


def grep_pvs(paths, plc_flag, usr_db_path=None):
    """
    Extracts PV .db or .pvlist file paths from grep match lines.
    Looks for id:'ioc-name' and dir: 'path/to/ioc'
    """
    db_paths = []
    if usr_db_path is None:
        dir_pattern = re.compile(r"dir:\s*'([^']+)'")
        id_pattern = re.compile(r"id:'([^']+)'")

        for line in paths:
            dir_match = dir_pattern.search(line)
            id_match = id_pattern.search(line)

            if dir_match and id_match:
                dir_path = dir_match.group(1)
                ioc_name = id_match.group(1)

                if dir_path.startswith("/reg/") or dir_path.startswith("/cds/"):
                    if plc_flag:
                        iocboot_path = os.path.join(dir_path, "iocBoot")
                        subdirs = glob.glob(os.path.join(iocboot_path, "*"))
                        full_dir_path = None
                        if len(subdirs) == 1:
                            db_files = glob.glob(os.path.join(subdirs[0], "*.db"))
                            if db_files:
                                full_dir_path = db_files[0]
                    else:
                        full_dir_path = os.path.join(
                            dir_path,
                            "build",
                            "iocBoot",
                            f"{ioc_name}",
                            f"{ioc_name.removeprefix('ioc-')}.db",
                        )
                else:
                    if plc_flag:
                        iocboot_path = os.path.join(
                            "/reg/g/pcds/epics", dir_path, "iocBoot"
                        )
                        subdirs = glob.glob(os.path.join(iocboot_path, "*"))
                        full_dir_path = None
                        if len(subdirs) == 1:
                            db_files = glob.glob(os.path.join(subdirs[0], "*.db"))
                            if db_files:
                                full_dir_path = db_files[0]
                    else:
                        full_dir_path = os.path.join(
                            "/reg/g/pcds/epics",
                            dir_path,
                            "build",
                            "iocBoot",
                            f"{ioc_name.removeprefix('ioc-')}.db",
                        )

                if not full_dir_path or not os.path.exists(full_dir_path):
                    print("Could not find a .db file, looking for pvlist...")
                    full_dir_path = os.path.join(
                        "/reg/d/iocData", ioc_name, "iocInfo", "IOC.pvlist"
                    )

                db_paths.append(full_dir_path)
    else:
        db_paths.append(usr_db_path)

    pv_list = []
    db_re_helper = re.compile(r'record\s*\(\s*\w+\s*,\s*"([^"]+)"')
    for path in db_paths:
        try:
            with open(path, "r") as f:
                if path.endswith(".pvlist"):
                    for line in f:
                        pv_list.append(line.split(",")[0].strip())
                else:
                    for line in f:
                        match = db_re_helper.search(line)
                        if match:
                            pv = match.group(1)
                            pv_list.append(pv)
        except Exception as e:
            print(f"Exception: {e}")
            continue

    return pv_list


def grep_file(filepath, regex):
    flags = re.IGNORECASE
    pattern = re.compile(regex, flags)
    matches = []

    try:
        with open(filepath, "r") as f:
            for line in f:
                if pattern.search(line):
                    matches.append(line.strip())
    except Exception as e:
        print(f"Failed to read {filepath}: {e}")

    return matches


def discover_pvs(keyword, hutch="all", plc_flag=False, usr_db_path=None):
    """
    Searches iocmanager.cfg files for an IOC and extracts PV paths from db or pvlist files.

    Inputs:
    keyword : str
        IOC name to search for.
    hutch : str
        One of the valid hutches, or "all" (default).
    plc_flag (optional): bool
        Is this IOC for a plc? If so, it canges the search path for the db

    Returns:
    pv_paths : list of str containing all pvs that were found

    """
    if usr_db_path is not None and os.path.isfile(usr_db_path):
        pv_paths = grep_pvs(usr_db_path, plc_flag, usr_db_path)
        return pv_paths

    elif usr_db_path is not None:
        raise FileExistsError(
            f"Invalid db path file provided: {usr_db_path}. File does not exist"
        )

    else:
        if hutch not in VALID_HUTCHES:
            raise ValueError(
                f"Invalid hutch: {hutch}. Must be one of: {', '.join(VALID_HUTCHES)}"
            )

        if hutch == "all":
            path_pattern = "/reg/g/pcds/pyps/config/*/iocmanager.cfg"
        else:
            path_pattern = f"/reg/g/pcds/pyps/config/{hutch}/iocmanager.cfg"

        files = glob.glob(path_pattern, recursive=True)
        if not files and os.path.isfile(path_pattern):
            files = [path_pattern]

        all_matches = []
        for file in files:
            all_matches.extend(grep_file(file, keyword))

        if len(all_matches) == 0:
            print("Could not find any files that match that ioc..")
        else:
            pv_paths = grep_pvs(all_matches, plc_flag)
            return pv_paths
    return 0

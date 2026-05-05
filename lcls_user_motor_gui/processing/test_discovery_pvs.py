import discover_pvs

if __name__ == "__main__":
    pvlist = discover_pvs.discover_pvs(
        "ioc-lcls-plc-template-user-motors", plc_flag=True, find_makefile=True
    )
    with open("pvlist_test.txt", "w") as f:
        for pv in pvlist:
            f.write(pv + "\n")

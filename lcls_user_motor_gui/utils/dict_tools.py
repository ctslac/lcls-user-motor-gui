from processing.parse_pvs import strip_key


def val_to_key(val, pvDict):
    key = [k for k, value in pvDict.items() if value == val]
    print(f"key: {key}")

    if not key:
        print(f"val_to_key: no key found for value {val}")
        return None

    """
    there may be more than one key for any given value, i might have to change the logic here
    """
    cleaned_axis = strip_key(key[0])
    print(f"val to key, cleaned axis: {cleaned_axis}, key: {key}")
    return str(cleaned_axis)


def find_unique_keys(prefix, pvDict):
    print("find unique di values")
    # assume Id_RBV
    unique_keys = set()  # Use a set to store unique values
    print(f"prefix: {prefix}")
    # Loop through the dictionary items
    for key, value in pvDict.items():
        # Check if the key starts with the given prefix
        if key.startswith(prefix) and (
            key.endswith("ID_RBV") or key.endswith("Id_RBV")
        ):
            # Add the value to the set of unique values
            unique_keys.add(key)

    # Return the unique values as a list
    return list(unique_keys)


def identify_di(item, pvDict):
    val = val_to_key(item, pvDict)
    if val is None:
        print(f"identify_di: no axis key found for {item}")
        return []

    things = find_unique_keys(val + ":SelG:DI:", pvDict)
    print(f"identify_config: item, {val}, DIs, {things}")

    return things


def identify_drv(item, pvDict):
    val = val_to_key(item, pvDict)
    if val is None:
        print(f"identify_drv: no axis key found for {item}")
        return []

    things = find_unique_keys(val + ":SelG:DRV:", pvDict)
    print(f"identify_config: item, {val}, DRVs, {things}")

    return things


def identify_enc(item, pvDict):
    val = val_to_key(item, pvDict)
    if val is None:
        print(f"identify_enc: no axis key found for {item}")
        return []

    things = find_unique_keys(val + ":SelG:ENC:", pvDict)
    print(f"identify_config: item, {val}, ENCs, {things}")

    return things


def strip_axis_id(item: str):
    if item is None:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("strip_axis_id received None; returning None")
        return None

    result = item.split(":SelG")[0]
    return result

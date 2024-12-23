try:
    from PyQt6.QtCore import Qt
except ImportError:
    from PyQt5.QtCore import Qt

CHECKED_STATE = Qt.CheckState.Checked.value if hasattr(Qt.CheckState.Checked, "value") else Qt.CheckState.Checked
UNCHECKED_STATE = (
    Qt.CheckState.Unchecked.value
    if hasattr(Qt.CheckState.Unchecked, "value")
    else Qt.CheckState.Unchecked
)


def is_above_2_4(version_str):
    """
    Checks if the version string represents a version higher than 2.4,
    considering only the major and minor version numbers.

    :param version_str: Version string to check (e.g., "2.5.0.1").
    :return: True if the version is higher than 2.4, False otherwise.
    """
    try:
        # Split the version into components and extract the major and minor parts
        parts = version_str.split(".")
        major = int(parts[0])
        minor = int(parts[1])

        # Check if it's a 2.X version and higher than 2.4
        return major == 2 and minor > 4
    except (IndexError, ValueError) as e:
        print(f"Invalid version string: {version_str}. Error: {e}")
        return False

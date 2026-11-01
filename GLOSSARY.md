# MO2 Download Manager

Language for downloads managed in a Mod Organizer 2 (MO2) downloads directory. A download is distinct from an installed mod.

## Language

**Download**:
A mod archive in the MO2 downloads directory, together with its metadata sidecar when one exists. Deleting a download does not uninstall a mod.
_Avoid_: Installed mod

**Metadata sidecar**:
The file associated with a download whose name is the complete archive filename followed by `.meta`, such as `Example.v1.2.7z.meta`. It records information about the download, including its source, installation status, and hidden status.

**Hidden download**:
A download marked hidden in MO2 without deleting its archive. Hidden status is distinct from whether the download is currently displayed in this plugin's table.
_Avoid_: Filtered-out download

**Filtered-out download**:
A download excluded from the current table view by search or the installed-download filter. Filtering does not change its hidden status or whether it is checked.
_Avoid_: Hidden download

**Checked download**:
A download selected by its checkbox as a target for a batch action, even when filtered out of the current view. Highlighting a row is not the same as checking a download.
_Avoid_: Highlighted row

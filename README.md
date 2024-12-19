# MO2 Download Manager+

![preview](./docs/window.png)

## What It Does

Adds a few new features to manage downloads within MO2 for hoarders like me.
Features include:

- Batch installation of mods
- Batch deletion of downloads
    - Custom auto-selection of duplicates, keeping the latest of each downloaded mod but removing old versions
- Batch removal of mods from the download list within MO2
- TBD...........

## Installing

Download the zip archive here or on [GitHub](https://github.com/aglowinthefield/mo2-download-manager/releases/) (I wrote
this README for Nexus haha)

Extract into the root of your MO2 install.

## Using

![launch](./docs/launch.png)

Click the plugins icon in the MO2 toolbar and launch with Download Manager.

**NOTE** Because 'refresh' is possibly pretty expensive if you have 100s
of GBs of downloads, it does not run on launch by default.
Hit refresh once when the window opens :)

## Feedback

Hit me up on GitHub or Nexus for issues. I'm an experienced dev
but unfortunately not with PyQt or C++, so any suggestions are
more than welcome. I made this for my own sanity and hope it's
useful for you too. Part of an upcoming suite of MO2 plugins and
improvements once I get my sea-legs with C++ and CMake.

## Building/Contributing

This project uses [Poetry](https://python-poetry.org/) for building. It should be as simple as:

`poetry install`

If you want the pycharm debugger, follow the instructions in the `Python Debug Server` section of PyCharm run
configurations if you want to use this
functionality. It'll just silently move along without it. I install the debugger separately to let MO2 recognize
it inside the plugin directory. Run below to do the same:

`pip install -r requirements.txt -t libs`

As of December 19, 2024 -- if you are using the latest version of PyCharm, you'll also want to follow
this
workaround: https://youtrack.jetbrains.com/issue/PY-77357/Python-Debug-Server-with-pydevd-pycharm-stopped-working-in-2024.3#focus=Change-27-11071318.0-0.pinned

otherwise MO2 will simply freeze when you try to start it with the debug server enabled.
